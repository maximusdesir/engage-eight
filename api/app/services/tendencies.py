"""Tendency aggregation + CSV ingest, scoped to one team workspace.

Reuses the ml ``engage8`` tendency, charting and Hudl code so the API and the
offline pipeline compute identical numbers. Every function takes the owning
``team_id``; callers must have checked ownership first.
"""
from __future__ import annotations

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.ml  # noqa: F401  (puts engage8 on sys.path)
from engage8 import vocab as ml_vocab  # noqa: E402
from engage8.charting import load_charting  # noqa: E402
from engage8.hudl import load_hudl, looks_like_hudl  # noqa: E402
from engage8.tendencies import SPLITS, tendency_table  # noqa: E402

from app.db.models import Play, Upload
from app.services import vocab as vocab_service

VALID_SOURCES = ("auto", "charting", "hudl")


class DuplicateUpload(Exception):
    def __init__(self, existing: Upload):
        self.existing = existing
        super().__init__(
            f"This file was already uploaded to this team as '{existing.filename}' "
            f"(upload {existing.id}). Delete that upload first to re-import it."
        )


# Canonical columns tendency_table actually reads off the frame.
_TENDENCY_COLUMNS = (
    "down", "ydstogo", "yardline_100", "quarter", "hash", "play_type",
    "play_family", "explosive", "epa", "formation", "motion_type",
)

# Play model columns we map across from a canonical frame.
_PLAY_COLUMNS = (
    "offense_team", "defense_team", "quarter", "game_seconds_remaining",
    "down", "ydstogo", "yardline_100", "hash", "score_differential",
    "personnel", "formation", "motion_type", "shotgun", "no_huddle",
    "play_type", "play_family", "pass_concept", "run_concept",
    "result_yards", "epa", "explosive",
)
_BOOL_COLUMNS = ("explosive", "shotgun", "no_huddle")


def _none_if_na(value):
    """Coerce pandas NaN/NA/NaT to ``None`` for ORM insertion."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return value
    return value


def _plays_to_frame(plays: list[Play]) -> pd.DataFrame:
    return pd.DataFrame(
        [{col: getattr(p, col) for col in _TENDENCY_COLUMNS} for p in plays],
        columns=list(_TENDENCY_COLUMNS),
    )


def scoped_plays(
    db: Session,
    team_id: int,
    team: str | None = None,
    opponent_id: int | None = None,
):
    """SELECT for a team workspace's plays, optionally narrowed."""
    stmt = select(Play).where(Play.team_id == team_id)
    if team is not None:
        stmt = stmt.where(Play.offense_team == team)
    if opponent_id is not None:
        stmt = stmt.where(Play.opponent_id == opponent_id)
    return stmt


def get_tendencies(
    db: Session,
    team_id: int,
    split: str = "down_distance",
    team: str | None = None,
    opponent_id: int | None = None,
) -> list[dict]:
    """Aggregate a team workspace's plays into a tendency table.

    Formation/motion are folded through the team's vocabulary mapping. Raises
    ``ValueError`` for an unknown split (the router maps that to a 400).
    """
    if split not in SPLITS:
        raise ValueError(f"Unknown split '{split}'. Choose from {list(SPLITS)}.")

    plays = db.scalars(scoped_plays(db, team_id, team, opponent_id)).all()
    if not plays:
        return []

    df = _plays_to_frame(plays)
    fmap, mmap = vocab_service.build_maps(db, team_id)
    # Pre-fold raw values with the team's mapping; the split's own normalize
    # pass (built-in vocab) is idempotent on canonical values.
    df["formation"] = df["formation"].map(lambda v: ml_vocab.normalize_formation(v, fmap))
    df["motion_type"] = df["motion_type"].map(lambda v: ml_vocab.normalize_motion(v, mmap))
    return tendency_table(df, split).to_dict(orient="records")


def ingest_csv(
    db: Session,
    team_id: int,
    file_path: str,
    *,
    filename: str,
    sha256: str,
    source: str = "auto",
    default_team: str | None = None,
    opponent_id: int | None = None,
) -> dict:
    """Load a charting OR Hudl CSV into a team workspace as one Upload.

    ``source`` is auto|charting|hudl ("auto" sniffs the headers).
    ``default_team`` labels offense_team on rows that don't carry one. Raises
    ``DuplicateUpload`` if this team already imported the same bytes.
    """
    if source not in VALID_SOURCES:
        raise ValueError(f"Unknown source '{source}'. Choose from {list(VALID_SOURCES)}.")

    existing = db.scalar(
        select(Upload).where(Upload.team_id == team_id, Upload.sha256 == sha256)
    )
    if existing is not None:
        raise DuplicateUpload(existing)

    resolved = source
    if resolved == "auto":
        resolved = "hudl" if looks_like_hudl(file_path) else "charting"

    if resolved == "hudl":
        df = load_hudl(file_path, default_offense_team=default_team)
    else:
        df = load_charting(file_path)
        if default_team:
            blank = df["offense_team"].isna() | (df["offense_team"].astype(str).str.strip() == "")
            df.loc[blank, "offense_team"] = default_team

    upload = Upload(
        team_id=team_id, opponent_id=opponent_id, filename=filename[:255],
        source=resolved, sha256=sha256, n_plays=len(df),
    )
    db.add(upload)
    db.flush()

    for record in df.to_dict(orient="records"):
        values = {col: _none_if_na(record.get(col)) for col in _PLAY_COLUMNS}
        for col in _BOOL_COLUMNS:
            if values[col] is not None:
                values[col] = bool(values[col])
        db.add(Play(team_id=team_id, opponent_id=opponent_id, upload_id=upload.id, **values))
    db.commit()

    teams = sorted({str(t) for t in df["offense_team"].dropna().unique()})
    fmap, mmap = vocab_service.build_maps(db, team_id)
    unmapped = vocab_service.unmapped_values(
        db, team_id, formation_map=fmap, motion_map=mmap, upload_id=upload.id
    )
    return {
        "upload_id": upload.id,
        "inserted": len(df),
        "teams": teams,
        "source": resolved,
        "unmapped_formations": unmapped["formations"],
        "unmapped_motions": unmapped["motions"],
        "skipped": df.attrs.get("skipped", {}),
        "unresolved_play_names": df.attrs.get("unresolved_play_names", []),
    }

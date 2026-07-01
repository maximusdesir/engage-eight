"""Tendency aggregation + charting-ingest service.

Reuses the ml ``engage8`` tendency and charting code so the API and the offline
pipeline compute identical numbers. The engage8 package lives in the sibling
``ml`` project (``settings.ml_root``) and is put on ``sys.path`` here.
"""
from __future__ import annotations

import sys

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Play
from app.services import vocab as vocab_service

# Make the engage8 ml package importable. settings.ml_root points at ../ml.
_ml_root = str(settings.ml_root)
if _ml_root not in sys.path:
    sys.path.insert(0, _ml_root)

from engage8 import vocab as ml_vocab  # noqa: E402
from engage8.charting import load_charting  # noqa: E402
from engage8.hudl import load_hudl, looks_like_hudl  # noqa: E402
from engage8.tendencies import SPLITS, tendency_table  # noqa: E402

VALID_SOURCES = ("auto", "charting", "hudl")

# Canonical columns tendency_table actually reads off the frame.
_TENDENCY_COLUMNS = (
    "down",
    "ydstogo",
    "yardline_100",
    "quarter",
    "hash",
    "play_type",
    "play_family",
    "explosive",
    "epa",
    "formation",
    "motion_type",
)

# Play model columns we map across from a load_charting() canonical frame.
_PLAY_COLUMNS = (
    "game_id",
    "offense_team",
    "defense_team",
    "quarter",
    "game_seconds_remaining",
    "down",
    "ydstogo",
    "yardline_100",
    "hash",
    "score_differential",
    "personnel",
    "formation",
    "motion_type",
    "play_type",
    "play_family",
    "pass_concept",
    "run_concept",
    "result_yards",
    "epa",
    "explosive",
)


def _none_if_na(value):
    """Coerce pandas NaN/NA/NaT to ``None`` for ORM insertion."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        # pd.isna on array-likes can raise; scalars are what we expect here.
        return value
    return value


def _plays_to_frame(plays: list[Play]) -> pd.DataFrame:
    """Build a DataFrame with just the columns tendency_table needs."""
    return pd.DataFrame(
        [{col: getattr(p, col) for col in _TENDENCY_COLUMNS} for p in plays],
        columns=list(_TENDENCY_COLUMNS),
    )


def get_tendencies(
    db: Session,
    split: str = "down_distance",
    team: str | None = None,
    team_id: int | None = None,
) -> list[dict]:
    """Aggregate stored plays into a tendency table.

    Filters to ``offense_team == team`` when a team is given. When ``team_id`` is
    given, that team's formation/motion vocabulary mapping is applied on read, so
    naming variants collapse onto the canonical vocabulary. Raises ``ValueError``
    for an unknown split (the router maps that to a 400). Returns an empty list
    when there are no matching plays.
    """
    if split not in SPLITS:
        raise ValueError(
            f"Unknown split '{split}'. Choose from {list(SPLITS)}."
        )

    stmt = select(Play)
    if team is not None:
        stmt = stmt.where(Play.offense_team == team)
    plays = db.scalars(stmt).all()
    if not plays:
        return []

    df = _plays_to_frame(plays)
    if team_id is not None:
        fmap, mmap = vocab_service.build_maps(db, team_id)
        # Pre-fold raw values with the team's mapping; the split's own
        # normalize pass (built-in vocab) is idempotent on canonical values.
        df["formation"] = df["formation"].map(
            lambda v: ml_vocab.normalize_formation(v, fmap)
        )
        df["motion_type"] = df["motion_type"].map(
            lambda v: ml_vocab.normalize_motion(v, mmap)
        )
    table = tendency_table(df, split)
    return table.to_dict(orient="records")


def _persist_canonical(db: Session, df, source: str) -> dict:
    """Insert a canonical-schema DataFrame as Play rows and summarize."""
    plays: list[Play] = []
    for record in df.to_dict(orient="records"):
        values = {col: _none_if_na(record.get(col)) for col in _PLAY_COLUMNS}
        explosive = values.get("explosive")
        values["explosive"] = None if explosive is None else bool(explosive)
        play = Play(**values)
        plays.append(play)
        db.add(play)

    db.commit()

    teams = sorted({p.offense_team for p in plays if p.offense_team is not None})
    preview = tendency_table(df).head().to_dict(orient="records") if len(df) else []
    # Raw formation/motion values the built-in vocab did not recognize, so the
    # upload screen can prompt the coach to map them (built-in only; per-team
    # mappings are resolved later on the Vocabulary screen).
    unmapped = vocab_service.unmapped_values(db, team=None) if not teams else \
        _union_unmapped(db, teams)
    return {
        "inserted": len(plays),
        "teams": teams,
        "source": source,
        "split_preview": preview,
        "unmapped_formations": unmapped["formations"],
        "unmapped_motions": unmapped["motions"],
    }


def _union_unmapped(db: Session, teams: list[str]) -> dict[str, list[str]]:
    """Union unmapped formation/motion raws across the given offense teams."""
    formations: list[str] = []
    motions: list[str] = []
    for team in teams:
        u = vocab_service.unmapped_values(db, team=team)
        formations.extend(u["formations"])
        motions.extend(u["motions"])
    return {
        "formations": sorted(set(formations), key=str.upper),
        "motions": sorted(set(motions), key=str.upper),
    }


def ingest_csv(
    db: Session, file_path: str, source: str = "auto", default_team: str | None = None
) -> dict:
    """Load a charting OR Hudl CSV into canonical rows and persist them.

    ``source`` is one of auto|charting|hudl. With "auto" the file's headers are
    sniffed to pick the right loader. ``default_team`` labels offense_team on
    rows that don't carry one (useful for tagging an opponent's export).
    """
    if source not in VALID_SOURCES:
        raise ValueError(
            f"Unknown source '{source}'. Choose from {list(VALID_SOURCES)}."
        )
    resolved = source
    if resolved == "auto":
        resolved = "hudl" if looks_like_hudl(file_path) else "charting"

    if resolved == "hudl":
        df = load_hudl(file_path, default_offense_team=default_team)
    else:
        df = load_charting(file_path)
        if default_team:
            blank = df["offense_team"].isna() | (df["offense_team"].astype(str) == "")
            df.loc[blank, "offense_team"] = default_team

    return _persist_canonical(db, df, resolved)


def ingest_charting_csv(db: Session, file_path: str) -> dict:
    """Backward-compatible wrapper that forces the charting format."""
    return ingest_csv(db, file_path, source="charting")

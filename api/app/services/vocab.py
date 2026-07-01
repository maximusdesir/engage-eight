"""Per-team formation/motion vocabulary mapping.

Wraps the ml ``engage8.vocab`` normalizers with the DB-backed per-team mapping
table so raw import strings ("Trips Rt") fold onto the canonical vocabulary.
Mappings are stored per owned team; normalization is applied on read, so editing
a mapping updates tendencies/predictions without re-importing.
"""
from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import Play, VocabMapping

# Make the engage8 ml package importable (mirrors services/tendencies.py).
_ml_root = str(settings.ml_root)
if _ml_root not in sys.path:
    sys.path.insert(0, _ml_root)

from engage8 import vocab as ml_vocab  # noqa: E402

VOCAB_KINDS = ("formation", "motion")


def canonical_options() -> dict[str, list[str]]:
    """The canonical vocabulary offered to the mapping UI and predict dropdowns."""
    return {
        "formations": list(ml_vocab.CANONICAL_FORMATIONS),
        "motions": list(ml_vocab.CANONICAL_MOTIONS),
    }


def build_maps(db: Session, team_id: int) -> tuple[dict[str, str], dict[str, str]]:
    """Return (formation_map, motion_map) normalize-ready dicts for a team."""
    rows = db.scalars(
        select(VocabMapping).where(VocabMapping.team_id == team_id)
    ).all()
    fmap = ml_vocab.build_mapping(
        (r.raw_value, r.canonical_value) for r in rows if r.kind == "formation"
    )
    mmap = ml_vocab.build_mapping(
        (r.raw_value, r.canonical_value) for r in rows if r.kind == "motion"
    )
    return fmap, mmap


def list_mappings(db: Session, team_id: int) -> list[VocabMapping]:
    return list(
        db.scalars(
            select(VocabMapping)
            .where(VocabMapping.team_id == team_id)
            .order_by(VocabMapping.kind, VocabMapping.raw_value)
        )
    )


def upsert_mapping(
    db: Session, team_id: int, kind: str, raw_value: str, canonical_value: str
) -> VocabMapping:
    """Create or update one raw->canonical mapping (unique per team+kind+raw)."""
    if kind not in VOCAB_KINDS:
        raise ValueError(f"Unknown kind '{kind}'. Use one of {list(VOCAB_KINDS)}.")
    existing = db.scalar(
        select(VocabMapping).where(
            VocabMapping.team_id == team_id,
            VocabMapping.kind == kind,
            VocabMapping.raw_value == raw_value,
        )
    )
    if existing is not None:
        existing.canonical_value = canonical_value
        return existing
    row = VocabMapping(
        team_id=team_id, kind=kind, raw_value=raw_value, canonical_value=canonical_value
    )
    db.add(row)
    return row


def _dedup(values) -> list[str]:
    """Dedup case-insensitively, keeping the first representative of each key."""
    seen: set[str] = set()
    out: list[str] = []
    for v in values:
        key = v.upper()
        if key not in seen:
            seen.add(key)
            out.append(v)
    return sorted(out, key=str.upper)


def unmapped_values(
    db: Session,
    team: str | None = None,
    formation_map: dict[str, str] | None = None,
    motion_map: dict[str, str] | None = None,
) -> dict[str, list[str]]:
    """Raw formation/motion values on stored plays that still fall through.

    A value is "unmapped" when neither the team's mapping nor the built-in vocab
    recognizes it (``normalize_*`` returns a passthrough). This is what the
    Vocabulary screen (and later a picture picker) asks the coach to resolve.
    """
    fmap = formation_map or {}
    mmap = motion_map or {}

    def _distinct(column):
        stmt = select(column).distinct()
        if team is not None:
            stmt = stmt.where(Play.offense_team == team)
        return [v for v in db.scalars(stmt).all() if v is not None]

    f_unmapped = [
        ml_vocab.normalize_formation(raw, fmap)
        for raw in _distinct(Play.formation)
        if not ml_vocab.is_canonical(
            "formation", ml_vocab.normalize_formation(raw, fmap)
        )
        and ml_vocab.normalize_formation(raw, fmap) is not None
    ]
    m_unmapped = [
        ml_vocab.normalize_motion(raw, mmap)
        for raw in _distinct(Play.motion_type)
        if ml_vocab.normalize_motion(raw, mmap) != "NONE"
        and not ml_vocab.is_canonical(
            "motion", ml_vocab.normalize_motion(raw, mmap)
        )
    ]
    return {"formations": _dedup(f_unmapped), "motions": _dedup(m_unmapped)}

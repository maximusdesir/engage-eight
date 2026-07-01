"""Per-team formation/motion vocabulary routes.

A coach maps their raw import strings ("Trips Rt") onto the canonical vocabulary
so tendencies and predictions combine naming variants. Everything is scoped to
the current user's team. This is the seam a picture-based picker plugs into
later: the picker just POSTs a canonical_value.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import User
from app.deps import get_current_user, get_db
from app.routers.teams import _get_owned_team
from app.schemas.vocab import (
    CanonicalOptions,
    MappingIn,
    MappingOut,
    VocabResponse,
)
from app.services import vocab as vocab_service

router = APIRouter(tags=["vocab"])


@router.get("/teams/{team_id}/vocab", response_model=VocabResponse)
def get_vocab(
    team_id: int,
    team: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> VocabResponse:
    """Canonical options, this team's mappings, and still-unmapped raw values.

    ``team`` optionally filters unmapped detection to one offense_team's plays.
    """
    _get_owned_team(team_id, db, user)
    fmap, mmap = vocab_service.build_maps(db, team_id)
    unmapped = vocab_service.unmapped_values(
        db, team=team, formation_map=fmap, motion_map=mmap
    )
    return VocabResponse(
        canonical=CanonicalOptions(**vocab_service.canonical_options()),
        mappings=[MappingOut.model_validate(m) for m in vocab_service.list_mappings(db, team_id)],
        unmapped=unmapped,
    )


@router.post("/teams/{team_id}/vocab", response_model=list[MappingOut])
def set_vocab(
    team_id: int,
    payload: list[MappingIn],
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[MappingOut]:
    """Upsert one or more raw->canonical mappings for the team."""
    _get_owned_team(team_id, db, user)
    saved = [
        vocab_service.upsert_mapping(
            db, team_id, m.kind, m.raw_value, m.canonical_value
        )
        for m in payload
    ]
    db.commit()
    return [MappingOut.model_validate(m) for m in saved]

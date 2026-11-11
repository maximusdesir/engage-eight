"""Tendency tables over one of the caller's teams' plays."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import Team
from app.deps import get_db, owned_team
from app.schemas.tendency import TendencyResponse
from app.services import tendencies as tendency_service

router = APIRouter(prefix="/teams/{team_id}", tags=["tendencies"])


@router.get("/tendencies", response_model=TendencyResponse)
def get_tendencies(
    split: str = "down_distance",
    team: str | None = None,
    opponent_id: int | None = None,
    owner_team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> TendencyResponse:
    """Run/pass split + top play per bucket for the chosen dimension.

    Only this team's plays are used. ``team`` narrows to one offense_team
    label (e.g. the opponent's name used on upload); ``opponent_id`` to plays
    tagged with one of this team's opponents. Formation/motion buckets use
    this team's vocabulary mapping. An unknown split returns 400.
    """
    try:
        rows = tendency_service.get_tendencies(
            db, owner_team.id, split=split, team=team, opponent_id=opponent_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return TendencyResponse(
        team_id=owner_team.id, team=team, opponent_id=opponent_id, split=split, rows=rows
    )

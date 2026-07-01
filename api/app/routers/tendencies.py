"""Public tendency endpoint.

Serves the coach-facing "what do they like to do" tables, computed from the
plays stored in the database via the ml engage8 tendency engine.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import User
from app.deps import get_current_user_optional, get_db
from app.routers.teams import _get_owned_team
from app.schemas.tendency import TendencyResponse
from app.services import tendencies as tendency_service

router = APIRouter(tags=["tendencies"])


@router.get("/tendencies", response_model=TendencyResponse)
def get_tendencies(
    team: str | None = None,
    split: str = "down_distance",
    team_id: int | None = None,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
) -> TendencyResponse:
    """Run/pass split + top play per bucket for the chosen dimension.

    Public endpoint (no auth) when ``team_id`` is omitted. ``split`` selects
    the aggregation dimension; an unknown split returns a 400 listing the
    valid choices. Passing ``team_id`` applies that team's formation/motion
    vocabulary mapping so naming variants collapse onto the canonical
    vocabulary -- a private, per-team resource, so it requires auth and
    ownership of that team (same check as ``/teams/{id}/vocab``), else a
    caller could read another team's mapping by observing shifted buckets.
    """
    if team_id is not None:
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required to view a team's mapped tendencies.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        _get_owned_team(team_id, db, user)
    try:
        rows = tendency_service.get_tendencies(
            db, split=split, team=team, team_id=team_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return TendencyResponse(team=team, split=split, rows=rows)

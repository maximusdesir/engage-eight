"""Team and opponent routes. Everything is scoped to the current user."""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Opponent, Team, User
from app.deps import get_current_user, get_db, get_owned_team
from app.schemas.team import (
    OpponentCreate,
    OpponentOut,
    TeamCreate,
    TeamOut,
)

router = APIRouter(tags=["teams"])


@router.get("/teams", response_model=list[TeamOut])
def list_teams(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Team]:
    return list(db.scalars(select(Team).where(Team.owner_id == user.id)))


@router.post("/teams", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Team:
    team = Team(
        owner_id=user.id,
        name=payload.name,
        level=payload.level,
        season=payload.season,
    )
    db.add(team)
    db.commit()
    db.refresh(team)
    return team


@router.get("/teams/{team_id}", response_model=TeamOut)
def get_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Team:
    return get_owned_team(team_id, db, user)


@router.get("/teams/{team_id}/opponents", response_model=list[OpponentOut])
def list_opponents(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[Opponent]:
    get_owned_team(team_id, db, user)
    return list(db.scalars(select(Opponent).where(Opponent.team_id == team_id)))


@router.post(
    "/teams/{team_id}/opponents",
    response_model=OpponentOut,
    status_code=status.HTTP_201_CREATED,
)
def create_opponent(
    team_id: int,
    payload: OpponentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Opponent:
    get_owned_team(team_id, db, user)
    opponent = Opponent(
        team_id=team_id,
        name=payload.name,
        oc_name=payload.oc_name,
        notes=payload.notes,
    )
    db.add(opponent)
    db.commit()
    db.refresh(opponent)
    return opponent

"""Play routes, scoped to one of the caller's teams."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Play, Team
from app.deps import check_opponent, get_db, owned_team
from app.schemas.team import PlayCreate, PlayOut
from app.services.tendencies import scoped_plays

router = APIRouter(prefix="/teams/{team_id}", tags=["plays"])


@router.get("/plays", response_model=list[PlayOut])
def list_plays(
    offense_team: str | None = None,
    opponent_id: int | None = None,
    down: int | None = None,
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> list[Play]:
    stmt = scoped_plays(db, team.id, offense_team, opponent_id)
    if down is not None:
        stmt = stmt.where(Play.down == down)
    stmt = stmt.order_by(Play.id).offset(offset).limit(limit)
    return list(db.scalars(stmt))


@router.post("/plays", response_model=PlayOut, status_code=status.HTTP_201_CREATED)
def create_play(
    payload: PlayCreate,
    team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> Play:
    check_opponent(db, team.id, payload.opponent_id)
    play = Play(team_id=team.id, **payload.model_dump())
    db.add(play)
    db.commit()
    db.refresh(play)
    return play


@router.delete("/plays/{play_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_play(
    play_id: int,
    team: Team = Depends(owned_team),
    db: Session = Depends(get_db),
) -> None:
    play = db.scalar(select(Play).where(Play.id == play_id, Play.team_id == team.id))
    if play is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Play not found")
    db.delete(play)
    db.commit()

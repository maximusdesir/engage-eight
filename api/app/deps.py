"""Shared FastAPI dependencies: DB session and current-user resolution."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.security import decode_access_token
from .db.models import Opponent, Team, User
from .db.session import SessionLocal

# tokenUrl points at the login route the auth router exposes.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login", auto_error=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _decode_user(token: str, db: Session) -> User:
    creds_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    sub = decode_access_token(token)
    if sub is None:
        raise creds_exc
    user = db.get(User, int(sub))
    if user is None:
        raise creds_exc
    return user


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return _decode_user(token, db)


def get_owned_team(team_id: int, db: Session, user: User) -> Team:
    """Fetch a team, 404ing unless it exists and belongs to the user."""
    team = db.scalar(select(Team).where(Team.id == team_id, Team.owner_id == user.id))
    if team is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Team not found")
    return team


def owned_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Team:
    """Dependency for ``/teams/{team_id}/...`` routes: the caller's team or 404."""
    return get_owned_team(team_id, db, user)


def check_opponent(db: Session, team_id: int, opponent_id: int | None) -> None:
    """404 unless ``opponent_id`` (if given) belongs to ``team_id``."""
    if opponent_id is None:
        return
    found = db.scalar(
        select(Opponent.id).where(Opponent.id == opponent_id, Opponent.team_id == team_id)
    )
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opponent not found")

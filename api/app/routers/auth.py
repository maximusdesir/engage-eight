"""Authentication routes: signup, login, and the current-user lookup."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import User
from app.deps import get_current_user, get_db
from app.schemas.auth import DemoSession, Token, UserCreate, UserOut
from app.services import demo as demo_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("signup", 10, 3600))],
)
def signup(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # role is not taken from the payload; it defaults to "coach" in the model.
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post(
    "/login",
    response_model=Token,
    dependencies=[Depends(rate_limit("login", 10, 60))],
)
def login(
    form: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> Token:
    user = db.scalar(select(User).where(User.email == form.username))
    if user is None or not verify_password(form.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(access_token=create_access_token(str(user.id)))


@router.post(
    "/demo",
    response_model=DemoSession,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(
        "demo", 10, 3600,
        detail="Too many demos from your network. Try again in an hour, or take the quiz.",
    ))],
)
def start_demo(db: Session = Depends(get_db)) -> DemoSession:
    """Create a throwaway account with a team and the fictional Central HS film.

    No credentials needed. The account is purged after 24 hours.
    """
    demo_service.purge_demo_users(db)  # a long-lived process never hits the startup purge
    if demo_service.count_demo_users(db) >= settings.demo_max_accounts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="The demo is full for today. Try again tomorrow, or take the quiz.",
        )
    user, team, opponent = demo_service.create_demo_session(db)
    return DemoSession(
        access_token=create_access_token(str(user.id)),
        team_id=team.id,
        opponent_id=opponent.id,
        opponent_name=opponent.name,
    )


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user

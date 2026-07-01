"""Shared FastAPI dependencies: DB session and current-user resolution."""
from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .core.security import decode_access_token
from .db.models import User
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


def get_current_user_optional(
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    """Like ``get_current_user``, but returns ``None`` instead of 401 when no
    token is supplied at all (a present-but-invalid token still raises 401).

    Lets one endpoint serve both anonymous requests and requests that need an
    authenticated, ownership-checked resource depending on the query.
    """
    if not token:
        return None
    return _decode_user(token, db)

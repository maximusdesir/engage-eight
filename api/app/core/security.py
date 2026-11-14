"""Password hashing and JWT helpers.

Auth routers build on these; deps.get_current_user decodes tokens with them.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from ..config import settings

# Checked when an email has no account, so a wrong email takes as long as a
# wrong password and response times don't reveal which emails are registered.
_DUMMY_HASH = bcrypt.hashpw(b"engage8-timing-equalizer", bcrypt.gensalt()).decode("utf-8")


def _to_bytes(plain: str) -> bytes:
    # bcrypt only uses the first 72 bytes; truncate explicitly to avoid errors.
    return plain.encode("utf-8")[:72]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str | None) -> bool:
    """Check a password. ``hashed=None`` (no such user) still spends a bcrypt
    check, then fails."""
    try:
        ok = bcrypt.checkpw(_to_bytes(plain), (hashed or _DUMMY_HASH).encode("utf-8"))
    except ValueError:
        return False
    return ok and hashed is not None


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes or settings.access_token_expire_minutes
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the subject (user id) if valid, else None."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.InvalidTokenError:
        return None
    sub = payload.get("sub")
    return sub if isinstance(sub, str) and sub.isdigit() else None

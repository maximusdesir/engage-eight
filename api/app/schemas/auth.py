"""Pydantic v2 schemas for authentication: users and tokens."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.config import settings


class UserCreate(BaseModel):
    """Signup payload.

    Note: role is intentionally NOT accepted here. Letting a client choose its
    own role at signup is a privilege-escalation hole; the role defaults to
    "coach" server-side and is only changed through a trusted admin path.
    """

    email: EmailStr
    password: str = Field(
        min_length=settings.min_password_length,
        max_length=128,
        description=f"At least {settings.min_password_length} characters.",
    )


class UserOut(BaseModel):
    """Public view of a user (never exposes the password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    is_demo: bool = False


class Token(BaseModel):
    """Bearer access token returned on login."""

    access_token: str
    token_type: str = "bearer"


class DemoSession(Token):
    """A fresh demo account: the token plus where its sample data lives."""

    team_id: int
    opponent_id: int
    opponent_name: str

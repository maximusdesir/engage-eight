"""SQLAlchemy ORM models for Engage Eight.

A trimmed version of the full schema, enough for the API's first pass: users,
teams, opponents, games, plays, and stored predictions. Multi-tenancy is kept
simple (a user owns teams) and can grow into orgs later.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="coach")  # admin|coach|analyst|player
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    teams: Mapped[list["Team"]] = relationship(back_populates="owner")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    level: Mapped[str] = mapped_column(String(20), default="hs")  # hs|college|nfl|club
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    owner: Mapped["User"] = relationship(back_populates="teams")
    opponents: Mapped[list["Opponent"]] = relationship(back_populates="team")


class Opponent(Base):
    __tablename__ = "opponents"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    oc_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    team: Mapped["Team"] = relationship(back_populates="opponents")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    opponent_id: Mapped[int | None] = mapped_column(ForeignKey("opponents.id"), nullable=True)
    season: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual")  # nflverse|manual|hudl


class Play(Base):
    """Canonical play row. Mirrors ml/engage8 config.CANONICAL_COLUMNS."""
    __tablename__ = "plays"

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int | None] = mapped_column(ForeignKey("games.id"), index=True, nullable=True)
    offense_team: Mapped[str | None] = mapped_column(String(40), index=True, nullable=True)
    defense_team: Mapped[str | None] = mapped_column(String(40), nullable=True)

    quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    game_seconds_remaining: Mapped[int | None] = mapped_column(Integer, nullable=True)
    down: Mapped[int | None] = mapped_column(Integer, index=True, nullable=True)
    ydstogo: Mapped[int | None] = mapped_column(Integer, nullable=True)
    yardline_100: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hash: Mapped[str | None] = mapped_column(String(1), nullable=True)
    score_differential: Mapped[int | None] = mapped_column(Integer, nullable=True)

    personnel: Mapped[str | None] = mapped_column(String(4), nullable=True)
    formation: Mapped[str | None] = mapped_column(String(40), nullable=True)
    motion_type: Mapped[str | None] = mapped_column(String(40), nullable=True)

    play_type: Mapped[str | None] = mapped_column(String(10), nullable=True)  # run|pass
    play_family: Mapped[str | None] = mapped_column(String(40), nullable=True)
    pass_concept: Mapped[str | None] = mapped_column(String(40), nullable=True)
    run_concept: Mapped[str | None] = mapped_column(String(40), nullable=True)

    result_yards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    epa: Mapped[float | None] = mapped_column(Float, nullable=True)
    explosive: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class VocabMapping(Base):
    """Per-team raw->canonical mapping for formations and pre-snap motions.

    Teams name formations/motions differently, so raw import strings ("Trips Rt")
    are stored on plays as-is and folded onto the canonical vocabulary on read.
    A coach resolves unrecognized raws here; the row is the seam a picture-based
    picker plugs into later (it just writes canonical_value).
    """
    __tablename__ = "vocab_mappings"
    __table_args__ = (
        UniqueConstraint("team_id", "kind", "raw_value", name="uq_vocab_team_kind_raw"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))  # formation|motion
    raw_value: Mapped[str] = mapped_column(String(80))
    canonical_value: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    game_state: Mapped[str] = mapped_column(Text)        # JSON string of inputs
    result: Mapped[str] = mapped_column(Text)            # JSON string of output
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

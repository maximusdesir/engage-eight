"""Pydantic v2 schemas for teams, opponents, and plays."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    level: Literal["hs", "college", "nfl", "club"] = "hs"
    season: int | None = None


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    level: str
    season: int | None = None


class OpponentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    oc_name: str | None = None
    notes: str | None = None


class OpponentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    name: str
    oc_name: str | None = None
    notes: str | None = None


class PlayCreate(BaseModel):
    """The chartable fields for a single play."""

    # Required situational fields.
    down: int = Field(ge=1, le=4)
    ydstogo: int = Field(ge=0, le=99)
    yardline_100: int = Field(ge=1, le=99)
    play_type: Literal["run", "pass"]

    # Optional context.
    opponent_id: int | None = None
    offense_team: str | None = Field(None, max_length=40)
    defense_team: str | None = None
    quarter: int | None = None
    game_seconds_remaining: int | None = None
    hash: Literal["L", "M", "R"] | None = None
    score_differential: int | None = None
    personnel: str | None = Field(None, max_length=4)
    formation: str | None = Field(None, max_length=40)
    motion_type: str | None = Field(None, max_length=40)
    shotgun: bool | None = None
    no_huddle: bool | None = None
    play_family: str | None = Field(None, max_length=40)
    pass_concept: str | None = Field(None, max_length=40)
    run_concept: str | None = Field(None, max_length=40)
    result_yards: int | None = None


class PlayOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    opponent_id: int | None = None
    upload_id: int | None = None
    down: int | None = None
    ydstogo: int | None = None
    yardline_100: int | None = None
    play_type: str | None = None
    offense_team: str | None = None
    defense_team: str | None = None
    quarter: int | None = None
    game_seconds_remaining: int | None = None
    hash: str | None = None
    score_differential: int | None = None
    personnel: str | None = None
    formation: str | None = None
    motion_type: str | None = None
    shotgun: bool | None = None
    no_huddle: bool | None = None
    play_family: str | None = None
    pass_concept: str | None = None
    run_concept: str | None = None
    result_yards: int | None = None


class UploadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    opponent_id: int | None = None
    filename: str
    source: str
    n_plays: int
    created_at: datetime

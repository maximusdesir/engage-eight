"""Pydantic v2 schemas for the prediction + recommendation endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class PredictRequest(BaseModel):
    """A single pre-snap situation to score.

    The model uses the situation plus shotgun/no-huddle. ``formation`` and
    ``motion_type`` are only used, together with ``team_id`` and
    ``offense_team``, to blend in that opponent's uploaded plays.
    """

    model_config = ConfigDict(extra="ignore")

    down: int = Field(..., ge=1, le=4, description="Current down (1-4).")
    distance: int = Field(..., ge=1, le=99, description="Yards to go for a first down.")
    yardline_100: int = Field(
        ..., ge=1, le=99, description="Yards from the opponent's goal line."
    )
    quarter: int = Field(2, ge=1, le=5, description="Quarter (5 = OT).")
    game_seconds_remaining: int | None = Field(
        None, ge=0, le=3600,
        description="Seconds left in the game. Default: 10:00 left in the quarter.",
    )
    score_differential: int = Field(
        0, ge=-99, le=99, description="Offense score minus defense score."
    )
    posteam_timeouts: int = Field(3, ge=0, le=3)
    shotgun: bool | None = Field(None, description="QB in shotgun/pistol. Unknown if omitted.")
    no_huddle: bool | None = Field(None, description="Offense skipped the huddle.")

    # Opponent-specific blend (optional, needs a team you own).
    team_id: int | None = None
    offense_team: str | None = Field(None, max_length=40)
    opponent_id: int | None = None
    formation: str | None = Field(None, max_length=40)
    motion_type: str | None = Field(None, max_length=40)


class BlendStep(BaseModel):
    """One level of the opponent blend, e.g. this opponent on 3rd & long."""

    label: str
    plays: int
    pass_rate: float
    pass_prob_after: float


class PredictResponse(BaseModel):
    """Calibrated run/pass lean for a situation."""

    pass_prob: float
    run_prob: float
    lean: str
    confidence: float
    why: str
    model_pass_prob: float          # league model alone, before any blend
    blend: list[BlendStep] = []     # empty when no opponent plays were used


class DefensiveCall(BaseModel):
    """A rules-based defensive suggestion (no model score attached)."""

    front: str
    coverage: str
    pressure: str
    stunt: str
    rationale: str


class RecommendRequest(PredictRequest):
    """Recommendation requests carry the same situation fields as a predict."""


class RecommendResponse(BaseModel):
    """The prediction plus rules-based defensive calls, in suggested order."""

    predicted: PredictResponse
    recommendations: list[DefensiveCall]
    basis: str = (
        "Rules-based suggestions keyed off the run/pass lean and the situation. "
        "Not scored by a model."
    )

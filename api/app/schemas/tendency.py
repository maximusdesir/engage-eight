"""Pydantic v2 schemas for the tendency + charting-upload endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TendencyRow(BaseModel):
    """One aggregated bucket from the ml tendency_table."""

    model_config = ConfigDict(extra="ignore")

    bucket: str
    plays: int
    run_pct: float
    pass_pct: float
    explosive_pct: float
    avg_epa: float | None = None
    top_play: str


class TendencyResponse(BaseModel):
    """A full tendency table for a team (or all teams) by a chosen split."""

    team: str | None = None
    split: str
    rows: list[TendencyRow]


class UploadSummary(BaseModel):
    """Result of ingesting a charting or Hudl CSV."""

    inserted: int
    teams: list[str]
    source: str          # "charting" or "hudl" (the format actually used)
    message: str
    # Raw formation/motion values the built-in vocab didn't recognize; the
    # upload screen prompts the coach to map these on the Vocabulary screen.
    unmapped_formations: list[str] = []
    unmapped_motions: list[str] = []

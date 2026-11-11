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
    explosive_pct: float | None = None   # None when no yards were charted
    avg_epa: float | None = None
    top_play: str


class TendencyResponse(BaseModel):
    """A tendency table over one team workspace's plays, by a chosen split."""

    team_id: int
    team: str | None = None           # offense_team label filter, if any
    opponent_id: int | None = None
    split: str
    rows: list[TendencyRow]


class UploadSummary(BaseModel):
    """Result of ingesting a charting or Hudl CSV."""

    upload_id: int
    inserted: int
    teams: list[str]
    source: str          # "charting" or "hudl" (the format actually used)
    message: str
    # Raw formation/motion values the built-in vocab didn't recognize; the
    # upload screen prompts the coach to map these on the Vocabulary screen.
    unmapped_formations: list[str] = []
    unmapped_motions: list[str] = []
    # Rows dropped during import and why, e.g. {"unknown_run_pass": 3}, plus
    # the play names that couldn't be called run or pass.
    skipped: dict[str, int] = {}
    unresolved_play_names: list[str] = []

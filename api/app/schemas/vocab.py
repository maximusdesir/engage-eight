"""Pydantic schemas for the per-team formation/motion vocabulary endpoints."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


class CanonicalOptions(BaseModel):
    """The canonical vocabulary offered as mapping targets / predict choices."""

    formations: list[str]
    motions: list[str]


class MappingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    raw_value: str
    canonical_value: str


class MappingIn(BaseModel):
    """One raw->canonical mapping to upsert."""

    kind: str              # formation | motion
    raw_value: str
    canonical_value: str

    @field_validator("kind")
    @classmethod
    def _valid_kind(cls, v: str) -> str:
        if v not in ("formation", "motion"):
            raise ValueError("kind must be 'formation' or 'motion'")
        return v


class VocabResponse(BaseModel):
    """Everything the Vocabulary screen needs for one team."""

    canonical: CanonicalOptions
    mappings: list[MappingOut]
    unmapped: dict[str, list[str]]   # {"formations": [...], "motions": [...]}

"""Formation / pre-snap motion vocabulary and normalization.

Every team names its formations and motions differently, and the raw strings
arrive three ways: Hudl free-text ("Trips Rt"), manual charting ("Trips"), and
nflverse codes ("SHOTGUN"). Left untouched, those are distinct categories to the
tendency engine and the model, so "Trips Rt" and "Trips" never combine.

This module defines a small starter canonical vocabulary and normalizers that
collapse raw values onto it. Normalization is deliberately non-destructive:
- an explicit per-team ``mapping`` (raw -> canonical) wins first,
- then built-in synonyms / direction-stripping,
- otherwise the cleaned raw string is returned unchanged (a "passthrough"),

so an unrecognized value is never silently dropped -- the API flags passthroughs
as "unmapped" so a coach can map them (later, by picture).

The normalizers mirror the tolerant style of ``_parse_hash`` / ``_parse_personnel``
in ``hudl.py``.
"""
from __future__ import annotations

import pandas as pd

# --- Starter canonical vocabulary -----------------------------------------
# A seed set, not the last word. Coaches extend it per team via mappings; the
# point is a stable spine the tendency engine and model can key on. Values are
# uppercase tokens. Formation blends alignment families (coach terms) with the
# nflverse ``offense_formation`` codes so all three sources land here.
CANONICAL_FORMATIONS: tuple[str, ...] = (
    "TRIPS", "DOUBLES", "TREY", "EMPTY", "PRO", "ACE",
    "I-FORM", "PISTOL", "HEAVY", "WILDCAT",
    "SHOTGUN", "SINGLEBACK", "JUMBO",
)

CANONICAL_MOTIONS: tuple[str, ...] = (
    "NONE", "JET", "ORBIT", "SHIFT", "ACROSS", "RETURN", "SHORT", "POP",
)

# Raw (uppercased) -> canonical. Direction-stripping (below) handles the
# "... RT / LEFT / STRONG" variants, so these only cover true synonyms.
_FORMATION_SYNONYMS: dict[str, str] = {
    "3X1": "TRIPS", "TREYS": "TREY",
    "2X2": "DOUBLES", "DEUCE": "DOUBLES", "DEUCES": "DOUBLES",
    "EMPTY GUN": "EMPTY", "SPREAD EMPTY": "EMPTY",
    "GUN": "SHOTGUN", "SPREAD": "SHOTGUN",
    "SINGLE BACK": "SINGLEBACK", "ONE BACK": "SINGLEBACK",
    "I FORM": "I-FORM", "IFORM": "I-FORM", "I_FORM": "I-FORM", "I": "I-FORM",
    "PISTOL GUN": "PISTOL",
    "WILD": "WILDCAT", "WILDCAT GUN": "WILDCAT",
    "GOAL LINE": "HEAVY", "GOALLINE": "HEAVY", "BIG": "HEAVY",
}

_MOTION_SYNONYMS: dict[str, str] = {
    "FLY": "JET", "JET SWEEP": "JET", "SPEED": "JET",
    "ORBIT RETURN": "ORBIT",
    "MOTION": "SHIFT", "SHIFT MOTION": "SHIFT",
    "CROSS": "ACROSS", "CROSSER": "ACROSS", "OVER": "ACROSS",
    "COME BACK": "RETURN", "BOOMERANG": "RETURN",
    "SHORT MOTION": "SHORT", "TIGHT": "SHORT",
    "POP MOTION": "POP",
}

# Values that mean "no pre-snap motion".
_MOTION_NONE = {"NONE", "NO", "N/A", "NA", "-", "0", "STATIC", "NM", "NO MOTION"}

# Trailing/leading strength or direction words we ignore when matching, so
# "Trips Rt" and "Trips Left" both fold to TRIPS.
_DIRECTION_TOKENS = {
    "RT", "LT", "RIGHT", "LEFT", "R", "L",
    "STRONG", "WEAK", "STR", "WK", "TO", "AWAY", "BOSS", "OPEN", "CLOSED",
}


def _clean(raw) -> str | None:
    """Trim, collapse internal whitespace; return None for null/empty."""
    if raw is None:
        return None
    try:
        if pd.isna(raw):
            return None
    except (TypeError, ValueError):
        pass  # array-likes; not expected for scalars
    s = " ".join(str(raw).strip().split())
    return s or None


def _strip_direction(key: str) -> str:
    toks = [t for t in key.split() if t not in _DIRECTION_TOKENS]
    return " ".join(toks)


def _match(key: str, synonyms: dict[str, str], canonical: tuple[str, ...]) -> str | None:
    if key in synonyms:
        return synonyms[key]
    if key in canonical:
        return key
    return None


def normalize_formation(raw, mapping: dict[str, str] | None = None) -> str | None:
    """Fold a raw formation string onto the canonical vocabulary.

    ``mapping`` is a per-team ``{RAW_UPPER: canonical}`` override (see
    ``build_mapping``) and wins over the built-ins. Returns None for null/empty
    and the cleaned raw string for anything unrecognized (a passthrough).
    """
    s = _clean(raw)
    if s is None:
        return None
    key = s.upper()
    if mapping and key in mapping:
        return mapping[key]
    hit = _match(key, _FORMATION_SYNONYMS, CANONICAL_FORMATIONS)
    if hit:
        return hit
    base = _strip_direction(key)
    if base != key:
        if mapping and base in mapping:
            return mapping[base]
        hit = _match(base, _FORMATION_SYNONYMS, CANONICAL_FORMATIONS)
        if hit:
            return hit
    return s


def normalize_motion(raw, mapping: dict[str, str] | None = None) -> str | None:
    """Fold a raw motion string onto the canonical vocabulary.

    None/empty and explicit "no motion" values both return "NONE". Unrecognized
    values pass through as the cleaned raw string.
    """
    s = _clean(raw)
    if s is None:
        return "NONE"
    key = s.upper()
    if mapping and key in mapping:
        return mapping[key]
    if key in _MOTION_NONE:
        return "NONE"
    hit = _match(key, _MOTION_SYNONYMS, CANONICAL_MOTIONS)
    if hit:
        return hit
    base = _strip_direction(key)
    if base != key:
        if mapping and base in mapping:
            return mapping[base]
        if base in _MOTION_NONE:
            return "NONE"
        hit = _match(base, _MOTION_SYNONYMS, CANONICAL_MOTIONS)
        if hit:
            return hit
    return s


def build_mapping(pairs) -> dict[str, str]:
    """Build a normalize-ready mapping from (raw_value, canonical_value) pairs.

    Keys are uppercased/whitespace-collapsed to match the normalizers' lookups.
    """
    out: dict[str, str] = {}
    for raw, canonical in pairs:
        cleaned = _clean(raw)
        if cleaned is None or not canonical:
            continue
        out[cleaned.upper()] = str(canonical)
    return out


def is_canonical(kind: str, value: str | None) -> bool:
    """Whether ``value`` is already a recognized canonical token for ``kind``."""
    if value is None:
        return False
    if kind == "formation":
        return value in CANONICAL_FORMATIONS
    if kind == "motion":
        return value in CANONICAL_MOTIONS
    raise ValueError(f"Unknown vocab kind '{kind}'. Use 'formation' or 'motion'.")

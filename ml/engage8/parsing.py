"""Shared, null-safe parsing helpers for the CSV loaders (charting, Hudl).

Real exports are messy: blank cells, a UTF-8 BOM on the header row, free-text
play names, and yes/no flags spelled a dozen ways. Every helper here returns a
missing value (``pd.NA``) rather than raising when a cell is blank, and none of
them feed a nullable comparison into ``np.where`` (which raises
``TypeError: boolean value of NA is ambiguous``).
"""
from __future__ import annotations

import re

import pandas as pd

from . import config


def is_blank(value) -> bool:
    if value is None:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        return False
    return str(value).strip() == ""


def read_csv(path) -> pd.DataFrame:
    """Read an export CSV, tolerating a BOM and fully blank rows."""
    df = pd.read_csv(path, encoding="utf-8-sig", skip_blank_lines=True)
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how="all")


def to_int(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").round().astype("Int64")


def half_from_quarter(quarter: pd.Series) -> pd.Series:
    """1 for Q1-2, 2 for Q3+ (OT counts as the second half), NA if unknown."""
    q = pd.to_numeric(quarter, errors="coerce")
    half = pd.Series(pd.NA, index=quarter.index, dtype="Int64")
    half[q.notna() & (q <= 2)] = 1
    half[q.notna() & (q > 2)] = 2
    return half


def explosive_flag(play_type: pd.Series, result_yards: pd.Series) -> pd.Series:
    """1/0 explosive by play type, NA when yards or play type are unknown."""
    yards = pd.to_numeric(result_yards, errors="coerce")
    thresh = play_type.map(
        {"run": config.EXPLOSIVE_RUN_YARDS, "pass": config.EXPLOSIVE_PASS_YARDS}
    ).astype("Float64")
    out = pd.Series(pd.NA, index=play_type.index, dtype="Int64")
    known = yards.notna() & thresh.notna()
    out[known] = (yards[known] >= thresh[known]).astype(int)
    return out


# --- Yes/no flags ----------------------------------------------------------
_TRUE = {"1", "Y", "YES", "TRUE", "T", "X"}
_FALSE = {"0", "N", "NO", "FALSE", "F"}


def parse_flag(value) -> object:
    if is_blank(value):
        return pd.NA
    s = str(value).strip().upper()
    if s.endswith(".0"):
        s = s[:-2]
    if s in _TRUE:
        return 1
    if s in _FALSE:
        return 0
    return pd.NA


def _tokens(text) -> set[str]:
    return set(re.findall(r"[A-Z0-9]+", str(text).upper()))


def parse_shotgun(*texts) -> object:
    """Infer shotgun (1) / under center (0) from formation or backfield text.

    Returns NA when the text doesn't say either way, which is most formation
    names ("Trips", "Doubles"). Pistol is counted as shotgun, matching how the
    NFL play-by-play the model trains on tags it.
    """
    for text in texts:
        if is_blank(text):
            continue
        toks = _tokens(text)
        if toks & {"GUN", "SHOTGUN", "PISTOL", "SG"}:
            return 1
        if toks & {"UC", "UNDER"} or {"UNDER", "CENTER"} <= toks:
            return 0
    return pd.NA


def parse_tempo(value) -> object:
    """No-huddle flag from a Hudl-style tempo/huddle column."""
    if is_blank(value):
        return pd.NA
    flag = parse_flag(value)
    if flag is not pd.NA:
        return flag
    s = str(value).strip().upper()
    if any(k in s for k in ("NO HUDDLE", "NOHUDDLE", "HURRY", "TEMPO", "FAST")) \
            or s in ("NH", "NHQ", "Q"):
        return 1
    if "HUDDLE" in s or s in ("H", "NORMAL", "REG"):
        return 0
    return pd.NA


# --- Run vs pass -----------------------------------------------------------
# Matched as whole words in the play-type column or the play name. Play-action
# and screens count as pass (they are dropbacks), matching the model's label.
_PASS_EXACT = {"P", "PASS", "DROPBACK", "DB"}
_RUN_EXACT = {"R", "RUN", "RUSH"}
_PASS_WORDS = {
    "PASS", "PASSING", "SCREEN", "DROPBACK", "PA", "BOOT", "BOOTLEG", "WAGGLE",
    "SPRINTOUT", "ROLLOUT", "MESH", "STICK", "SMASH", "FLOOD", "SNAG",
    "SPACING", "CURL", "CURLS", "FLAT", "SLANT", "SLANTS", "VERT", "VERTS",
    "VERTICALS", "SEAM", "SEAMS", "WHEEL", "DIG", "SAIL", "LEVELS", "SHALLOW",
    "HITCH", "HITCHES", "FADE", "HAIL", "TUNNEL", "BUBBLE", "SWING",
    "JAILBREAK", "DAGGER",
}
_PASS_PHRASES = ("PLAY ACTION", "PLAY-ACTION", "DROP BACK")
_RUN_WORDS = {
    "RUN", "RUSH", "DRAW", "SWEEP", "ZONE", "IZ", "OZ", "POWER", "COUNTER",
    "DIVE", "ISO", "TRAP", "TOSS", "DUO", "WHAM", "BUCK", "SNEAK", "WEDGE",
    "BELLY", "OPTION", "KEEP", "KEEPER", "PITCH", "STRETCH", "MIDLINE", "VEER",
    "REVERSE",
}
# Present in the name, these make it a pass even next to a run word
# ("PA Power", "RB Screen", "Boot Wham").
_PASS_OVERRIDE = {"PA", "SCREEN", "BOOT", "BOOTLEG", "WAGGLE"}


def _classify(text) -> object:
    if is_blank(text):
        return pd.NA
    s = " ".join(str(text).strip().upper().split())
    if s in _PASS_EXACT:
        return "pass"
    if s in _RUN_EXACT:
        return "run"
    toks = _tokens(s)
    if "RPO" in toks:
        return pd.NA          # outcome depends on the read; can't call it
    if any(p in s for p in _PASS_PHRASES) or toks & _PASS_OVERRIDE:
        return "pass"
    is_pass = bool(toks & _PASS_WORDS)
    is_run = bool(toks & _RUN_WORDS)
    if is_pass != is_run:
        return "pass" if is_pass else "run"
    return pd.NA              # neither, or both (ambiguous)


def parse_play_type(raw, play_name=None) -> object:
    """Resolve run vs pass from a play-type column, falling back to the name.

    Returns NA when neither says (e.g. "RPO", or a team-specific name); the
    caller reports those rows instead of guessing.
    """
    first = _classify(raw)
    if first is not pd.NA:
        return first
    return _classify(play_name)

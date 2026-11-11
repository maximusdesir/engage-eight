"""Hudl CSV adapter: map a Hudl breakdown export into the canonical schema.

Hudl breakdown/playlist exports vary team to team because the columns are
user-configured, so this adapter is deliberately tolerant: it normalizes the
header names, maps the common ones through an alias table, converts Hudl's
yard-line and hash conventions, and leaves anything it can't map null (the
model and tendency code both handle nulls).

    python -m engage8.hudl --template          # write a sample Hudl-style CSV
    python -m engage8.hudl --load export.csv    # validate + summarize
"""
from __future__ import annotations

import argparse
import re

import pandas as pd

from . import config
from .parsing import (
    half_from_quarter, explosive_flag, is_blank, parse_flag, parse_play_type,
    parse_shotgun, parse_tempo, read_csv, to_int,
)

# Normalized Hudl header -> intermediate field. Headers are matched after
# uppercasing, dropping '.', and collapsing whitespace (so "Dist." -> "DIST").
HUDL_ALIASES = {
    "DN": "down", "DOWN": "down",
    "DIST": "ydstogo", "DISTANCE": "ydstogo", "TO GO": "ydstogo", "TOGO": "ydstogo",
    "QTR": "quarter", "QUARTER": "quarter", "PERIOD": "quarter",
    "HASH": "hash", "HASH MARK": "hash", "HM": "hash",
    "OFF FORM": "formation", "OFF FORMATION": "formation", "FORMATION": "formation",
    "OFFENSIVE FORMATION": "formation", "FORM": "formation",
    "MOTION": "motion_type", "MO": "motion_type",
    "PERS": "personnel", "PERSONNEL": "personnel", "OFF PERS": "personnel",
    "PLAY TYPE": "play_type_raw", "TYPE": "play_type_raw",
    "RUN/PASS": "play_type_raw", "R/P": "play_type_raw", "PLAY CATEGORY": "play_type_raw",
    "OFF PLAY": "play_name", "PLAY": "play_name", "PLAY NAME": "play_name",
    "PLAY CALL": "play_name", "CONCEPT": "play_name",
    "GN/LS": "result_yards", "GN/LOSS": "result_yards", "GAIN/LOSS": "result_yards",
    "GAIN": "result_yards", "GN": "result_yards", "YARDS": "result_yards",
    "YDS": "result_yards", "RESULT YARDS": "result_yards",
    "YARD LN": "yardline_raw", "YARD LINE": "yardline_raw", "YDLN": "yardline_raw",
    "YD LN": "yardline_raw", "LOS": "yardline_raw", "BALL ON": "yardline_raw",
    "ODK": "odk", "PHASE": "odk",
    "OFF TEAM": "offense_team", "DEF TEAM": "defense_team",
    "BACKFIELD": "backfield", "BACKFIELD SET": "backfield", "OFF BACKFIELD": "backfield",
    "QB ALIGN": "backfield", "QB SET": "backfield",
    "SHOTGUN": "shotgun_raw", "GUN": "shotgun_raw",
    "NO HUDDLE": "tempo_raw", "TEMPO": "tempo_raw", "HUDDLE": "tempo_raw",
    "NH": "tempo_raw",
}

# Hudl-ish headers used to auto-detect a Hudl file vs the plain charting CSV.
HUDL_SIGNAL_HEADERS = {"ODK", "OFF FORM", "GN/LS", "YARD LN", "DN", "OFF PLAY"}

TEMPLATE_PATH = config.DATA_DIR / "hudl_sample.csv"


def _norm_header(h) -> str:
    return " ".join(str(h).upper().replace(".", "").split())


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return the column if present, else an all-null Series aligned to df."""
    if name in df.columns:
        return df[name]
    return pd.Series([pd.NA] * len(df), index=df.index)


def _parse_hash(value) -> object:
    if is_blank(value):
        return pd.NA
    s = str(value).strip().upper()
    if not s:
        return pd.NA
    if s[0] == "L":
        return "L"
    if s[0] == "R":
        return "R"
    if s[0] in ("M", "C") or s.startswith("MID"):
        return "M"
    return pd.NA


def _parse_personnel(value) -> object:
    """Pull a clean two-digit personnel grouping (e.g. '11', '21') if present."""
    if is_blank(value):
        return pd.NA
    m = re.search(r"\d{2}", str(value))
    return m.group() if m else pd.NA


def _yl_from_signed(iv: int) -> object:
    """Yard line under Hudl's sign convention: negative=own, positive=opp."""
    a = abs(iv)
    if a == 0 or a > 50:
        return pd.NA
    if a == 50:
        return 50            # midfield
    return 100 - a if iv < 0 else a


def _parse_yardline(value) -> object:
    """Convert a Hudl yard-line value to yardline_100 (yards to opp goal).

    Hudl encodes territory by sign: a negative value (or "OWN N") is your own
    side, a positive/unsigned value (or "OPP N") is the opponent's side.
      -35 / OWN 35  -> 100 - 35 = 65
      +30 / OPP 30 / 30 -> 30
      50 / C / MID  -> 50 (midfield)
    Note: pandas often strips a leading '+', so an unsigned positive number is
    treated as opponent territory, matching the dominant Hudl convention.
    """
    if is_blank(value):
        return pd.NA
    # Numeric input: the sign is authoritative.
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return _yl_from_signed(int(round(float(value))))

    s = str(value).strip().upper().replace(" ", "")
    if not s or s == "NAN":
        return pd.NA
    if s in ("C", "MID", "MIDFIELD"):
        return 50

    own = None
    if s.startswith("OWN") or s.startswith("-"):
        own = True
    elif s.startswith("OPP") or s.startswith("+"):
        own = False

    m = re.search(r"\d+", s)
    if not m:
        return pd.NA
    yard = int(m.group())
    if own is True:
        return _yl_from_signed(-yard)
    if own is False:
        return _yl_from_signed(yard)
    return _yl_from_signed(yard)  # unsigned -> opponent territory (convention)


def _clip(series: pd.Series, n: int) -> pd.Series:
    return series.map(lambda v: pd.NA if is_blank(v) else str(v).strip()[:n])


def load_hudl(path, default_offense_team: str | None = None) -> pd.DataFrame:
    """Load a Hudl breakdown CSV and map it to the canonical Play schema.

    Rows that can't be used are dropped and counted in ``df.attrs["skipped"]``
    (no down, or run/pass couldn't be determined), with the unresolved play
    names in ``df.attrs["unresolved_play_names"]`` so the caller can report
    them instead of losing them silently.
    """
    raw = read_csv(path)

    colmap = {c: HUDL_ALIASES[_norm_header(c)] for c in raw.columns
              if _norm_header(c) in HUDL_ALIASES}
    # If the same intermediate field maps from two columns, keep the first.
    seen: set[str] = set()
    dedup = {}
    for src, dst in colmap.items():
        if dst not in seen:
            dedup[src] = dst
            seen.add(dst)
    work = raw[list(dedup)].rename(columns=dedup)

    # Keep offensive plays when an ODK/phase column exists.
    if "odk" in work.columns:
        first = work["odk"].map(lambda v: "" if is_blank(v) else str(v).strip().upper()[:1])
        work = work[first == "O"]

    out = pd.DataFrame(index=work.index)
    out["down"] = to_int(_col(work, "down"))
    out["ydstogo"] = to_int(_col(work, "ydstogo"))
    out["quarter"] = to_int(_col(work, "quarter"))
    out["yardline_100"] = to_int(_col(work, "yardline_raw").map(_parse_yardline))
    out["hash"] = _col(work, "hash").map(_parse_hash)
    out["personnel"] = _col(work, "personnel").map(_parse_personnel)
    out["formation"] = _clip(_col(work, "formation"), 40)
    out["backfield"] = _clip(_col(work, "backfield"), 40)
    out["motion_type"] = _clip(_col(work, "motion_type"), 40)

    # Shotgun: an explicit column wins, else infer from backfield/formation.
    explicit = _col(work, "shotgun_raw").map(parse_flag)
    inferred = pd.Series(
        [parse_shotgun(b, f) for b, f in zip(out["backfield"], out["formation"])],
        index=out.index, dtype="object",
    )
    out["shotgun"] = explicit.where(explicit.notna(), inferred).astype("Int64")
    out["no_huddle"] = _col(work, "tempo_raw").map(parse_tempo).astype("Int64")

    play_name = _col(work, "play_name")
    pt_raw = _col(work, "play_type_raw")
    out["play_type"] = pd.Series(
        [parse_play_type(a, b) for a, b in zip(pt_raw, play_name)],
        index=out.index, dtype="object",
    )
    out["play_family"] = _clip(play_name, 40)
    out["result_yards"] = to_int(_col(work, "result_yards"))

    team = _col(work, "offense_team")
    if default_offense_team is not None:
        team = team.map(lambda v: default_offense_team if is_blank(v) else v)
    out["offense_team"] = team
    out["defense_team"] = _col(work, "defense_team")

    # Keep only real run/pass plays with a down (the prediction target), and
    # account for everything dropped.
    no_down = out["down"].isna()
    unresolved = ~no_down & ~out["play_type"].isin(["run", "pass"])
    unresolved_names = sorted(
        {str(v) for v in out.loc[unresolved, "play_family"] if not is_blank(v)},
        key=str.upper,
    )
    out = out[~no_down & ~unresolved].copy()

    out["half"] = half_from_quarter(out["quarter"])
    out["explosive"] = explosive_flag(out["play_type"], out["result_yards"])
    out["play_id"] = [f"hudl_{i}" for i in range(len(out))]

    for col in config.CANONICAL_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    out = out[config.CANONICAL_COLUMNS].reset_index(drop=True)
    out.attrs["skipped"] = {
        "no_down": int(no_down.sum()),
        "unknown_run_pass": int(unresolved.sum()),
    }
    out.attrs["unresolved_play_names"] = unresolved_names
    teams = [t for t in out["offense_team"].dropna().unique().tolist()]
    print(f"Loaded {len(out):,} Hudl offensive plays" + (f" for {teams}" if teams else ""))
    if unresolved.any():
        print(f"  skipped {int(unresolved.sum())} plays with no run/pass call: "
              f"{unresolved_names[:10]}")
    return out


def looks_like_hudl(path) -> bool:
    """Heuristic: does this CSV's header row look like a Hudl export?"""
    try:
        header = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
    except Exception:
        return False
    norm = {_norm_header(c) for c in header}
    # The plain charting CSV uses exact lowercase canonical names.
    if "play_type" in {str(c).strip() for c in header}:
        return False
    return len(norm & HUDL_SIGNAL_HEADERS) >= 2


def write_template(path=TEMPLATE_PATH) -> None:
    config.ensure_data_dirs()
    rows = [
        ["1", "O", "1", "10", "-25", "L", "Trips Rt", "Inside Zone", "Run", "Jet", "11", "5", "1"],
        ["2", "O", "2", "5", "-30", "R", "Doubles", "Stick", "Pass", "None", "11", "8", "1"],
        ["3", "O", "3", "2", "+45", "M", "Heavy", "Power", "Run", "", "21", "1", "2"],
        ["4", "D", "1", "10", "+20", "L", "", "", "", "", "", "0", "2"],
        ["5", "O", "3", "9", "-40", "R", "Empty", "Four Verticals", "Pass", "", "10", "-2", "3"],
    ]
    cols = ["PLAY #", "ODK", "DN", "DIST", "YARD LN", "HASH", "OFF FORM",
            "OFF PLAY", "PLAY TYPE", "MOTION", "PERS", "GN/LS", "QTR"]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)
    print(f"Wrote sample Hudl-style CSV -> {path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Hudl breakdown CSV adapter.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--template", action="store_true", help="write a sample Hudl CSV")
    g.add_argument("--load", type=str, help="path to a Hudl export CSV")
    p.add_argument("--team", type=str, default=None, help="label offense_team for all rows")
    args = p.parse_args()

    if args.template:
        write_template()
    else:
        plays = load_hudl(args.load, default_offense_team=args.team)
        from .tendencies import tendency_table
        print(tendency_table(plays).to_string(index=False))


if __name__ == "__main__":
    main()

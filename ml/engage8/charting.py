"""Manual charting: bring your own opponent.

For teams that aren't in nflverse (your actual Friday/Saturday opponent), chart
their plays into a simple CSV and load it into the same canonical schema the
tendency + prediction engine uses.

    python -m engage8.charting --template            # write a blank template
    python -m engage8.charting --load opponent.csv   # validate + summarize
"""
from __future__ import annotations

import argparse

import pandas as pd

from . import config
from .parsing import (
    explosive_flag, half_from_quarter, parse_flag, parse_play_type,
    parse_shotgun, read_csv,
)

# The minimal columns a coach/analyst fills in while charting film.
CHARTING_COLUMNS = [
    "game_id", "offense_team", "defense_team",
    "quarter", "game_seconds_remaining",
    "down", "ydstogo", "yardline_100", "hash",
    "score_differential",
    "personnel", "formation", "backfield", "motion_type",
    "shotgun", "no_huddle",
    "play_type", "play_family", "pass_concept", "run_concept",
    "result_yards",
]

TEMPLATE_PATH = config.DATA_DIR / "charting_template.csv"


def write_template(path=TEMPLATE_PATH) -> None:
    config.ensure_data_dirs()
    example = {
        "game_id": "2026_wk1_us_vs_central", "offense_team": "CENTRAL",
        "defense_team": "US", "quarter": 1, "game_seconds_remaining": 720,
        "down": 1, "ydstogo": 10, "yardline_100": 75, "hash": "M",
        "score_differential": 0, "personnel": "11", "formation": "Trips",
        "backfield": "Gun", "motion_type": "Jet", "shotgun": 1, "no_huddle": 0,
        "play_type": "run",
        "play_family": "Inside Zone", "pass_concept": "", "run_concept": "IZ",
        "result_yards": 5,
    }
    pd.DataFrame([example], columns=CHARTING_COLUMNS).to_csv(path, index=False)
    print(f"Wrote charting template -> {path}")
    print("Fill one row per play, then: python -m engage8.charting --load <file>")


def load_charting(path) -> pd.DataFrame:
    """Validate a charting CSV and map it to the canonical Play schema.

    ``play_type`` accepts run/pass in any case (also R/P, rush, dropback). Rows
    without a usable down or run/pass value are dropped and counted in
    ``df.attrs["skipped"]``.
    """
    df = read_csv(path)
    missing = [c for c in ("down", "ydstogo", "yardline_100", "play_type") if c not in df.columns]
    if missing:
        raise ValueError(f"Charting file missing required columns: {missing}")

    play_type = pd.Series(
        [parse_play_type(v) for v in df["play_type"]], index=df.index, dtype="object"
    )
    down = pd.to_numeric(df["down"], errors="coerce")
    no_down = down.isna()
    unresolved = ~no_down & ~play_type.isin(["run", "pass"])
    unresolved_values = sorted(
        {str(v) for v in df.loc[unresolved, "play_type"].dropna()}, key=str.upper
    )
    keep = ~no_down & ~unresolved
    df = df[keep].copy()
    df["play_type"] = play_type[keep]

    out = pd.DataFrame(index=df.index)
    for col in config.CANONICAL_COLUMNS:
        out[col] = df[col] if col in df.columns else pd.NA

    out["play_id"] = [f"chart_{i}" for i in range(len(out))]
    out["half"] = half_from_quarter(out["quarter"])
    out["no_huddle"] = out["no_huddle"].map(parse_flag).astype("Int64")
    shotgun = out["shotgun"].map(parse_flag)
    inferred = pd.Series(
        [parse_shotgun(b, f) for b, f in zip(out["backfield"], out["formation"])],
        index=out.index, dtype="object",
    )
    out["shotgun"] = shotgun.where(shotgun.notna(), inferred).astype("Int64")
    out["explosive"] = explosive_flag(out["play_type"], out["result_yards"])
    out = out[config.CANONICAL_COLUMNS].reset_index(drop=True)
    out.attrs["skipped"] = {
        "no_down": int(no_down.sum()),
        "unknown_run_pass": int(unresolved.sum()),
    }
    out.attrs["unresolved_play_names"] = unresolved_values
    print(f"Loaded {len(out):,} charted plays for "
          f"{out['offense_team'].dropna().unique().tolist()}")
    if unresolved.any():
        print(f"  skipped {int(unresolved.sum())} rows with play_type not run/pass: "
              f"{unresolved_values[:10]}")
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Manual opponent charting.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--template", action="store_true", help="write a blank CSV template")
    g.add_argument("--load", type=str, help="path to a filled charting CSV")
    args = p.parse_args()

    if args.template:
        write_template()
    else:
        plays = load_charting(args.load)
        from .tendencies import tendency_table
        print(tendency_table(plays).to_string(index=False))


if __name__ == "__main__":
    main()

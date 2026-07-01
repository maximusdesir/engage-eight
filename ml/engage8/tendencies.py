"""Tendency aggregation: the coach-facing "what do they like to do" engine.

Works on any canonical plays frame (nflverse OR manually charted opponent
data), so the same code self-scouts and opponent-scouts.

Run (quick demo against the pulled data):
    python -m engage8.tendencies --team KC
"""
from __future__ import annotations

import argparse

import pandas as pd

from . import config, vocab


def _dd_bucket(down: int, dist) -> str:
    if down == 1:
        return "1st & 10" if dist == 10 else "1st & other"
    if down == 2:
        return "2nd & short" if dist <= 3 else "2nd & medium" if dist <= 6 else "2nd & long"
    if down == 3:
        return "3rd & short" if dist <= 2 else "3rd & medium" if dist <= 6 else "3rd & long"
    return "4th down"


def _zone(yardline_100: int) -> str:
    if yardline_100 <= 20:
        return "Red zone"
    if yardline_100 <= 40:
        return "Fringe"
    if yardline_100 <= 60:
        return "Midfield"
    if yardline_100 <= 80:
        return "Own territory"
    return "Backed up"


SPLITS = {
    "down_distance": lambda df: df.apply(lambda r: _dd_bucket(r["down"], r["ydstogo"]), axis=1),
    "field_zone": lambda df: df["yardline_100"].apply(_zone),
    # Formation/motion are folded onto the canonical vocabulary so a team's
    # naming variants ("Trips Rt" / "Trips") combine into one bucket. The API
    # passes each team's raw->canonical mapping ahead of this via normalization
    # on read; the built-in synonyms below still apply offline (no mapping).
    "formation": lambda df: df["formation"].map(vocab.normalize_formation).fillna("(unknown)"),
    "motion": lambda df: df["motion_type"].map(vocab.normalize_motion).fillna("NONE"),
    "quarter": lambda df: "Q" + df["quarter"].astype(str),
    "hash": lambda df: df["hash"].fillna("(unknown)"),
}


def tendency_table(plays: pd.DataFrame, split: str = "down_distance") -> pd.DataFrame:
    """Return run/pass split + top play per bucket for the chosen dimension."""
    if split not in SPLITS:
        raise ValueError(f"Unknown split '{split}'. Choose from {list(SPLITS)}.")
    df = plays.copy()
    df["bucket"] = SPLITS[split](df)
    df["is_pass"] = (df["play_type"] == "pass").astype(int)

    rows = []
    for bucket, g in df.groupby("bucket", sort=False):
        n = len(g)
        if n == 0:
            continue
        pass_rate = g["is_pass"].mean()
        # Top play family if tagged, else fall back to run/pass.
        fam = g["play_family"].dropna()
        top_play = fam.value_counts().idxmax() if len(fam) else (
            "pass" if pass_rate >= 0.5 else "run"
        )
        rows.append({
            "bucket": bucket,
            "plays": n,
            "run_pct": round((1 - pass_rate) * 100, 1),
            "pass_pct": round(pass_rate * 100, 1),
            "explosive_pct": round(g["explosive"].fillna(0).mean() * 100, 1),
            "avg_epa": round(g["epa"].mean(), 3),
            "top_play": top_play,
        })
    out = pd.DataFrame(rows).sort_values("plays", ascending=False).reset_index(drop=True)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Show a team's tendency table.")
    p.add_argument("--team", type=str, default=None, help="offense_team code, e.g. KC")
    p.add_argument("--split", type=str, default="down_distance", choices=list(SPLITS))
    args = p.parse_args()

    if not config.PLAYS_PARQUET.exists():
        raise SystemExit("No plays.parquet yet. Run `python -m engage8.extract` first.")
    plays = pd.read_parquet(config.PLAYS_PARQUET)
    if args.team:
        plays = plays[plays["offense_team"] == args.team]
        if plays.empty:
            raise SystemExit(f"No plays for team '{args.team}'.")

    table = tendency_table(plays, args.split)
    title = f"{args.team or 'ALL'} tendencies by {args.split}"
    print("\n" + title)
    print("=" * len(title))
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()

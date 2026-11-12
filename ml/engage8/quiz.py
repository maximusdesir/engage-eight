"""Export the "Call it" quiz: real 2023 plays with the model's pass probability.

2023 is the held-out test season, so the model never trained on these plays.
For each sampled play we save the pre-snap situation, the model's calibrated
pass probability, the actual call, and the nflverse play description (shown
only after the player answers).

Play-by-play comes from nflverse (https://github.com/nflverse/nflverse-data).

Run (needs the raw 2023 pull, so run extract first):
    python -m engage8.extract --seasons 2023
    python -m engage8.quiz
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .extract import scrimmage_mask
from .predict import load_model, predict_proba

SEASON = 2023
SEED = 8
# Plays per down, 400 total. Proportional sampling would be 44% 1st down and
# 2% 4th down; these quotas keep the late downs, where the calls are harder.
QUOTAS = {1: 120, 2: 120, 3: 110, 4: 50}

REPO_ROOT = config.ML_ROOT.parent
DEFAULT_OUT = REPO_ROOT / "web" / "public" / "quiz" / "plays-2023.json"


def _intval(v) -> int | None:
    return None if pd.isna(v) else int(v)


def sample_plays(pbp: pd.DataFrame, quotas: dict[int, int], seed: int) -> pd.DataFrame:
    """Stratified-by-down sample of scrimmage run/pass plays."""
    df = pbp.loc[scrimmage_mask(pbp)].copy()
    df = df[df["desc"].notna() & df["game_seconds_remaining"].notna()]
    parts = []
    for down, n in quotas.items():
        pool = df[df["down"] == down]
        parts.append(pool.sample(n=min(n, len(pool)), random_state=seed))
    out = pd.concat(parts)
    # Shuffle so the file is not grouped by down.
    return out.sample(frac=1.0, random_state=seed).reset_index(drop=True)


def build_quiz(pbp: pd.DataFrame, artifact: dict, quotas=QUOTAS, seed=SEED) -> list[dict]:
    plays = sample_plays(pbp, quotas, seed)
    # Same called-dropback label the model trains on (scrambles/sacks = pass).
    dropback = plays["qb_dropback"].fillna(plays["play_type"].eq("pass").astype(float))

    situations, rows = [], []
    for (_, r), db in zip(plays.iterrows(), dropback):
        situation = {
            "down": int(r["down"]),
            "distance": int(r["ydstogo"]),
            "yardline_100": int(r["yardline_100"]),
            "quarter": int(r["qtr"]),
            "game_seconds_remaining": int(r["game_seconds_remaining"]),
            "score_differential": _intval(r["score_differential"]),
            "posteam_timeouts": _intval(r["posteam_timeouts_remaining"]),
            "shotgun": _intval(r["shotgun"]),
            "no_huddle": _intval(r["no_huddle"]),
        }
        situations.append(situation)
        rows.append({
            "id": f"{r['game_id']}_{int(r['play_id'])}",
            "week": int(r["week"]),
            "offense": r["posteam"],
            "defense": r["defteam"],
            "down": situation["down"],
            "distance": situation["distance"],
            "yardline_100": situation["yardline_100"],
            "quarter": situation["quarter"],
            "clock": situation["game_seconds_remaining"],
            "score_diff": situation["score_differential"],
            "timeouts": situation["posteam_timeouts"],
            "shotgun": situation["shotgun"],
            "no_huddle": situation["no_huddle"],
            "actual": "pass" if db == 1 else "run",
            "desc": " ".join(str(r["desc"]).split()),
        })

    probs = predict_proba(artifact, situations)
    for row, p in zip(rows, probs):
        row["model_pass_prob"] = round(float(p), 3)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="Export quiz plays for the web app.")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    raw = config.RAW_DIR / f"play_by_play_{SEASON}.parquet"
    if not raw.exists():
        raise SystemExit(f"{raw} not found. Run `python -m engage8.extract --seasons {SEASON}` first.")
    pbp = pd.read_parquet(raw)
    rows = build_quiz(pbp, load_model())

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": SEASON,
        "source": "nflverse play-by-play (https://github.com/nflverse/nflverse-data)",
        "note": "Held-out test season: the model never trained on these plays.",
        "plays": rows,
    }
    args.out.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    print(f"Wrote {len(rows)} plays -> {args.out} ({args.out.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()

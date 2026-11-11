"""Feature engineering: canonical plays -> model-ready feature table.

Builds situational features from fields a coach knows before the snap. Reads
plays.parquet, writes features.parquet.

Previous-play lag features were tried and dropped: with prev1/prev2/drive index
known they added 0.3 points of test accuracy (74.4% vs 74.1%, 2023), and sent
blank (the usual case in the app) they scored below the model without them.

Run:
    python -m engage8.features
"""
from __future__ import annotations

import pandas as pd

from . import config

# Features the model consumes. Every one is known before the snap and can be
# entered by a coach (or charted from film), so training and serving see the
# same inputs. Formation/personnel/motion/hash are NOT model features: they are
# null in the public NFL data, so the model could never learn from them. They
# feed the per-opponent blend in the API instead (api/app/services/blend.py).
SITUATION_FEATURES = [
    "down", "ydstogo", "yardline_100", "quarter", "half",
    "game_seconds_remaining", "score_differential", "posteam_timeouts",
    "is_goal_to_go", "is_red_zone", "is_two_minute", "is_third_and_long",
    "is_short_yardage", "field_zone",
]
PRESNAP_FLAGS = ["shotgun", "no_huddle"]

ALL_FEATURES = SITUATION_FEATURES + PRESNAP_FLAGS
TARGET = "is_pass"          # 1 = called dropback, 0 = designed run
EXPLOSIVE_TARGET = "explosive"


def _field_zone(yardline_100: pd.Series) -> pd.Series:
    """Coarse field zone: 0=backed up,1=own,2=midfield,3=fringe,4=red zone."""
    bins = [-1, 10, 40, 60, 80, 100]
    return pd.cut(yardline_100, bins=bins, labels=[4, 3, 2, 1, 0]).astype("Int64")
    # note: yardline_100 counts down toward opponent goal, so small = red zone


def build_features(plays: pd.DataFrame) -> pd.DataFrame:
    df = plays.copy()

    # Target: pass vs run.
    df["is_pass"] = (df["play_type"] == "pass").astype("Int64")

    # --- Situational flags ---------------------------------------------
    df["is_goal_to_go"] = (df["yardline_100"] <= df["ydstogo"]).astype("Int64")
    df["is_red_zone"] = (df["yardline_100"] <= 20).astype("Int64")
    df["is_two_minute"] = (
        (df["game_seconds_remaining"] <= 120)
        | ((df["game_seconds_remaining"] > 1680)
           & (df["game_seconds_remaining"] <= 1800))
    ).astype("Int64")
    df["is_third_and_long"] = (
        (df["down"] == 3) & (df["ydstogo"] >= 7)
    ).astype("Int64")
    df["is_short_yardage"] = (df["ydstogo"] <= 2).astype("Int64")
    df["field_zone"] = _field_zone(df["yardline_100"])

    keep = (
        ["play_id", "game_id", "season", "week"]
        + ALL_FEATURES
        + [TARGET, EXPLOSIVE_TARGET, "epa"]
    )
    keep = [c for c in keep if c in df.columns]
    out = df[keep].copy()
    for c in ALL_FEATURES:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").astype("float64")
    print(f"Built features: {len(out):,} rows, {len(ALL_FEATURES)} features")
    return out


def main() -> None:
    if not config.PLAYS_PARQUET.exists():
        raise SystemExit(
            f"{config.PLAYS_PARQUET} not found. Run `python -m engage8.extract` first."
        )
    plays = pd.read_parquet(config.PLAYS_PARQUET)
    config.ensure_data_dirs()
    feats = build_features(plays)
    feats.to_parquet(config.FEATURES_PARQUET, index=False)
    print(f"Wrote {config.FEATURES_PARQUET}")


if __name__ == "__main__":
    main()

"""Extract: pull nflverse play-by-play and normalize into the canonical schema.

Run:
    python -m engage8.extract --seasons 2019 2020 2021 2022 2023

Writes the canonical plays parquet to ml/data/processed/plays.parquet.
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config


NFLVERSE_PBP_URL = (
    "https://github.com/nflverse/nflverse-data/releases/download/pbp/"
    "play_by_play_{season}.parquet"
)


def fetch_nflverse(seasons: list[int]) -> pd.DataFrame:
    """Download raw nflfastR play-by-play directly from nflverse-data releases.

    We pull the published parquet per season (cached under data/raw/) rather
    than depending on nfl_data_py, whose pinned deps don't build on newer
    Python. This is the same underlying nflfastR data.
    """
    import urllib.request
    config.ensure_data_dirs()

    frames = []
    for season in seasons:
        cache = config.RAW_DIR / f"play_by_play_{season}.parquet"
        if not cache.exists():
            url = NFLVERSE_PBP_URL.format(season=season)
            print(f"  downloading {season} -> {cache.name} ...")
            req = urllib.request.Request(url, headers={"User-Agent": "engage8"})
            with urllib.request.urlopen(req, timeout=120) as r:
                cache.write_bytes(r.read())
        else:
            print(f"  using cached {cache.name}")
        frames.append(pd.read_parquet(cache))

    pbp = pd.concat(frames, ignore_index=True)
    print(f"  pulled {len(pbp):,} raw rows across {len(seasons)} season(s)")
    return pbp


def scrimmage_mask(pbp: pd.DataFrame) -> pd.Series:
    """Rows kept as run/pass scrimmage plays with a real down and spot.

    Shared with quiz.py so it picks from exactly the plays the model sees.
    """
    return (
        pbp["play_type"].isin(["run", "pass"])
        & pbp["down"].notna()
        & pbp["ydstogo"].notna()
        & pbp["yardline_100"].notna()
    )


def normalize_nflverse(pbp: pd.DataFrame) -> pd.DataFrame:
    """Map raw nflfastR columns into the canonical Play schema.

    We keep only true scrimmage run/pass plays. The label is the *called*
    play: ``qb_dropback`` marks dropbacks, so scrambles and sacks count as
    pass. (nflverse's ``play_type`` files scrambles under "run", which put
    designed passes in the run class, about 7% of "runs".)
    """
    df = pbp.loc[scrimmage_mask(pbp)].copy()

    out = pd.DataFrame(index=df.index)
    out["play_id"] = df["play_id"].astype("Int64").astype(str)
    out["game_id"] = df["game_id"].astype(str)
    out["season"] = df["season"].astype("Int64")
    out["week"] = df["week"].astype("Int64")
    out["offense_team"] = df["posteam"]
    out["defense_team"] = df["defteam"]

    out["quarter"] = df["qtr"].astype("Int64")
    out["game_seconds_remaining"] = df["game_seconds_remaining"]
    out["half"] = pd.Series(np.where(df["qtr"] <= 2, 1, 2), index=df.index).astype("Int64")

    out["down"] = df["down"].astype("Int64")
    out["ydstogo"] = df["ydstogo"].astype("Int64")
    out["yardline_100"] = df["yardline_100"].astype("Int64")
    # nflverse doesn't expose hash; leave null (manual charting can fill it).
    out["hash"] = pd.NA
    out["score_differential"] = df["score_differential"]
    out["posteam_timeouts"] = df.get("posteam_timeouts_remaining")

    # Personnel/formation/motion: mostly unavailable in public pbp -> null.
    out["personnel"] = pd.NA
    out["formation"] = df.get("offense_formation")  # present in some seasons
    out["backfield"] = pd.NA
    out["motion_type"] = pd.NA
    out["shotgun"] = df["shotgun"].astype("Int64")
    out["no_huddle"] = df["no_huddle"].astype("Int64")

    dropback = df["qb_dropback"].fillna(df["play_type"].eq("pass").astype(float))
    out["play_type"] = np.where(dropback == 1, "pass", "run")
    out["play_family"] = pd.NA
    out["pass_concept"] = pd.NA
    out["run_concept"] = pd.NA

    out["result_yards"] = df["yards_gained"]
    out["epa"] = df["epa"]
    out["success"] = (df["epa"] > 0).astype("Int64")

    # Explosive: yardage threshold by play type.
    thresh = np.where(
        out["play_type"] == "run",
        config.EXPLOSIVE_RUN_YARDS,
        config.EXPLOSIVE_PASS_YARDS,
    )
    out["explosive"] = (df["yards_gained"] >= thresh).astype("Int64")

    out = out[config.CANONICAL_COLUMNS].reset_index(drop=True)
    print(f"  normalized to {len(out):,} run/pass plays")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull & normalize nflverse pbp.")
    parser.add_argument(
        "--seasons", type=int, nargs="+", default=config.DEFAULT_SEASONS,
        help="Seasons to download (e.g. --seasons 2021 2022 2023)",
    )
    args = parser.parse_args()

    pbp = fetch_nflverse(args.seasons)
    plays = normalize_nflverse(pbp)

    plays.to_parquet(config.PLAYS_PARQUET, index=False)
    print(f"Wrote {config.PLAYS_PARQUET} ({len(plays):,} plays)")


if __name__ == "__main__":
    main()

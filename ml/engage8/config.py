"""Paths, constants, and the canonical Play schema for Engage Eight.

Everything in the pipeline reads/writes through these paths. data/ is
git-ignored and regenerated; models/ holds the committed, trained model.
"""
from __future__ import annotations

from pathlib import Path

# --- Directories -----------------------------------------------------------
ML_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ML_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"          # raw nflverse pulls
PROCESSED_DIR = DATA_DIR / "processed"  # normalized + featurized parquet


def ensure_data_dirs() -> None:
    """Create the (git-ignored) data directories. Called by pipeline steps
    that write there, not at import, so importing the package (e.g. from the
    API in a read-only container) has no side effects."""
    for d in (DATA_DIR, RAW_DIR, PROCESSED_DIR, MODELS_DIR):
        d.mkdir(parents=True, exist_ok=True)


# Pipeline artifact paths
PLAYS_PARQUET = PROCESSED_DIR / "plays.parquet"        # canonical schema
FEATURES_PARQUET = PROCESSED_DIR / "features.parquet"  # model-ready features
# The trained model is committed (ml/models/), so a fresh checkout or deploy
# can serve predictions without re-running the pipeline. It is stored as
# LightGBM text + JSON (no pickle), so loading it never executes code and does
# not depend on the exact scikit-learn/LightGBM version that trained it.
MODELS_DIR = ML_ROOT / "models"
MODEL_PATH = MODELS_DIR / "runpass.txt"        # LightGBM booster
MODEL_META_PATH = MODELS_DIR / "runpass.json"  # features, calibration, metrics

# --- Canonical Play schema -------------------------------------------------
# Every data source (nflverse, manual charting CSV) normalizes into these
# columns. Fields the source can't provide are left null; LightGBM handles
# missingness natively.
CANONICAL_COLUMNS = [
    "play_id", "game_id", "season", "week",
    "offense_team", "defense_team",
    "quarter", "game_seconds_remaining", "half",
    "down", "ydstogo", "yardline_100", "hash",
    "score_differential", "posteam_timeouts",
    "personnel", "formation", "backfield", "motion_type",
    "shotgun", "no_huddle",   # 1/0 pre-snap flags (chartable, model inputs)
    "play_type",          # run | pass. "pass" = a called dropback, so QB
                          # scrambles and sacks count as pass (the model target)
    "play_family", "pass_concept", "run_concept",
    "result_yards", "epa", "success", "explosive",
]

# --- Modeling constants ----------------------------------------------------
# Explosive play definition (yards gained), used in tendency tables: 12+ for
# runs, 16+ for passes.
EXPLOSIVE_RUN_YARDS = 12
EXPLOSIVE_PASS_YARDS = 16

# Seasons pulled by default. train.py holds out the newest as test, the one
# before it for calibration, and trains on the rest.
DEFAULT_SEASONS = [2019, 2020, 2021, 2022, 2023]

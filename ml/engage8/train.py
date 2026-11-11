"""Train the run/pass model with honest evaluation.

Key correctness choices:
  * Time-based split (train on older seasons, test on the newest), never a
    random split, which leaks future plays and inflates accuracy.
  * Probability calibration on a held-out season, so the reported "63% pass"
    actually means ~63% over many such situations.
  * Reports Brier score + log loss + ROC-AUC, not just accuracy.

Writes the model to ml/models/ (LightGBM text + JSON metadata). That directory
is committed so deploys serve predictions without re-running the pipeline.

Run:
    python -m engage8.train
"""
from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import (
    accuracy_score, brier_score_loss, log_loss, roc_auc_score,
)

from . import config
from .features import ALL_FEATURES, PRESNAP_FLAGS, TARGET

MODEL_VERSION = "0.2.0"

PARAMS = {
    "objective": "binary",
    "learning_rate": 0.03,
    "num_leaves": 63,
    "min_child_samples": 100,
    "bagging_fraction": 0.8,
    "bagging_freq": 1,
    "feature_fraction": 0.8,
    "lambda_l2": 1.0,
    "seed": 8,
    "verbose": -1,
}


# Share of train/calib rows where each pre-snap flag is blanked. NFL data
# always has them, but a coach often won't, and without this the model would
# read "unknown" as 0 (under center / huddle). Masking teaches it a real
# "unknown" branch that averages over both.
FLAG_MASK_RATE = 0.25


def _mask_flags(X: pd.DataFrame, seed: int) -> pd.DataFrame:
    X = X.copy()
    rng = np.random.default_rng(seed)
    for c in PRESNAP_FLAGS:
        X.loc[rng.random(len(X)) < FLAG_MASK_RATE, c] = np.nan
    return X


def _split_by_season(df: pd.DataFrame):
    """Return (train, calib, test) by season. Newest = test."""
    seasons = sorted(df["season"].dropna().unique())
    if len(seasons) < 3:
        raise SystemExit(
            "Need >=3 seasons for a clean train/calib/test split. "
            f"Got: {seasons}. Pull more seasons in `extract`."
        )
    test_season = seasons[-1]
    calib_season = seasons[-2]
    train = df[df["season"] <= seasons[-3]]
    calib = df[df["season"] == calib_season]
    test = df[df["season"] == test_season]
    print(
        f"Split  train: {sorted(int(s) for s in train['season'].unique())} ({len(train):,})  "
        f"calib: {calib_season} ({len(calib):,})  "
        f"test: {test_season} ({len(test):,})"
    )
    return train, calib, test


def _fit_lgbm(X_train, y_train, X_calib, y_calib):
    import lightgbm as lgb

    dtrain = lgb.Dataset(X_train, y_train)
    dvalid = lgb.Dataset(X_calib, y_calib, reference=dtrain)
    return lgb.train(
        PARAMS, dtrain, num_boost_round=600, valid_sets=[dvalid],
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )


def _evaluate(name, y_true, p_pred, baseline_rate=None) -> dict:
    y_hat = (p_pred >= 0.5).astype(int)
    metrics = {
        "n": int(len(y_true)),
        "accuracy": round(float(accuracy_score(y_true, y_hat)), 4),
        "brier": round(float(brier_score_loss(y_true, p_pred)), 4),
        "log_loss": round(float(log_loss(y_true, p_pred, labels=[0, 1])), 4),
        "roc_auc": round(float(roc_auc_score(y_true, p_pred)), 4),
    }
    if baseline_rate is not None:
        # Accuracy of always guessing the majority class.
        metrics["baseline_accuracy"] = round(float(max(baseline_rate, 1 - baseline_rate)), 4)
    print(f"  [{name}] " + "  ".join(f"{k}={v}" for k, v in metrics.items()))
    return metrics


def train_runpass(df: pd.DataFrame) -> dict:
    train, calib, test = _split_by_season(df)
    feats = list(ALL_FEATURES)

    X_train, y_train = _mask_flags(train[feats], 1), train[TARGET].astype(int)
    X_calib, y_calib = _mask_flags(calib[feats], 2), calib[TARGET].astype(int)
    X_test, y_test = test[feats], test[TARGET].astype(int)

    print("Training run/pass model ...")
    booster = _fit_lgbm(X_train, y_train, X_calib, y_calib)
    best = booster.best_iteration or booster.current_iteration()

    # Calibrate raw probabilities on the held-out calib season (isotonic).
    raw_calib = booster.predict(X_calib, num_iteration=best)
    calibrator = IsotonicRegression(out_of_bounds="clip")
    calibrator.fit(raw_calib, y_calib)

    # Evaluate on the untouched test season, raw vs calibrated.
    raw_test = booster.predict(X_test, num_iteration=best)
    cal_test = calibrator.predict(raw_test)

    test_rate = float(y_test.mean())
    print("Test-season performance:")
    raw_metrics = _evaluate("raw", y_test, raw_test, test_rate)
    cal_metrics = _evaluate("calibrated", y_test, cal_test, test_rate)

    # Same season with shotgun/no-huddle unknown (situation only).
    X_blank = X_test.copy()
    X_blank[PRESNAP_FLAGS] = np.nan
    blank_test = calibrator.predict(booster.predict(X_blank, num_iteration=best))
    blank_metrics = _evaluate("calibrated, flags unknown", y_test, blank_test, test_rate)

    gains = booster.feature_importance(importance_type="gain", iteration=best)
    importances = dict(sorted(
        ((f, round(float(g), 1)) for f, g in zip(feats, gains)),
        key=lambda kv: kv[1], reverse=True,
    ))

    report = {
        "test_season": int(test["season"].max()),
        "test_season_raw": raw_metrics,
        "test_season_calibrated": cal_metrics,
        "test_season_calibrated_flags_unknown": blank_metrics,
        "train_pass_rate": round(float(y_train.mean()), 4),
        "feature_importance_gain": importances,
        "n_trees": int(best),
    }

    config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
    booster.save_model(str(config.MODEL_PATH), num_iteration=best)
    meta = {
        "version": MODEL_VERSION,
        "trained_on": date.today().isoformat(),
        "target": "called dropback (1) vs designed run (0)",
        "features": feats,
        # Isotonic calibration as its breakpoints; predict = np.interp.
        "calibration": {
            "x": [round(float(v), 6) for v in calibrator.X_thresholds_],
            "y": [round(float(v), 6) for v in calibrator.y_thresholds_],
        },
        "metrics": report,
    }
    config.MODEL_META_PATH.write_text(json.dumps(meta, indent=2) + "\n")
    print(f"Saved model -> {config.MODEL_PATH}")
    print(f"Saved metadata + metrics -> {config.MODEL_META_PATH}")
    return report


def main() -> None:
    if not config.FEATURES_PARQUET.exists():
        raise SystemExit(
            f"{config.FEATURES_PARQUET} not found. Run `python -m engage8.features` first."
        )
    df = pd.read_parquet(config.FEATURES_PARQUET)
    train_runpass(df)


if __name__ == "__main__":
    main()

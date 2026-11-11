"""Predict run/pass for a single pre-snap situation.

Run:
    python -m engage8.predict --down 2 --distance 6 --yardline 38 \
        --quarter 2 --clock 252 --score-diff 3 --shotgun

Returns a calibrated pass probability + a plain-English "why". The model only
uses inputs it was trained on (situation + shotgun/no-huddle); team-specific
formation and motion tendencies are layered on top by the API from a team's
uploaded plays.
"""
from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

from . import config
from .features import _field_zone


class ModelNotFound(FileNotFoundError):
    pass


def load_model() -> dict:
    if not config.MODEL_PATH.exists() or not config.MODEL_META_PATH.exists():
        raise ModelNotFound(
            f"{config.MODEL_PATH} not found. Train first: python -m engage8.train"
        )
    import lightgbm as lgb

    meta = json.loads(config.MODEL_META_PATH.read_text())
    booster = lgb.Booster(model_file=str(config.MODEL_PATH))
    return {"booster": booster, **meta}


def default_clock(quarter: int) -> int:
    """game_seconds_remaining with 10:00 left in the given quarter."""
    if quarter >= 5:
        return 600
    return (4 - quarter) * 900 + 600


def _situation_row(features: list[str], **kw) -> pd.DataFrame:
    """Build a one-row feature frame from a pre-snap situation."""
    down = kw["down"]
    dist = kw["distance"]
    yard = kw["yardline_100"]
    quarter = kw.get("quarter")
    if quarter is None:
        quarter = 2
    clock = kw.get("game_seconds_remaining")
    if clock is None:
        clock = default_clock(quarter)
    score = kw.get("score_differential")
    timeouts = kw.get("posteam_timeouts")

    row = {
        "down": down, "ydstogo": dist, "yardline_100": yard,
        "quarter": quarter, "half": 1 if quarter <= 2 else 2,
        "game_seconds_remaining": clock,
        "score_differential": 0 if score is None else score,
        "posteam_timeouts": 3 if timeouts is None else timeouts,
        "is_goal_to_go": int(yard <= dist),
        "is_red_zone": int(yard <= 20),
        "is_two_minute": int(clock <= 120 or 1680 < clock <= 1800),
        "is_third_and_long": int(down == 3 and dist >= 7),
        "is_short_yardage": int(dist <= 2),
        "field_zone": int(_field_zone(pd.Series([yard])).iloc[0]),
        # Unknown -> missing; LightGBM routes NaN the way it learned to.
        "shotgun": kw.get("shotgun"),
        "no_huddle": kw.get("no_huddle"),
    }
    X = pd.DataFrame([{f: row.get(f) for f in features}])
    return X.apply(pd.to_numeric, errors="coerce").astype("float64")


def predict_proba(artifact: dict, situations: list[dict]) -> np.ndarray:
    """Calibrated pass probability for many situations in one model call.

    Each situation uses the same keys as ``predict_situation`` (down,
    distance, yardline_100, and optional quarter, clock, score, flags).
    Missing optional values fall back to the same defaults.
    """
    if not situations:
        return np.array([])
    X = pd.concat(
        [_situation_row(artifact["features"], **kw) for kw in situations],
        ignore_index=True,
    )
    raw = artifact["booster"].predict(X)
    cal = artifact["calibration"]
    return np.interp(raw, cal["x"], cal["y"])


def predict_situation(artifact: dict, **kw) -> dict:
    p_pass = float(predict_proba(artifact, [kw])[0])
    return summarize(p_pass, _explain(kw, p_pass))


def summarize(p_pass: float, why: str) -> dict:
    p_run = 1.0 - p_pass
    return {
        "pass_prob": round(p_pass, 3),
        "run_prob": round(p_run, 3),
        "lean": "PASS" if p_pass >= 0.5 else "RUN",
        "confidence": round(max(p_pass, p_run), 3),
        "why": why,
    }


def _explain(kw: dict, p_pass: float) -> str:
    down, dist = kw["down"], kw["distance"]
    bits = [f"{_ordinal(down)} & {dist}"]
    if kw["yardline_100"] <= 20:
        bits.append("red zone")
    if down == 3 and dist >= 7:
        bits.append("obvious passing down")
    if dist <= 2:
        bits.append("short yardage (run-leaning)")
    if kw.get("shotgun") == 1:
        bits.append("shotgun")
    elif kw.get("shotgun") == 0:
        bits.append("under center")
    if kw.get("no_huddle") == 1:
        bits.append("no huddle")
    lean = "pass" if p_pass >= 0.5 else "run"
    return f"{', '.join(bits)}: {int(round(max(p_pass, 1 - p_pass) * 100))}% {lean}."


def _ordinal(n: int) -> str:
    return {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}.get(n, f"{n}th")


def main() -> None:
    p = argparse.ArgumentParser(description="Predict run/pass for a situation.")
    p.add_argument("--down", type=int, required=True)
    p.add_argument("--distance", type=int, required=True)
    p.add_argument("--yardline", type=int, required=True,
                   help="Yards from opponent goal line (yardline_100)")
    p.add_argument("--quarter", type=int, default=2)
    p.add_argument("--clock", type=int, default=None,
                   help="game_seconds_remaining (3600=kickoff, 0=end); "
                        "default 10:00 left in --quarter")
    p.add_argument("--score-diff", type=int, default=0)
    g = p.add_mutually_exclusive_group()
    g.add_argument("--shotgun", dest="shotgun", action="store_const", const=1)
    g.add_argument("--under-center", dest="shotgun", action="store_const", const=0)
    p.add_argument("--no-huddle", dest="no_huddle", action="store_const", const=1)
    args = p.parse_args()

    try:
        artifact = load_model()
    except ModelNotFound as exc:
        raise SystemExit(str(exc)) from exc
    result = predict_situation(
        artifact,
        down=args.down, distance=args.distance, yardline_100=args.yardline,
        quarter=args.quarter, game_seconds_remaining=args.clock,
        score_differential=args.score_diff, shotgun=args.shotgun,
        no_huddle=args.no_huddle,
    )
    print(f"\n  Pass: {result['pass_prob']:.0%}   Run: {result['run_prob']:.0%}")
    print(f"  Lean: {result['lean']}  (confidence {result['confidence']:.0%})")
    print(f"  Why:  {result['why']}\n")


if __name__ == "__main__":
    main()

"""Run/pass prediction service.

Loads the committed model from ``ml/models`` once per process and scores
situations with it. When the caller names an opponent in one of their teams,
the league prediction is blended with that opponent's uploaded plays (see
``services/blend.py``).
"""
from __future__ import annotations

from functools import lru_cache

from fastapi import HTTPException, status

import app.ml  # noqa: F401  (puts engage8 on sys.path)
from engage8.predict import (  # noqa: E402
    ModelNotFound, load_model, predict_proba, predict_situation,
)

# Request fields forwarded to the model. Formation/motion/team are not model
# inputs; they only select which uploaded plays the blend uses.
MODEL_INPUTS = (
    "down",
    "distance",
    "yardline_100",
    "quarter",
    "game_seconds_remaining",
    "score_differential",
    "posteam_timeouts",
    "shotgun",
    "no_huddle",
)


@lru_cache(maxsize=1)
def get_artifact() -> dict:
    """Load the trained model once. A missing model becomes a clean 503."""
    try:
        return load_model()
    except ModelNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not found; run the ml pipeline (python -m engage8.train).",
        ) from exc


def model_kwargs(game_state: dict) -> dict:
    kw = {k: game_state[k] for k in MODEL_INPUTS if game_state.get(k) is not None}
    for flag in ("shotgun", "no_huddle"):
        if flag in kw:
            kw[flag] = int(kw[flag])
    return kw


def predict(game_state: dict) -> dict:
    """League-model prediction: pass_prob, run_prob, lean, confidence, why."""
    return predict_situation(get_artifact(), **model_kwargs(game_state))


def predict_many(situations: list[dict]):
    """Calibrated pass probabilities for many situations (numpy array)."""
    return predict_proba(get_artifact(), situations)

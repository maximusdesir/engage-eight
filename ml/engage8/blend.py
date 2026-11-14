"""Opponent blend: shift the league model toward one opponent's own plays.

The math only, no database, so the API (``api/app/services/blend.py``) and the
backtest (``engage8.backtest``) run the same code.

The caller passes nested levels of the opponent's plays, broadest first (all
plays, then the same down & distance bucket, then the same formation, ...).
At each level we compare what the opponent actually did with what the model
(plus the levels above) expected on those same plays, as a log-odds offset,
and shrink it by n / (n + prior_plays). So a level only adds what the level
above didn't already explain, a handful of plays only nudges the prediction,
and a big sample can move it a long way.
"""
from __future__ import annotations

import math

import numpy as np

# How many plays the prior (model + levels above) is worth at each level.
# Picked by the 2023 NFL backtest (python -m engage8.backtest): 80 had the
# lowest log loss with 9 weeks of film and never hurt with 1 to 4 weeks, where
# the old guess of 20 did. NFL offenses sit close to the league model; a high
# school offense may stray further, which would favor a smaller prior.
PRIOR_PLAYS = 80.0


def logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def level_offsets(
    y: np.ndarray,
    base_logit: np.ndarray,
    masks: list[np.ndarray],
    prior_plays: float = PRIOR_PLAYS,
) -> list[tuple[int, int, float]]:
    """Walk the levels and return (level index, plays, offset so far) for each
    level that was applied.

    y: 1.0 for pass, 0.0 for run, one entry per opponent play.
    base_logit: the model's log-odds of pass for each of those plays.
    masks: one boolean array per level, each a subset of the one before.

    Add the last offset to the model's log-odds for the situation being
    predicted. A level with no plays stops the walk; a level with the same
    plays as the one above is skipped, so the same evidence never counts twice.
    """
    offset = 0.0
    applied: list[tuple[int, int, float]] = []
    prev_n = None
    for i, m in enumerate(masks):
        n = int(m.sum())
        if n == 0:
            break
        if n == prev_n:
            continue
        prev_n = n
        k = float(y[m].sum())
        expected = float(sigmoid(base_logit[m] + offset).sum())
        observed_lo = math.log((k + 0.5) / (n - k + 0.5))
        expected_lo = math.log((expected + 0.5) / (n - expected + 0.5))
        offset += (n / (n + prior_plays)) * (observed_lo - expected_lo)
        applied.append((i, n, offset))
    return applied

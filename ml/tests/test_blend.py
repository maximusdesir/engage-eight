"""Opponent blend math and its backtest, on synthetic plays (no NFL data needed).

    cd ml && python -m pytest tests/test_blend.py
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from engage8 import backtest as bt
from engage8.blend import level_offsets, logit, sigmoid


def test_one_level_matches_the_formula():
    # 30 plays, 24 passes, model says 50/50 on each.
    y = np.array([1.0] * 24 + [0.0] * 6)
    base = np.zeros(30)
    [(i, n, offset)] = level_offsets(y, base, [np.ones(30, dtype=bool)], prior_plays=10)
    observed = math.log(24.5 / 6.5)
    expected = math.log(15.5 / 15.5)
    assert (i, n) == (0, 30)
    assert math.isclose(offset, 30 / 40 * (observed - expected))


def test_a_huge_prior_leaves_the_model_alone():
    y = np.ones(50)
    [(_, _, offset)] = level_offsets(y, np.zeros(50), [np.ones(50, dtype=bool)],
                                     prior_plays=float("inf"))
    assert offset == 0.0


def test_more_plays_pull_harder():
    def offset_for(n):
        return level_offsets(np.ones(n), np.zeros(n), [np.ones(n, dtype=bool)], 20)[-1][2]
    assert 0 < offset_for(5) < offset_for(50) < offset_for(500)


def test_repeated_level_is_skipped_and_empty_level_stops():
    y = np.array([1.0, 1.0, 0.0, 1.0])
    everything = np.ones(4, dtype=bool)
    nothing = np.zeros(4, dtype=bool)
    applied = level_offsets(y, np.zeros(4), [everything, everything.copy(), nothing, everything])
    assert [(i, n) for i, n, _ in applied] == [(0, 4)]


def test_logit_and_sigmoid_round_trip():
    for p in (0.1, 0.5, 0.9):
        assert math.isclose(float(sigmoid(logit(p))), p)
    assert logit(0.0) < 0 < logit(1.0)  # clamped, not infinite


def _season(seed: int = 8) -> pd.DataFrame:
    """Two teams over 18 weeks. The model says 50% pass on every play; PASS
    really passes 80% of the time, EVEN really is 50/50."""
    rng = np.random.default_rng(seed)
    rows = []
    for team, rate in (("PASS", 0.8), ("EVEN", 0.5)):
        for week in range(1, 19):
            for _ in range(40):
                rows.append({"offense_team": team, "week": week,
                             "bucket": rng.choice(["1st & 10", "3rd & long"]),
                             "is_pass": float(rng.random() < rate), "model_p": 0.5})
    return pd.DataFrame(rows)


def test_split_uses_weeks_before_10_as_film():
    df = _season()
    film, test = bt.split(df)
    assert film["week"].between(1, 9).all() and test["week"].between(10, 18).all()
    film2, _ = bt.split(df, film_weeks=2)
    assert set(film2["week"]) == {8, 9}


def test_backtest_rewards_a_team_that_strays_from_the_model():
    film, test = bt.split(_season())
    res = bt.sweep(film, test, priors=[20, 80, float("inf")]).set_index("prior")
    assert math.isclose(res.loc[float("inf"), "log_loss"], math.log(2), rel_tol=1e-6)
    assert res.loc[80, "log_loss"] < res.loc[float("inf"), "log_loss"]
    gains = bt.per_team_gain(film, test, 80)
    assert gains["PASS"] > 0.05 > abs(gains["EVEN"])
    lo, hi = bt.bootstrap_gain(film, test, 80, draws=200)
    assert lo <= hi

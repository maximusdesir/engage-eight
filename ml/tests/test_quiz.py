"""Quiz export: the committed JSON is well formed, and the sampler is stratified.

    cd ml && python -m pytest tests/test_quiz.py
"""
from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pandas as pd

from engage8 import config
from engage8.predict import load_model
from engage8.quiz import DEFAULT_OUT, QUOTAS, build_quiz, sample_plays

QUIZ_FIELDS = {
    "id", "week", "offense", "defense", "down", "distance", "yardline_100",
    "quarter", "clock", "score_diff", "timeouts", "shotgun", "no_huddle",
    "actual", "desc", "model_pass_prob",
}


def test_committed_quiz_file_loads():
    data = json.loads(DEFAULT_OUT.read_text())
    assert data["season"] == 2023
    plays = data["plays"]
    assert len(plays) == sum(QUOTAS.values())
    assert len({p["id"] for p in plays}) == len(plays)
    assert Counter(p["down"] for p in plays) == QUOTAS
    for p in plays:
        assert set(p) == QUIZ_FIELDS
        assert 0.0 <= p["model_pass_prob"] <= 1.0
        assert p["actual"] in ("run", "pass")
        assert p["desc"]


def _fake_pbp(n: int = 600, seed: int = 8) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "game_id": [f"2023_{i % 17 + 1:02d}_AAA_BBB" for i in range(n)],
        "play_id": np.arange(n, dtype=float),
        "week": [i % 17 + 1 for i in range(n)],
        "posteam": "AAA", "defteam": "BBB",
        "play_type": rng.choice(["run", "pass", "punt", "no_play"], n),
        "qb_dropback": rng.choice([0.0, 1.0], n),
        "down": rng.choice([1.0, 2.0, 3.0, 4.0, np.nan], n),
        "ydstogo": rng.integers(1, 15, n).astype(float),
        "yardline_100": rng.integers(1, 99, n).astype(float),
        "qtr": rng.integers(1, 5, n),
        "game_seconds_remaining": rng.integers(0, 3600, n).astype(float),
        "score_differential": rng.integers(-14, 14, n).astype(float),
        "posteam_timeouts_remaining": rng.integers(0, 4, n).astype(float),
        "shotgun": rng.choice([0.0, 1.0], n),
        "no_huddle": rng.choice([0.0, 1.0], n),
        "desc": "a play",
    })


def test_sampler_is_seeded_and_stratified():
    pbp = _fake_pbp()
    quotas = {1: 20, 2: 20, 3: 10, 4: 5}
    a = sample_plays(pbp, quotas, seed=8)
    b = sample_plays(pbp, quotas, seed=8)
    assert Counter(a["down"].astype(int)) == quotas
    assert a["play_id"].tolist() == b["play_id"].tolist()
    assert a["play_type"].isin(["run", "pass"]).all()   # punts/no_play excluded


def test_build_quiz_probs_in_unit_interval():
    if not config.MODEL_PATH.exists():
        return  # fresh checkout without the model is covered by other tests
    rows = build_quiz(_fake_pbp(), load_model(), {1: 20, 2: 20, 3: 10, 4: 5}, seed=8)
    assert len(rows) == 55
    assert all(0.0 <= r["model_pass_prob"] <= 1.0 for r in rows)

"""The fictional Central HS demo CSV: reproducible, loads cleanly, tendencies hold.

    cd ml && python -m pytest tests/test_demo_opponent.py
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from engage8 import vocab
from engage8.hudl import load_hudl, looks_like_hudl

ROOT = Path(__file__).resolve().parents[2]
DEMO_CSV = ROOT / "api" / "demo" / "central_hs.csv"
SCRIPT = ROOT / "ml" / "scripts" / "make_sample_opponent.py"


def _generator():
    spec = importlib.util.spec_from_file_location("make_sample_opponent", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_committed_csv_matches_the_generator(tmp_path):
    gen = _generator()
    out = tmp_path / "again.csv"
    gen.write_csv(gen.generate(gen.SEED), out)
    assert out.read_bytes() == DEMO_CSV.read_bytes()


@pytest.fixture(scope="module")
def plays():
    df = load_hudl(DEMO_CSV)
    df["formation_c"] = df["formation"].map(vocab.normalize_formation)
    df["motion_c"] = df["motion_type"].map(vocab.normalize_motion)
    df["is_pass"] = df["play_type"] == "pass"
    return df


def test_demo_csv_loads_as_hudl_without_losing_plays(plays):
    assert looks_like_hudl(DEMO_CSV)
    assert len(plays) == 250                      # kicking rows are filtered out
    assert plays.attrs["skipped"] == {"no_down": 0, "unknown_run_pass": 0}
    assert plays["offense_team"].eq("Central HS (fictional)").all()
    assert plays["formation_c"].isin(vocab.CANONICAL_FORMATIONS).all()


def test_demo_tendencies_are_the_ones_we_wrote_in(plays):
    i_form = plays[plays["formation_c"] == "I-FORM"]["is_pass"]
    empty = plays[plays["formation_c"] == "EMPTY"]["is_pass"]
    jet = plays[plays["motion_c"] == "JET"]["is_pass"]
    assert len(i_form) >= 25 and len(empty) >= 25 and len(jet) >= 25
    assert (1 - i_form.mean()) >= 0.60            # runs from I-Form
    assert empty.mean() >= 0.85                   # passes from Empty
    assert (1 - jet.mean()) >= 0.80               # jet motion means run
    third_long = plays[(plays["down"] == 3) & (plays["ydstogo"] >= 7)]["is_pass"]
    assert third_long.mean() >= 0.7

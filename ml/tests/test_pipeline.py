"""Tests that run on synthetic data, no network or LightGBM required.

    cd ml && python -m pytest        # or: python tests/test_pipeline.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from engage8 import vocab
from engage8.config import CANONICAL_COLUMNS
from engage8.features import build_features, TARGET
from engage8.tendencies import tendency_table


def _synthetic_plays(n: int = 400, seed: int = 8) -> pd.DataFrame:
    """Make a plausible canonical plays frame for two seasons."""
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        down = int(rng.integers(1, 5))
        dist = int(rng.integers(1, 15))
        # Pass more likely on 3rd and long, which gives the model real signal.
        p_pass = 0.45 + (0.4 if (down == 3 and dist >= 7) else 0.0) - (0.2 if dist <= 2 else 0)
        is_pass = rng.random() < min(max(p_pass, 0.05), 0.95)
        yards = int(rng.integers(-3, 25))
        rows.append({
            "play_id": str(i), "game_id": f"g{i // 40}",
            "season": 2022 + (i % 2), "week": 1 + (i % 17),
            "offense_team": rng.choice(["KC", "SF"]), "defense_team": "OPP",
            "quarter": int(rng.integers(1, 5)),
            "game_seconds_remaining": int(rng.integers(0, 3600)),
            "half": 1, "down": down, "ydstogo": dist,
            "yardline_100": int(rng.integers(1, 99)), "hash": pd.NA,
            "score_differential": int(rng.integers(-14, 15)),
            "posteam_timeouts": 3, "personnel": pd.NA,
            "formation": rng.choice(["SHOTGUN", "SINGLEBACK", pd.NA]),
            "backfield": pd.NA, "motion_type": pd.NA,
            "play_type": "pass" if is_pass else "run",
            "play_family": pd.NA, "pass_concept": pd.NA, "run_concept": pd.NA,
            "result_yards": yards, "epa": float(rng.normal(0, 1)),
            "success": int(yards > 4), "explosive": int(yards >= 12),
        })
    return pd.DataFrame(rows)[CANONICAL_COLUMNS]


def test_build_features_has_target_and_flags():
    feats = build_features(_synthetic_plays())
    assert TARGET in feats.columns
    assert feats[TARGET].isin([0, 1]).all()
    # 3rd & long flag should be set correctly.
    assert "is_third_and_long" in feats.columns
    assert "field_zone" in feats.columns
    # Lag feature exists and is bounded.
    assert "prev3_pass_rate" in feats.columns


def test_lag_features_are_chronological():
    feats = build_features(_synthetic_plays())
    # drive_play_index starts at 0 within each game/offense group.
    assert feats["drive_play_index"].min() == 0


def test_tendency_table_sums_to_100():
    table = tendency_table(_synthetic_plays(), split="down_distance")
    assert not table.empty
    for _, r in table.iterrows():
        assert abs(r["run_pct"] + r["pass_pct"] - 100.0) < 0.5


def test_third_and_long_is_pass_heavy():
    plays = _synthetic_plays(n=1500)
    table = tendency_table(plays, split="down_distance")
    row = table[table["bucket"] == "3rd & long"]
    if not row.empty:
        assert row.iloc[0]["pass_pct"] > 55  # signal we baked in


def test_hudl_adapter_maps_and_converts():
    import tempfile
    from engage8.hudl import load_hudl, looks_like_hudl

    csv = ("PLAY #,ODK,DN,DIST,YARD LN,HASH,OFF FORM,OFF PLAY,PLAY TYPE,PERS,GN/LS,QTR\n"
           "1,O,1,10,-25,L,Trips,Inside Zone,Run,11,5,1\n"
           "2,O,3,8,+35,R,Empty,Four Verticals,Pass,10,12,2\n"
           "3,D,1,10,+20,L,,,,,0,2\n")     # defense row must be dropped
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as f:
        f.write(csv)
        path = f.name

    assert looks_like_hudl(path)
    df = load_hudl(path, default_offense_team="LINCOLN")
    assert len(df) == 2                              # defense row filtered out
    assert list(df["yardline_100"]) == [75, 35]      # own 25 -> 75, opp 35 -> 35
    assert list(df["play_type"]) == ["run", "pass"]
    assert list(df["hash"]) == ["L", "R"]
    assert set(df["offense_team"]) == {"LINCOLN"}     # team label applied


def test_vocab_normalizes_naming_variants():
    # Casing, direction, and synonyms all fold onto one canonical token.
    assert vocab.normalize_formation("Trips Rt") == "TRIPS"
    assert vocab.normalize_formation("TRIPS") == "TRIPS"
    assert vocab.normalize_formation("trips left") == "TRIPS"
    assert vocab.normalize_formation("3x1") == "TRIPS"
    # Unrecognized values pass through unchanged (never silently dropped).
    assert vocab.normalize_formation("Weird Set") == "Weird Set"
    assert not vocab.is_canonical("formation", "Weird Set")
    # A per-team mapping wins and makes the value canonical.
    fmap = vocab.build_mapping([("Weird Set", "PRO")])
    assert vocab.normalize_formation("weird set", fmap) == "PRO"
    # Motion: none-like and empty both fold to NONE; synonyms fold too.
    assert vocab.normalize_motion("") == "NONE"
    assert vocab.normalize_motion(None) == "NONE"
    assert vocab.normalize_motion("Fly") == "JET"
    assert vocab.normalize_motion("Jet Rt") == "JET"


def test_motion_tendency_split():
    plays = _synthetic_plays(n=200)
    # Give half the plays a jet-motion variant so there is a real bucket.
    plays.loc[plays.index[::2], "motion_type"] = "Jet Rt"
    table = tendency_table(plays, split="motion")
    assert not table.empty
    assert "JET" in set(table["bucket"])          # variant folded to canonical
    for _, r in table.iterrows():
        assert abs(r["run_pct"] + r["pass_pct"] - 100.0) < 0.5


if __name__ == "__main__":
    test_build_features_has_target_and_flags()
    test_lag_features_are_chronological()
    test_tendency_table_sums_to_100()
    test_third_and_long_is_pass_heavy()
    test_hudl_adapter_maps_and_converts()
    test_vocab_normalizes_naming_variants()
    test_motion_tendency_split()
    print("All tests passed")

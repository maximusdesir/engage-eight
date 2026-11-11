"""Pipeline tests on synthetic data and small CSV fixtures (no network).

    cd ml && python -m pytest
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from engage8 import vocab
from engage8.charting import load_charting
from engage8.config import CANONICAL_COLUMNS
from engage8.features import ALL_FEATURES, TARGET, build_features
from engage8.hudl import load_hudl, looks_like_hudl
from engage8.parsing import parse_play_type, parse_shotgun
from engage8.tendencies import tendency_table

FIXTURES = Path(__file__).parent / "fixtures"


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
            "shotgun": int(rng.integers(0, 2)), "no_huddle": 0,
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
    # Every model feature is present and numeric (no categoricals to drift).
    for f in ALL_FEATURES:
        assert f in feats.columns
        assert feats[f].dtype == "float64"
    # Inputs the public data can't supply are not model features.
    for f in ("offense_team", "formation", "personnel", "motion_type", "hash"):
        assert f not in ALL_FEATURES


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


def _write(tmp_path, text, name="f.csv"):
    path = tmp_path / name
    path.write_text(text)
    return str(path)


def test_hudl_adapter_maps_and_converts(tmp_path):
    path = _write(tmp_path,
        "PLAY #,ODK,DN,DIST,YARD LN,HASH,OFF FORM,OFF PLAY,PLAY TYPE,PERS,GN/LS,QTR\n"
        "1,O,1,10,-25,L,Trips,Inside Zone,Run,11,5,1\n"
        "2,O,3,8,+35,R,Empty,Four Verticals,Pass,10,12,2\n"
        "3,D,1,10,+20,L,,,,,0,2\n")     # defense row must be dropped
    assert looks_like_hudl(path)
    df = load_hudl(path, default_offense_team="LINCOLN")
    assert len(df) == 2                              # defense row filtered out
    assert list(df["yardline_100"]) == [75, 35]      # own 25 -> 75, opp 35 -> 35
    assert list(df["play_type"]) == ["run", "pass"]
    assert list(df["hash"]) == ["L", "R"]
    assert set(df["offense_team"]) == {"LINCOLN"}     # team label applied


def test_hudl_blank_quarter_does_not_crash(tmp_path):
    # Regression: a blank QTR cell used to raise "boolean value of NA is
    # ambiguous" from np.where on a nullable comparison.
    path = _write(tmp_path,
        "ODK,QTR,DN,DIST,YARD LN,PLAY TYPE,GN/LS\n"
        "O,,1,10,-25,Run,\n"
        "O,3,2,7,-30,Pass,8\n")
    df = load_hudl(path)
    assert len(df) == 2
    assert df["half"].isna().iloc[0] and df["half"].iloc[1] == 2
    # Unknown yards -> explosive unknown, not "not explosive".
    assert df["explosive"].isna().iloc[0] and df["explosive"].iloc[1] == 0


def test_hudl_standard_export_fixture():
    path = FIXTURES / "hudl_standard_export.csv"   # BOM, blank QTRs, kicks
    assert looks_like_hudl(path)
    df = load_hudl(path, default_offense_team="CENTRAL")
    assert len(df) == 9                       # O rows minus the extra point
    assert list(df["play_type"]) == [
        "run", "pass", "run", "pass", "pass", "pass", "run", "run", "run"]
    assert df["half"].isna().sum() == 2       # the two blank-QTR plays
    assert list(df["shotgun"].astype("object").where(df["shotgun"].notna(), None)) == [
        1, 1, 0, None, 1, 1, 1, 0, 0]          # Gun/Pistol=1, UC=0, blank=None
    assert df.attrs["skipped"]["unknown_run_pass"] == 1
    assert df["yardline_100"].iloc[0] == 75


def test_hudl_without_play_type_column_reports_unresolved():
    df = load_hudl(FIXTURES / "hudl_no_play_type.csv")
    # Mesh / Smash resolve to pass from the name, Iso / Inside Zone to run.
    assert list(df["play_type"]) == ["run", "pass", "run", "pass"]
    # Ambiguous names are skipped and reported, not silently lost.
    assert df.attrs["skipped"]["unknown_run_pass"] == 2
    assert df.attrs["unresolved_play_names"] == ["Black 23", "RPO Glance"]
    assert list(df["no_huddle"]) == [0, 1, 0, 0]
    assert list(df["shotgun"].fillna(-1)) == [1, 1, -1, 1]


def test_charting_tolerates_blanks_and_case(tmp_path):
    path = _write(tmp_path,
        "offense_team,quarter,down,ydstogo,yardline_100,play_type,result_yards,formation\n"
        "CENTRAL,,1,10,75,Run,5,Gun Trips\n"
        "CENTRAL,2,3,8,40,PASS,,\n"
        "CENTRAL,2,2,4,30,punt,0,\n")
    df = load_charting(path)
    assert list(df["play_type"]) == ["run", "pass"]
    assert df["half"].isna().iloc[0]
    assert df["explosive"].isna().iloc[1]
    assert df["shotgun"].iloc[0] == 1
    assert df.attrs["skipped"]["unknown_run_pass"] == 1


@pytest.mark.parametrize("raw,name,expected", [
    ("Run", None, "run"), ("P", None, "pass"), (None, "Mesh", "pass"),
    (None, "Inside Zone", "run"), (None, "PA Power", "pass"),
    (None, "RB Screen", "pass"), (None, "QB Sneak", "run"),
    (None, "Four Verts", "pass"), (None, "Jet Sweep", "run"),
    (None, "RPO Glance", None), (None, "Black 23", None), (None, None, None),
    ("", "Counter", "run"),
])
def test_parse_play_type(raw, name, expected):
    got = parse_play_type(raw, name)
    assert (got is pd.NA and expected is None) or got == expected


def test_parse_shotgun():
    assert parse_shotgun("Gun Trips Rt") == 1
    assert parse_shotgun(None, "Pistol") == 1
    assert parse_shotgun("UC") == 0
    assert parse_shotgun("Under Center") == 0
    assert parse_shotgun("Trips") is pd.NA


def test_committed_model_loads_and_is_sane():
    pytest.importorskip("lightgbm")
    from engage8.predict import load_model, predict_situation

    model = load_model()
    assert model["features"] == ALL_FEATURES
    long_gun = predict_situation(model, down=3, distance=8, yardline_100=45, shotgun=1)
    short_uc = predict_situation(model, down=3, distance=1, yardline_100=2, shotgun=0)
    assert long_gun["pass_prob"] > 0.8 and long_gun["lean"] == "PASS"
    assert short_uc["run_prob"] > 0.6 and short_uc["lean"] == "RUN"
    # Unknown shotgun sits between the two known values, not on one of them.
    known = [predict_situation(model, down=1, distance=10, yardline_100=75, shotgun=v)
             ["pass_prob"] for v in (0, 1)]
    unknown = predict_situation(model, down=1, distance=10, yardline_100=75)["pass_prob"]
    assert min(known) < unknown < max(known)


def test_vocab_normalizes_naming_variants():
    # Casing, direction, and synonyms all fold onto one canonical token.
    assert vocab.normalize_formation("Trips Rt") == "TRIPS"
    assert vocab.normalize_formation("TRIPS") == "TRIPS"
    assert vocab.normalize_formation("trips left") == "TRIPS"
    assert vocab.normalize_formation("3x1") == "TRIPS"
    assert vocab.normalize_formation("Gun Trips Rt") == "TRIPS"
    assert vocab.normalize_formation("Gun") == "SHOTGUN"
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

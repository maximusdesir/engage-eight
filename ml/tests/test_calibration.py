"""Calibration table and chart, on synthetic predictions (no NFL data needed).

    cd ml && python -m pytest tests/test_calibration.py
"""
from __future__ import annotations

import numpy as np

from engage8.calibration import average_gap, calibration_table, plot


def _calibrated(n: int = 50_000, seed: int = 8):
    rng = np.random.default_rng(seed)
    p = rng.random(n)
    return (rng.random(n) < p).astype(int), p


def test_a_calibrated_model_sits_on_the_diagonal():
    y, p = _calibrated()
    table = calibration_table(y, p)
    assert len(table) == 10 and table["plays"].sum() == len(y)
    assert ((table["predicted"] - table["actual"]).abs() < 0.02).all()
    assert average_gap(table) < 0.01


def test_an_overconfident_model_shows_a_gap():
    y, p = _calibrated()
    pushed = np.clip(0.5 + (p - 0.5) * 1.6, 0, 1)  # more extreme than the truth
    assert average_gap(calibration_table(y, pushed)) > 0.05


def test_edges_land_in_the_end_bins():
    table = calibration_table(np.array([0, 1, 1]), np.array([0.0, 1.0, 0.1]))
    assert table["lo"].tolist() == [0.0, 0.9]
    assert table["plays"].tolist() == [2, 1]


def test_chart_renders_in_both_modes(tmp_path):
    y, p = _calibrated(5_000)
    table = calibration_table(y, p)
    for mode in ("light", "dark"):
        out = tmp_path / f"{mode}.png"
        plot(table, len(y), out, mode)
        assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

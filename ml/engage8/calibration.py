"""Calibration chart: the model's pass probability vs how often teams passed.

Scores every 2023 play (the held-out test season), groups them into 10-point
bins of predicted pass probability, and compares each bin's average
prediction with its actual pass rate. A calibrated model sits on the diagonal.
Writes a light and a dark PNG for the README.

Run (needs data/processed from the pipeline):
    python -m engage8.calibration
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config
from .predict import load_model, predict_frame

SEASON = 2023
BINS = 10
DOCS = config.ML_ROOT.parent / "docs"
OUT = {"light": DOCS / "calibration.png", "dark": DOCS / "calibration-dark.png"}

# Colors from the data-viz reference palette: series slot 1 (blue), text
# tokens, and recessive grid/bars, stepped separately for each mode.
THEMES = {
    "light": {"surface": "#fcfcfb", "text": "#0b0b0b", "muted": "#52514e",
              "grid": "#e4e3df", "bars": "#c9c8c2", "series": "#2a78d6"},
    "dark": {"surface": "#1a1a19", "text": "#f0efec", "muted": "#c3c2b7",
             "grid": "#30302e", "bars": "#55544f", "series": "#3987e5"},
}


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = BINS) -> pd.DataFrame:
    """One row per probability bin: plays, mean prediction, actual pass rate."""
    edges = np.linspace(0, 1, bins + 1)
    idx = np.clip(np.digitize(p, edges[1:-1], right=True), 0, bins - 1)
    df = pd.DataFrame({"bin": idx, "p": p, "y": y})
    out = df.groupby("bin").agg(plays=("y", "size"), predicted=("p", "mean"), actual=("y", "mean"))
    out["lo"] = edges[out.index]
    out["hi"] = edges[out.index + 1]
    return out.reset_index(drop=True)[["lo", "hi", "plays", "predicted", "actual"]]


def average_gap(table: pd.DataFrame) -> float:
    """Play-weighted mean |predicted - actual| (expected calibration error)."""
    gap = (table["predicted"] - table["actual"]).abs()
    return float((gap * table["plays"]).sum() / table["plays"].sum())


def load_test_season(season: int = SEASON) -> tuple[np.ndarray, np.ndarray]:
    feats = pd.read_parquet(config.FEATURES_PARQUET)
    test = feats[feats["season"] == season]
    return test["is_pass"].astype(int).to_numpy(), predict_frame(load_model(), test)


def plot(table: pd.DataFrame, n_plays: int, out: Path, mode: str = "light") -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.ticker import FuncFormatter, PercentFormatter

    c = THEMES[mode]
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 9,
        "axes.edgecolor": c["grid"], "axes.labelcolor": c["muted"],
        "xtick.color": c["muted"], "ytick.color": c["muted"],
        "xtick.major.size": 0, "ytick.major.size": 0,
    })
    fig = plt.figure(figsize=(8, 6.4), dpi=200, facecolor=c["surface"])
    grid = fig.add_gridspec(2, 1, height_ratios=[3.2, 1], hspace=0.08,
                            left=0.1, right=0.97, top=0.82, bottom=0.1)
    top = fig.add_subplot(grid[0])
    bottom = fig.add_subplot(grid[1], sharex=top)

    for ax in (top, bottom):
        ax.set_facecolor(c["surface"])
        ax.grid(True, color=c["grid"], linewidth=0.6)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)

    pct = PercentFormatter(1.0, decimals=0)
    top.plot([0, 1], [0, 1], linestyle=(0, (4, 3)), linewidth=1, color=c["muted"])
    top.plot(table["predicted"], table["actual"], color=c["series"], linewidth=1.6,
             marker="o", markersize=6.5, markeredgecolor=c["surface"], markeredgewidth=1.2,
             zorder=3)
    top.set(xlim=(0, 1), ylim=(0, 1))
    top.xaxis.set_major_formatter(pct)
    top.yaxis.set_major_formatter(pct)
    top.set_xticks(np.linspace(0, 1, 6))
    top.set_yticks(np.linspace(0, 1, 6))
    top.tick_params(labelbottom=False)
    top.set_ylabel("Teams actually passed")
    # rotation=45 in data space, so the label runs along the diagonal at any
    # aspect ratio.
    top.text(0.88, 0.835, "perfect calibration", color=c["muted"], fontsize=8.5,
             rotation=45, transform_rotates_text=True, rotation_mode="anchor",
             ha="center", va="top")

    # One direct label, on the bin the README quotes.
    row = table.iloc[(table["predicted"] - 0.75).abs().argmin()]
    top.annotate(f"Model said {row['predicted']:.0%} pass\nteams passed {row['actual']:.1%}",
                 xy=(row["predicted"], row["actual"]), xytext=(-14, 22),
                 textcoords="offset points", ha="right", va="bottom",
                 color=c["text"], fontsize=8.5,
                 arrowprops={"arrowstyle": "-", "color": c["muted"], "linewidth": 0.8})

    width = (table["hi"] - table["lo"]).to_numpy() * 0.92
    bottom.bar((table["lo"] + table["hi"]) / 2, table["plays"], width=width,
               color=c["bars"], linewidth=0)
    bottom.set_xlabel("Model's pass probability")
    bottom.set_ylabel("Plays")
    bottom.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v / 1000:g}k" if v else "0"))
    bottom.set_yticks(np.linspace(0, np.ceil(table["plays"].max() / 2000) * 2000, 3))

    fig.text(0.1, 0.93, "When the model says X% pass, teams pass about X% of the time",
             color=c["text"], fontsize=12, fontweight="bold")
    fig.text(0.1, 0.885,
             f"{n_plays:,} plays from the {SEASON} season, which the model never trained on. "
             f"Average gap: {average_gap(table):.1%}.",
             color=c["muted"], fontsize=9)
    fig.text(0.1, 0.855, "Each dot is a 10-point bin of predictions. Bars show how many "
             "plays fall in each bin.", color=c["muted"], fontsize=9)
    fig.text(0.97, 0.02, "Data: nflverse", color=c["muted"], fontsize=7.5, ha="right")

    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, facecolor=c["surface"])
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description="Calibration chart for the run/pass model.")
    ap.add_argument("--season", type=int, default=SEASON)
    args = ap.parse_args()

    y, p = load_test_season(args.season)
    table = calibration_table(y, p)
    print(table.to_string(index=False, formatters={
        "lo": "{:.0%}".format, "hi": "{:.0%}".format,
        "predicted": "{:.1%}".format, "actual": "{:.1%}".format}))
    print(f"\n{len(y):,} plays, average gap {average_gap(table):.2%}")
    for mode, path in OUT.items():
        plot(table, len(y), path, mode)
        print(f"wrote {path.relative_to(config.ML_ROOT.parent)}")


if __name__ == "__main__":
    main()

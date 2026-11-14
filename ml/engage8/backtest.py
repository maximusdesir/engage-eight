"""Backtest the opponent blend on the 2023 NFL season.

For each team, its weeks 1-9 plays are the "uploaded film" and its weeks 10-18
plays are the ones we predict, first with the league model alone and then with
the model plus the blend (``engage8.blend``) at several prior strengths. All
32 teams are pooled and compared by log loss. 2023 is the held-out test
season, so the model never trained on any of these plays.

NFL play-by-play has no formation or motion, so this exercises the first two
blend levels: all of the team's plays, then its plays in the same down &
distance bucket.

Run (needs data/processed from the pipeline: extract, then features):
    python -m engage8.backtest
"""
from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from . import config
from .blend import PRIOR_PLAYS, level_offsets
from .predict import load_model
from .tendencies import _dd_bucket

SEASON = 2023
LAST_FILM_WEEK = 9
LAST_REGULAR_WEEK = 18
# Prior strengths to try, in plays. inf = no blend (the league model alone).
PRIORS = [0, 5, 10, 20, 40, 80, 160, 320, 640, float("inf")]
# Weeks of film before week 10, for the "how much film do you need" table.
FILM_WEEKS = [1, 2, 4, 9]
FILM_TABLE_PRIORS = [10, 20, 40, 80, 160, 320]
BOOTSTRAP_DRAWS = 2000
SEED = 8


# Same clamp as engage8.blend.logit. Isotonic calibration returns exactly 0 or
# 1 for a few extreme situations; clamping once at load means the model alone
# and the blend are scored from identical probabilities.
P_MIN = 1e-4


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, P_MIN, 1 - P_MIN)
    return np.log(p / (1 - p))


def play_losses(y: np.ndarray, p: np.ndarray) -> np.ndarray:
    p = np.clip(np.asarray(p, dtype=float), 1e-15, 1 - 1e-15)
    y = np.asarray(y, dtype=float)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def log_loss(y: np.ndarray, p: np.ndarray) -> float:
    return float(play_losses(y, p).mean())


def load_season(season: int = SEASON) -> pd.DataFrame:
    """Regular-season plays with the model's calibrated pass probability.

    Columns: offense_team, week, bucket, is_pass, model_p.
    """
    feats = pd.read_parquet(config.FEATURES_PARQUET)
    plays = pd.read_parquet(config.PLAYS_PARQUET, columns=["game_id", "play_id", "offense_team"])
    df = feats.merge(plays, on=["game_id", "play_id"], how="inner", validate="one_to_one")
    df = df[(df["season"] == season) & (df["week"] <= LAST_REGULAR_WEEK)].copy()

    artifact = load_model()
    raw = artifact["booster"].predict(df[artifact["features"]].astype("float64"))
    cal = artifact["calibration"]
    df["model_p"] = np.clip(np.interp(raw, cal["x"], cal["y"]), P_MIN, 1 - P_MIN)
    df["bucket"] = [_dd_bucket(int(d), int(t)) for d, t in zip(df["down"], df["ydstogo"])]
    df["is_pass"] = df["is_pass"].astype(float)
    return df[["offense_team", "week", "bucket", "is_pass", "model_p"]].reset_index(drop=True)


def blended(film: pd.DataFrame, test: pd.DataFrame, prior: float) -> np.ndarray:
    """Pass probability for each test play after blending in that team's film."""
    out = _logit(test["model_p"].to_numpy())
    if np.isinf(prior):
        return 1 / (1 + np.exp(-out))
    for team, team_film in film.groupby("offense_team"):
        y = team_film["is_pass"].to_numpy()
        base = _logit(team_film["model_p"].to_numpy())
        film_bucket = team_film["bucket"].to_numpy()
        everything = np.ones(len(team_film), dtype=bool)
        team_test = test.index[test["offense_team"] == team]
        for bucket, rows in test.loc[team_test].groupby("bucket").groups.items():
            applied = level_offsets(y, base, [everything, film_bucket == bucket], prior)
            if applied:
                out[test.index.get_indexer(rows)] += applied[-1][2]
    return 1 / (1 + np.exp(-out))


def split(df: pd.DataFrame, film_weeks: int = LAST_FILM_WEEK):
    """Film = the film_weeks weeks before week 10; test = weeks 10-18."""
    first = LAST_FILM_WEEK - film_weeks + 1
    film = df[(df["week"] >= first) & (df["week"] <= LAST_FILM_WEEK)]
    test = df[df["week"] > LAST_FILM_WEEK].reset_index(drop=True)
    return film, test


def sweep(film: pd.DataFrame, test: pd.DataFrame, priors=PRIORS) -> pd.DataFrame:
    """Log loss, Brier, and accuracy on the test plays for each prior."""
    y = test["is_pass"].to_numpy()
    rows = []
    for prior in priors:
        p = blended(film, test, prior)
        rows.append({
            "prior": prior,
            "log_loss": log_loss(y, p),
            "brier": float(np.mean((p - y) ** 2)),
            "accuracy": float(np.mean((p >= 0.5) == (y == 1))),
        })
    return pd.DataFrame(rows)


def per_team_gain(film, test, prior: float) -> pd.Series:
    """Log-loss improvement (model alone minus blended) for each team."""
    y = test["is_pass"].to_numpy()
    p_model = test["model_p"].to_numpy()
    p_blend = blended(film, test, prior)
    gains = {}
    for team, idx in test.groupby("offense_team").groups.items():
        i = test.index.get_indexer(idx)
        gains[team] = log_loss(y[i], p_model[i]) - log_loss(y[i], p_blend[i])
    return pd.Series(gains).sort_values()


def bootstrap_gain(film, test, prior: float, draws=BOOTSTRAP_DRAWS, seed=SEED):
    """95% interval for the pooled log-loss gain, resampling whole teams."""
    y = test["is_pass"].to_numpy()
    diff = play_losses(y, test["model_p"]) - play_losses(y, blended(film, test, prior))
    diff = pd.Series(diff).groupby(test["offense_team"].to_numpy())
    sums, counts = diff.sum().to_numpy(), diff.count().to_numpy()
    rng = np.random.default_rng(seed)
    pick = rng.integers(0, len(sums), size=(draws, len(sums)))
    gains = sums[pick].sum(axis=1) / counts[pick].sum(axis=1)
    return float(np.percentile(gains, 2.5)), float(np.percentile(gains, 97.5))


def _fmt_prior(p: float) -> str:
    return "none (model only)" if np.isinf(p) else f"{p:g}"


def main() -> None:
    ap = argparse.ArgumentParser(description="Backtest the opponent blend on 2023 NFL plays.")
    ap.add_argument("--season", type=int, default=SEASON)
    args = ap.parse_args()

    df = load_season(args.season)
    film, test = split(df)
    print(f"{args.season}: {df['offense_team'].nunique()} teams, film weeks 1-{LAST_FILM_WEEK} "
          f"({len(film):,} plays), predicting weeks {LAST_FILM_WEEK + 1}-{LAST_REGULAR_WEEK} "
          f"({len(test):,} plays)\n")

    res = sweep(film, test)
    base_ll = res.loc[res["prior"] == float("inf"), "log_loss"].item()
    print("| Prior (plays) | Log loss | vs model | Brier | Accuracy |")
    print("|---|---|---|---|---|")
    for r in res.itertuples():
        print(f"| {_fmt_prior(r.prior)} | {r.log_loss:.4f} | {base_ll - r.log_loss:+.4f} "
              f"| {r.brier:.4f} | {r.accuracy:.1%} |")

    best = res.loc[res["log_loss"].idxmin(), "prior"]
    for prior, why in ((best, "best"), (PRIOR_PLAYS, "shipped")):
        gains = per_team_gain(film, test, prior)
        lo, hi = bootstrap_gain(film, test, prior)
        gain = base_ll - res.loc[res["prior"] == prior, "log_loss"].item()
        print(f"\nPrior {prior:g} ({why}): log loss {gain:+.4f} "
              f"({gain / base_ll:.1%}), 95% CI {lo:+.4f} to {hi:+.4f} (teams resampled). "
              f"Better for {int((gains > 0).sum())} of {len(gains)} teams; "
              f"biggest gain {gains.index[-1]} {gains.iloc[-1]:+.4f}, "
              f"biggest loss {gains.index[0]} {gains.iloc[0]:+.4f}.")

    print("\nHow much film? Log-loss gain over the model alone, by prior "
          "(film = the weeks just before week 10)\n")
    shown = [p for p in PRIORS if p in FILM_TABLE_PRIORS]
    print("| Film | Plays per team | " + " | ".join(f"{p:g}" for p in shown) + " |")
    print("|---|---|" + "---|" * len(shown))
    for weeks in FILM_WEEKS:
        f, t = split(df, weeks)
        r = sweep(f, t, shown + [float("inf")]).set_index("prior")["log_loss"]
        b = r[float("inf")]
        per_team = int(f.groupby("offense_team").size().median())
        print(f"| {weeks} week{'s' if weeks > 1 else ''} | {per_team} | "
              + " | ".join(f"{b - r[p]:+.4f}" for p in shown) + " |")


if __name__ == "__main__":
    main()

"""Blend the league model with one opponent's uploaded plays.

The league model knows NFL situational football; it knows nothing about the
opponent a coach is scouting. This layers that opponent's own tendencies on
top, from the plays uploaded to the coach's team workspace:

1. all of the opponent's plays (are they run-heavy overall?)
2. plays in the same down & distance bucket
3. ... that also came out of the same formation (if given)
4. ... with the same pre-snap motion (if given)

The math lives in ``engage8.blend`` (shared with the backtest that picked
PRIOR_PLAYS); this module picks the plays for each level and labels the steps.
"""
from __future__ import annotations

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.ml  # noqa: F401
from engage8 import blend as ml_blend  # noqa: E402
from engage8 import vocab as ml_vocab  # noqa: E402
from engage8.tendencies import _dd_bucket  # noqa: E402

from app.db.models import Play
from app.services import prediction_service
from app.services import vocab as vocab_service


def _situation(p: Play) -> dict:
    return {
        "down": p.down,
        "distance": max(p.ydstogo or 10, 1),
        "yardline_100": p.yardline_100 if p.yardline_100 else 50,
        "quarter": p.quarter,
        "game_seconds_remaining": p.game_seconds_remaining,
        "score_differential": p.score_differential,
        "shotgun": None if p.shotgun is None else int(p.shotgun),
        "no_huddle": None if p.no_huddle is None else int(p.no_huddle),
    }


def blend(
    db: Session,
    team_id: int,
    game_state: dict,
    model_pass_prob: float,
) -> tuple[float, list[dict]]:
    """Return (blended pass prob, per-level steps). No opponent -> no change."""
    label = game_state.get("offense_team")
    opponent_id = game_state.get("opponent_id")
    if not label and opponent_id is None:
        return model_pass_prob, []

    stmt = select(Play).where(
        Play.team_id == team_id,
        Play.down.is_not(None),
        Play.play_type.in_(("run", "pass")),
    )
    if label:
        stmt = stmt.where(Play.offense_team == label)
    if opponent_id is not None:
        stmt = stmt.where(Play.opponent_id == opponent_id)
    plays = list(db.scalars(stmt))
    if not plays:
        return model_pass_prob, []

    name = label or "this opponent"
    y = np.array([1.0 if p.play_type == "pass" else 0.0 for p in plays])
    base = np.array([ml_blend.logit(v) for v in prediction_service.predict_many(
        [_situation(p) for p in plays])])

    fmap, mmap = vocab_service.build_maps(db, team_id)
    formation = ml_vocab.normalize_formation(game_state.get("formation"), fmap)
    motion = (ml_vocab.normalize_motion(game_state.get("motion_type"), mmap)
              if game_state.get("motion_type") else None)
    bucket = _dd_bucket(game_state["down"], game_state["distance"])

    play_bucket = np.array([_dd_bucket(p.down, p.ydstogo or 10) for p in plays])
    play_form = np.array([ml_vocab.normalize_formation(p.formation, fmap) for p in plays],
                         dtype=object)
    play_motion = np.array([ml_vocab.normalize_motion(p.motion_type, mmap) for p in plays],
                           dtype=object)

    levels = [(f"{name}, all plays", np.ones(len(plays), dtype=bool))]
    mask = play_bucket == bucket
    levels.append((f"{name} on {bucket}", mask))
    if formation:
        mask = mask & (play_form == formation)
        levels.append((f"... from {formation}", mask))
    if motion:
        mask = mask & (play_motion == motion)
        levels.append((f"... with {motion} motion", mask))

    target = ml_blend.logit(model_pass_prob)
    offset = 0.0
    steps: list[dict] = []
    for i, n, offset in ml_blend.level_offsets(y, base, [m for _, m in levels]):
        text, m = levels[i]
        steps.append({
            "label": text,
            "plays": n,
            "pass_rate": round(float(y[m].sum()) / n, 3),
            "pass_prob_after": round(float(ml_blend.sigmoid(target + offset)), 3),
        })

    return float(ml_blend.sigmoid(target + offset)), steps

"""Prediction + defensive recommendation endpoints (signed-in users)."""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.ratelimit import rate_limit
from app.db.models import Prediction, User
from app.deps import check_opponent, get_current_user, get_db, get_owned_team
from app.schemas.prediction import (
    PredictRequest,
    PredictResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.services import blend, prediction_service, recommendation

router = APIRouter(tags=["prediction"])
log = logging.getLogger(__name__)

_limit = Depends(rate_limit("predict", 120, 60))


def _persist(db: Session, user: User, game_state: dict, result: dict) -> None:
    """Best-effort log of a prediction; a DB hiccup never breaks the response."""
    try:
        db.add(Prediction(
            user_id=user.id,
            game_state=json.dumps(game_state),
            result=json.dumps(result),
        ))
        db.commit()
    except Exception:  # noqa: BLE001 - logging is non-critical
        log.exception("could not log prediction")
        db.rollback()


def _predict(req: PredictRequest, db: Session, user: User) -> PredictResponse:
    game_state = req.model_dump()
    base = prediction_service.predict(game_state)
    result = dict(base, model_pass_prob=base["pass_prob"], blend=[])

    if req.team_id is not None:
        get_owned_team(req.team_id, db, user)
        check_opponent(db, req.team_id, req.opponent_id)
        p, steps = blend.blend(db, req.team_id, game_state, base["pass_prob"])
        if steps:
            from engage8.predict import summarize  # noqa: PLC0415

            used = steps[-1]
            why = (f"{base['why']} Adjusted with {used['plays']} of this opponent's "
                   f"plays ({used['label']}).")
            result = dict(summarize(p, why), model_pass_prob=base["pass_prob"], blend=steps)
    return PredictResponse(**result)


@router.post("/predict", response_model=PredictResponse, dependencies=[_limit])
def predict(
    req: PredictRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PredictResponse:
    """Score a pre-snap situation; optionally blend in an opponent's plays."""
    resp = _predict(req, db, user)
    _persist(db, user, req.model_dump(), resp.model_dump())
    return resp


@router.post("/recommend", response_model=RecommendResponse, dependencies=[_limit])
def recommend(
    req: RecommendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> RecommendResponse:
    """Predict run/pass, then suggest rules-based defensive calls."""
    predicted = _predict(req, db, user)
    calls = recommendation.recommend(predicted.model_dump(), req.model_dump())
    resp = RecommendResponse(predicted=predicted, recommendations=calls)
    _persist(db, user, req.model_dump(), resp.model_dump())
    return resp

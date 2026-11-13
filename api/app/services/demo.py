"""Throwaway demo accounts for the one-click "Try the demo" flow.

A demo user owns one team and one fictional opponent (Central HS) whose film is
the committed ``api/demo/central_hs.csv``, imported through the normal
``ingest_csv`` path. Demo users have no usable password and are purged after
``DEMO_TTL``.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import API_ROOT
from app.db.models import Game, Opponent, Play, Prediction, Team, Upload, User, VocabMapping
from app.services import tendencies as tendency_service

DEMO_CSV = API_ROOT / "demo" / "central_hs.csv"
DEMO_TTL = timedelta(hours=24)
DEMO_EMAIL_DOMAIN = "demo.engage8.app"
DEMO_TEAM_NAME = "Demo HS"
DEMO_OPPONENT_NAME = "Central HS (fictional)"
# Not a valid bcrypt hash, so verify_password() is always False: demo users
# can only be reached through the token /auth/demo hands out.
UNUSABLE_PASSWORD_HASH = "!"


def create_demo_session(db: Session, csv_path: Path = DEMO_CSV) -> tuple[User, Team, Opponent]:
    """Create a demo user with a team, an opponent and the sample film loaded."""
    user = User(
        email=f"demo-{secrets.token_hex(8)}@{DEMO_EMAIL_DOMAIN}",
        hashed_password=UNUSABLE_PASSWORD_HASH,
        is_demo=True,
    )
    db.add(user)
    db.flush()
    team = Team(owner_id=user.id, name=DEMO_TEAM_NAME, level="hs", season=datetime.now().year)
    db.add(team)
    db.flush()
    opponent = Opponent(
        team_id=team.id,
        name=DEMO_OPPONENT_NAME,
        notes="Fictional sample opponent generated for the demo.",
    )
    db.add(opponent)
    db.commit()
    user_id = user.id

    try:
        tendency_service.ingest_csv(
            db, team.id, str(csv_path),
            filename=csv_path.name,
            sha256=hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            source="hudl", opponent_id=opponent.id,
        )
    except Exception:
        db.rollback()
        _delete_users(db, [user_id])  # don't leave a half-built demo account behind
        raise
    db.refresh(user)
    return user, team, opponent


def _delete_users(db: Session, user_ids: list[int]) -> None:
    """Delete users and everything they own.

    ``teams.owner_id`` has no ON DELETE CASCADE, so walk the tree explicitly,
    children first. Plays, uploads, opponents and vocab would cascade from the
    team on their own; games would not.
    """
    if not user_ids:
        return
    team_ids = list(db.scalars(select(Team.id).where(Team.owner_id.in_(user_ids))))
    if team_ids:
        for model in (Play, Upload, VocabMapping, Game, Opponent):
            db.execute(delete(model).where(model.team_id.in_(team_ids)))
        db.execute(delete(Team).where(Team.id.in_(team_ids)))
    db.execute(delete(Prediction).where(Prediction.user_id.in_(user_ids)))
    db.execute(delete(User).where(User.id.in_(user_ids)))
    db.commit()


def purge_demo_users(db: Session, now: datetime | None = None) -> int:
    """Delete demo users older than ``DEMO_TTL`` with their data; return how many."""
    cutoff = (now or datetime.utcnow()) - DEMO_TTL
    ids = list(db.scalars(
        select(User.id).where(User.is_demo.is_(True), User.created_at < cutoff)
    ))
    _delete_users(db, ids)
    return len(ids)

"""Shared fixtures for the API tests (FastAPI TestClient, throwaway SQLite).

    cd api && python -m pytest

Every test gets its own accounts and teams (unique emails), and rate-limit
counters are cleared before each test, so tests don't depend on each other.
The database is shared for the session, because running the migrations and
loading the model for every test would be slow.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

# Settings are read at import time, so set them before importing the app.
# Pinning each one also keeps a developer's api/.env out of the tests.
_DB_DIR = tempfile.mkdtemp(prefix="engage8-api-tests-")
os.environ.update({
    "ENGAGE8_DATABASE_URL": f"sqlite:///{_DB_DIR}/test.db",
    "ENGAGE8_DEBUG": "true",
    "ENGAGE8_JWT_SECRET": "test-secret-" + uuid4().hex + uuid4().hex,
    "ENGAGE8_RATE_LIMIT_ENABLED": "true",
    "ENGAGE8_CLIENT_IP_HEADER": "",
    "ENGAGE8_DEMO_MAX_ACCOUNTS": "1000",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core import ratelimit  # noqa: E402
from app.db.session import SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "ml" / "tests" / "fixtures"
PW = "correct-horse-1"


@dataclass
class Account:
    email: str
    headers: dict[str, str]


def pytest_sessionfinish(session, exitstatus):
    # Runs even when no test used the database (e.g. only test_config.py).
    engine.dispose()
    shutil.rmtree(_DB_DIR, ignore_errors=True)


@pytest.fixture(scope="session")
def client():
    init_db()  # alembic upgrade head (the lifespan only runs under a context manager)
    return TestClient(app)


@pytest.fixture(autouse=True)
def fresh_rate_limits():
    ratelimit.reset()


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def signup(client):
    """Make a new coach account and return its email and auth headers."""
    def make(prefix: str = "coach") -> Account:
        email = f"{prefix}-{uuid4().hex[:10]}@engage8.app"
        r = client.post("/auth/signup", json={"email": email, "password": PW})
        assert r.status_code == 201, r.text
        r = client.post("/auth/login", data={"username": email, "password": PW})
        assert r.status_code == 200, r.text
        return Account(email, {"Authorization": f"Bearer {r.json()['access_token']}"})
    return make


@pytest.fixture
def coach(signup) -> Account:
    return signup("coach")


@pytest.fixture
def other_coach(signup) -> Account:
    return signup("other")


@pytest.fixture
def new_team(client):
    def make(account: Account, name: str = "My HS") -> int:
        r = client.post("/teams", json={"name": name, "level": "hs", "season": 2026},
                        headers=account.headers)
        assert r.status_code == 201, r.text
        return r.json()["id"]
    return make


@pytest.fixture
def team(coach, new_team) -> int:
    return new_team(coach)


@pytest.fixture
def opponent(client, coach, team) -> int:
    r = client.post(f"/teams/{team}/opponents", json={"name": "Central", "oc_name": "Smith"},
                    headers=coach.headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


@pytest.fixture
def upload(client):
    """POST a file to /teams/{id}/uploads; returns the response."""
    def post(account: Account, team_id: int, content, filename: str = "chart.csv", **form):
        return client.post(f"/teams/{team_id}/uploads", headers=account.headers,
                           data={k: str(v) for k, v in form.items()},
                           files={"file": (filename, content, "text/csv")})
    return post


@pytest.fixture
def demo(client):
    """Start a demo session; returns (session json, auth headers)."""
    def start():
        r = client.post("/auth/demo")
        assert r.status_code == 201, r.text
        body = r.json()
        return body, {"Authorization": f"Bearer {body['access_token']}"}
    return start

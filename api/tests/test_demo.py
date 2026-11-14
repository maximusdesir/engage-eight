"""One-click demo accounts: own data, no password, purged after 24 h, capped."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db.models import Play, Team, User
from app.services.demo import count_demo_users, purge_demo_users
from conftest import PW


def test_each_demo_gets_its_own_team_and_opponent(demo):
    (d1, _), (d2, _) = demo(), demo()
    assert d1["team_id"] != d2["team_id"] and d1["opponent_id"] != d2["opponent_id"]


def test_demo_user_is_flagged(client, demo):
    _, headers = demo()
    assert client.get("/auth/me", headers=headers).json()["is_demo"] is True


def test_demo_account_has_no_usable_password(client, demo):
    _, headers = demo()
    email = client.get("/auth/me", headers=headers).json()["email"]
    assert client.post("/auth/login", data={"username": email, "password": PW}).status_code == 401


def test_demo_film_is_loaded(client, demo):
    d, headers = demo()
    r = client.get(f"/teams/{d['team_id']}/tendencies", headers=headers,
                   params={"opponent_id": d["opponent_id"], "split": "formation"})
    assert r.status_code == 200
    rows = {x["bucket"]: x for x in r.json()["rows"]}
    # Central HS runs from I-Form and throws from Empty.
    assert rows["I-FORM"]["run_pct"] > 50 > rows["EMPTY"]["run_pct"]


def test_demo_film_is_a_normal_upload(client, demo):
    d, headers = demo()
    r = client.get(f"/teams/{d['team_id']}/uploads", headers=headers)
    assert r.status_code == 200 and len(r.json()) == 1 and r.json()[0]["n_plays"] > 200


@pytest.mark.parametrize("path", ["", "/tendencies", "/uploads", "/plays"])
def test_demo_team_is_private(client, demo, coach, path):
    d, _ = demo()
    _, another_demo = demo()
    for headers in (another_demo, coach.headers):
        assert client.get(f"/teams/{d['team_id']}{path}", headers=headers).status_code == 404


def test_demo_user_cant_see_a_regular_team(client, demo, team):
    _, headers = demo()
    assert client.get(f"/teams/{team}", headers=headers).status_code == 404


def test_purge_keeps_fresh_demos_and_regular_users(client, db, demo, coach):
    demo()
    assert purge_demo_users(db) == 0
    assert db.scalar(select(User.id).where(User.email == coach.email)) is not None


def test_purge_deletes_old_demos_and_their_data(client, db, demo, coach):
    (d1, h1), (d2, _) = demo(), demo()
    purged = purge_demo_users(db, now=datetime.utcnow() + timedelta(hours=25))
    plays_left = db.scalar(select(func.count()).select_from(Play).where(
        Play.team_id.in_([d1["team_id"], d2["team_id"]])))
    assert purged >= 2 and plays_left == 0
    assert db.get(Team, d1["team_id"]) is None
    assert client.get("/auth/me", headers=h1).status_code == 401  # token stops working
    assert client.get("/auth/me", headers=coach.headers).status_code == 200


def test_demo_is_rate_limited_per_network(client):
    codes = [client.post("/auth/demo").status_code for _ in range(10)]
    assert codes == [201] * 10
    r = client.post("/auth/demo")
    assert r.status_code == 429 and "network" in r.json()["detail"]


def test_demo_cap_says_the_demo_is_full(client, db, monkeypatch):
    monkeypatch.setattr(settings, "demo_max_accounts", count_demo_users(db))
    r = client.post("/auth/demo")
    assert r.status_code == 429 and "full" in r.json()["detail"]
    monkeypatch.undo()
    assert client.post("/auth/demo").status_code == 201

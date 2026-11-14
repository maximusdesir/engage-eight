"""Hardening: request size, field limits, upload limits, tokens, and CORS."""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.config import settings
from app.core.bodylimit import TOO_LARGE
from app.services import tendencies as tendency_service

CSV_HEAD = "offense_team,down,ydstogo,yardline_100,play_type,formation\n"


# ---- Request size ----------------------------------------------------------

def test_oversized_body_is_rejected_before_it_is_read(client, coach, team):
    big = b"x" * (7 * 1024 * 1024)
    r = client.post(f"/teams/{team}/uploads", headers=coach.headers,
                    files={"file": ("big.csv", big, "text/csv")})
    assert r.status_code == 413 and r.json()["detail"] == TOO_LARGE


def test_oversized_chunked_body_is_rejected(client, coach, team):
    def chunks():  # no Content-Length: the middleware has to count
        for _ in range(8):
            yield b"y" * (1024 * 1024)
    headers = {**coach.headers, "content-type": "multipart/form-data; boundary=x"}
    r = client.post(f"/teams/{team}/uploads", headers=headers, content=chunks())
    assert r.status_code == 413


# ---- Field limits match the database (Postgres enforces them) -------------

@pytest.mark.parametrize("path_fmt, body", [
    ("/teams", {"name": "X", "season": 30000}),
    ("/teams/{team}/opponents", {"name": "X", "oc_name": "o" * 121}),
    ("/teams/{team}/opponents", {"name": "X", "notes": "n" * 2001}),
    ("/teams/{team}/plays", {"down": 1, "ydstogo": 10, "yardline_100": 50,
                             "play_type": "run", "defense_team": "d" * 41}),
    ("/teams/{team}/plays", {"down": 1, "ydstogo": 10, "yardline_100": 50,
                             "play_type": "run", "quarter": 9}),
    ("/teams/{team}/plays", {"down": 1, "ydstogo": 10, "yardline_100": 50,
                             "play_type": "run", "result_yards": 2**40}),
])
def test_out_of_range_fields_are_422(client, coach, team, path_fmt, body):
    r = client.post(path_fmt.format(team=team), json=body, headers=coach.headers)
    assert r.status_code == 422


def test_vocab_batch_is_capped(client, coach, team):
    mappings = [{"kind": "formation", "raw_value": f"F{i}", "canonical_value": "TRIPS"}
                for i in range(501)]
    r = client.post(f"/teams/{team}/vocab", json=mappings, headers=coach.headers)
    assert r.status_code == 422


def test_team_creation_is_rate_limited(client, coach):
    codes = [client.post("/teams", json={"name": f"T{i}"}, headers=coach.headers).status_code
             for i in range(31)]
    assert codes[:30] == [201] * 30 and codes[30] == 429


# ---- Uploads ---------------------------------------------------------------

def test_long_names_in_a_csv_are_trimmed_to_fit(client, coach, team, upload):
    long_formation = "Trips Right Open Flex Nasty Split Over Unbalanced Wing"  # 55 chars
    r = upload(coach, team, CSV_HEAD + f"CENTRAL,1,10,50,run,{long_formation}\n")
    assert r.status_code == 201, r.text
    play = client.get(f"/teams/{team}/plays", headers=coach.headers).json()[0]
    assert play["formation"] == long_formation[:40]


def test_too_many_plays_in_one_upload(coach, team, upload, monkeypatch):
    monkeypatch.setattr(tendency_service, "MAX_PLAYS_PER_UPLOAD", 2)
    r = upload(coach, team, CSV_HEAD + "CENTRAL,1,10,50,run,PRO\n" * 3)
    assert r.status_code == 400 and "more than one upload can hold" in r.json()["detail"]


def test_unexpected_upload_errors_dont_echo_internals(coach, team, upload, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("INSERT INTO plays ... secret internals")
    monkeypatch.setattr(tendency_service, "ingest_csv", boom)
    r = upload(coach, team, CSV_HEAD + "CENTRAL,1,10,50,run,PRO\n")
    assert r.status_code == 400 and "INSERT" not in r.json()["detail"]


# ---- Tokens ----------------------------------------------------------------

def _token(**payload):
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


@pytest.mark.parametrize("token", [
    "not-a-jwt",
    _token(sub="abc"),  # not a user id
    _token(sub="1", exp=datetime.now(timezone.utc) - timedelta(minutes=1)),  # expired
    jwt.encode({"sub": "1"}, "some-other-secret-that-is-long-enough", algorithm="HS256"),
    jwt.encode({"sub": "1"}, None, algorithm="none"),  # unsigned
])
def test_bad_tokens_are_401(client, token):
    r = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_unknown_email_and_wrong_password_get_the_same_answer(client, coach):
    wrong_pw = client.post("/auth/login", data={"username": coach.email, "password": "nope-nope-1"})
    no_user = client.post("/auth/login", data={"username": "ghost@x.com", "password": "nope-nope-1"})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


# ---- CORS ------------------------------------------------------------------

def _preflight(client, origin):
    return client.options("/auth/demo", headers={
        "Origin": origin, "Access-Control-Request-Method": "POST"})


def test_cors_allows_the_web_origin_without_credentials(client):
    r = _preflight(client, settings.cors_origins[0])
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == settings.cors_origins[0]
    assert "access-control-allow-credentials" not in r.headers


def test_cors_refuses_other_origins(client):
    r = _preflight(client, "https://evil.example")
    assert "access-control-allow-origin" not in r.headers

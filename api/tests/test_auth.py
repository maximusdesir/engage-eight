"""Health, signup, login, and the current user."""
from conftest import PW


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


def test_short_password_is_rejected(client):
    r = client.post("/auth/signup", json={"email": "weak@engage8.app", "password": "x"})
    assert r.status_code == 422


def test_signup_then_me(client, coach):
    r = client.get("/auth/me", headers=coach.headers)
    assert r.status_code == 200
    assert r.json()["email"] == coach.email and r.json()["is_demo"] is False


def test_signup_ignores_a_client_set_role(client):
    r = client.post("/auth/signup",
                    json={"email": "sneaky@x.com", "password": PW, "role": "admin"})
    assert r.status_code == 201 and r.json()["role"] == "coach"


def test_wrong_password_is_rejected(client, coach):
    r = client.post("/auth/login", data={"username": coach.email, "password": "wrong-password"})
    assert r.status_code == 401

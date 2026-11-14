"""Rate limits key on the visitor's IP, and a forged X-Forwarded-For can't dodge them."""
import pytest

from app.config import settings


@pytest.fixture
def bad_logins(client, coach):
    """Twelve wrong-password logins (limit is 10 a minute); returns status codes."""
    def run(headers_for=lambda i: {}):
        return [client.post("/auth/login", headers=headers_for(i),
                            data={"username": coach.email, "password": "wrong-password"}
                            ).status_code for i in range(12)]
    return run


def test_login_is_rate_limited(bad_logins):
    codes = bad_logins()
    assert 429 in codes and codes[0] == 401


def test_rotating_x_forwarded_for_doesnt_reset_the_limit(bad_logins):
    assert 429 in bad_logins(lambda i: {"X-Forwarded-For": f"203.0.113.{i}"})


def test_client_ip_header_keys_the_limit(client, coach, bad_logins, monkeypatch):
    monkeypatch.setattr(settings, "client_ip_header", "cf-connecting-ip")
    codes = bad_logins(lambda i: {"CF-Connecting-IP": "198.51.100.1",
                                  "X-Forwarded-For": f"203.0.113.{i}"})
    assert 429 in codes
    # A different visitor still has their own allowance.
    r = client.post("/auth/login", headers={"CF-Connecting-IP": "198.51.100.2"},
                    data={"username": coach.email, "password": "wrong-password"})
    assert r.status_code == 401

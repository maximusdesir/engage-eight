"""Hosting settings: database URLs and the client IP header."""
import pytest

from app.config import Settings


@pytest.mark.parametrize("raw", [
    "postgresql://u:p@db.neon.tech/e8?sslmode=require",
    "postgres://u:p@db.neon.tech/e8?sslmode=require",
])
def test_plain_postgres_urls_use_psycopg3(raw):
    url = Settings(debug=True, database_url=raw).database_url
    assert url == "postgresql+psycopg://u:p@db.neon.tech/e8?sslmode=require"


def test_sqlite_url_is_left_alone():
    assert Settings(debug=True, database_url="sqlite:///x.db").database_url == "sqlite:///x.db"


def test_x_forwarded_for_cant_be_the_client_ip_header():
    with pytest.raises(ValueError):
        Settings(debug=True, client_ip_header="X-Forwarded-For")


def test_production_refuses_the_placeholder_secret():
    with pytest.raises(ValueError):
        Settings(debug=False, jwt_secret="dev-secret-change-me")

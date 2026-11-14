"""Application settings.

Reads from environment variables (and a .env file if present). Fails closed:
``debug`` defaults to false, so the app refuses to start without a real
ENGAGE8_JWT_SECRET. For local development set ENGAGE8_DEBUG=true (see
.env.example), which allows the insecure placeholder secret.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent      # api/
PROJECT_ROOT = API_ROOT.parent                          # repo root
ML_ROOT = PROJECT_ROOT / "ml"

# Placeholder used only for local development. Production must override it.
INSECURE_DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ENGAGE8_", extra="ignore")

    app_name: str = "Engage Eight API"
    debug: bool = False

    # SQLite by default; set ENGAGE8_DATABASE_URL to a Postgres URL in prod.
    database_url: str = f"sqlite:///{API_ROOT / 'engage8.db'}"

    # Auth. In production (debug=False) jwt_secret MUST be overridden via
    # ENGAGE8_JWT_SECRET; see the validator below.
    jwt_secret: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # ML: where the trained run/pass artifact and the engage8 package live.
    ml_root: Path = ML_ROOT

    # Rate limiting (in-process, per client IP). Fine for a single API
    # instance; put a shared limiter (e.g. at the proxy) in front of several.
    rate_limit_enabled: bool = True
    # Only trust X-Forwarded-For when the API sits behind your own proxy.
    trust_proxy_headers: bool = False

    min_password_length: int = 10

    # CORS for the browser dashboard. 5173 is the Vite dev server; 3000 is kept
    # for a future Next.js/Vercel frontend. Override in prod via
    # ENGAGE8_CORS_ORIGINS (JSON list) with the deployed origin.
    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ]

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3(cls, url: str) -> str:
        """Point plain Postgres URLs at the installed psycopg 3 driver.

        Hosts like Neon and Render hand out ``postgresql://`` (or
        ``postgres://``) URLs, which SQLAlchemy maps to psycopg2, which isn't
        installed. Rewrite the scheme so those URLs can be pasted as-is.
        """
        for prefix in ("postgresql://", "postgres://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @model_validator(mode="after")
    def _require_strong_secret_in_prod(self):
        """Refuse to start in production with the insecure default secret.

        With ENGAGE8_DEBUG=false, a real ENGAGE8_JWT_SECRET must be set, or
        anyone who has read the (public) source could forge auth tokens.
        """
        if not self.debug and self.jwt_secret in ("", INSECURE_DEFAULT_SECRET):
            raise ValueError(
                "ENGAGE8_JWT_SECRET must be set to a strong, unique value when "
                "ENGAGE8_DEBUG is false. Generate one with: openssl rand -hex 32"
            )
        return self


settings = Settings()

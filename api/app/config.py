"""Application settings.

Reads from environment variables (and a .env file if present). Defaults are
chosen so the API runs locally with zero configuration: SQLite on disk and the
trained model from the sibling ml/ project.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parent.parent      # api/
PROJECT_ROOT = API_ROOT.parent                          # engage_eight/
ML_ROOT = PROJECT_ROOT / "ml"

# Placeholder used only for local development. Production must override it.
INSECURE_DEFAULT_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="ENGAGE8_", extra="ignore")

    app_name: str = "Engage Eight API"
    debug: bool = True

    # SQLite by default; set ENGAGE8_DATABASE_URL to a Postgres URL in prod.
    database_url: str = f"sqlite:///{API_ROOT / 'engage8.db'}"

    # Auth. In production (debug=False) jwt_secret MUST be overridden via
    # ENGAGE8_JWT_SECRET; see the validator below.
    jwt_secret: str = INSECURE_DEFAULT_SECRET
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    # ML: where the trained run/pass artifact and the engage8 package live.
    ml_root: Path = ML_ROOT
    ml_artifact_path: Path = ML_ROOT / "artifacts" / "runpass_model.joblib"

    # CORS for the browser dashboard. 5173 is the Vite dev server; 3000 is kept
    # for a future Next.js/Vercel frontend. Override in prod via
    # ENGAGE8_CORS_ORIGINS (JSON list) with the deployed origin.
    cors_origins: list[str] = [
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:3000", "http://127.0.0.1:3000",
    ]

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

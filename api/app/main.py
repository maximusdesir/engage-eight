"""Engage Eight API entrypoint.

Run locally (dev mode allows the placeholder JWT secret):
    cd api
    ENGAGE8_DEBUG=true uvicorn app.main:app --reload
Then open http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .core.bodylimit import BodySizeLimit
from .db.session import SessionLocal, init_db
from .routers import auth, plays, predict, teams, tendencies, uploads, vocab
from .routers.uploads import MAX_UPLOAD_BYTES
from .services.demo import purge_demo_users


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # alembic upgrade head
    with SessionLocal() as db:
        purge_demo_users(db)   # demo accounts older than 24 h
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

# Largest upload (5 MB) plus room for the multipart wrapping and form fields.
app.add_middleware(BodySizeLimit, max_bytes=MAX_UPLOAD_BYTES + 512 * 1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    # Auth is a bearer header, never a cookie, so the browser has no reason to
    # send credentials cross-origin.
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "app": settings.app_name}


# Each router is owned by a focused module; they are registered here.
app.include_router(auth.router)
app.include_router(teams.router)
app.include_router(plays.router)
app.include_router(predict.router)
app.include_router(tendencies.router)
app.include_router(uploads.router)
app.include_router(vocab.router)

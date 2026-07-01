"""Engage Eight API entrypoint.

Run locally:
    cd api
    uvicorn app.main:app --reload
Then open http://localhost:8000/docs
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db.session import init_db
from .routers import auth, plays, predict, teams, tendencies, uploads, vocab


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()          # create SQLite tables on startup
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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

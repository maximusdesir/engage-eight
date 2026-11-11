"""Small in-process, per-client-IP sliding-window rate limiter.

Good enough for a single API process. With several workers/instances each
keeps its own counts, so put a shared limiter (proxy or Redis) in front.

    @router.post("/login", dependencies=[Depends(rate_limit("login", 10, 60))])
"""
from __future__ import annotations

import threading
import time
from collections import deque

from fastapi import HTTPException, Request, status

from app.config import settings

_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = {}
_last_sweep = 0.0


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _sweep(now: float, max_window: float = 3600.0) -> None:
    """Drop idle keys so memory stays bounded."""
    global _last_sweep
    if now - _last_sweep < 60:
        return
    _last_sweep = now
    for key in [k for k, q in _hits.items() if not q or now - q[-1] > max_window]:
        del _hits[key]


def rate_limit(name: str, limit: int, window_seconds: int):
    """FastAPI dependency allowing ``limit`` calls per ``window_seconds``."""

    def dependency(request: Request) -> None:
        if not settings.rate_limit_enabled:
            return
        now = time.monotonic()
        key = (name, client_ip(request))
        with _lock:
            _sweep(now)
            q = _hits.setdefault(key, deque())
            while q and now - q[0] >= window_seconds:
                q.popleft()
            if len(q) >= limit:
                retry = int(window_seconds - (now - q[0])) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Try again shortly.",
                    headers={"Retry-After": str(retry)},
                )
            q.append(now)

    return dependency


def reset() -> None:
    """Clear all counters (tests)."""
    with _lock:
        _hits.clear()

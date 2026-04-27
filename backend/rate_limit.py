"""SlowAPI rate limiter configuration."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.config import SETTINGS


limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],  # applied per-endpoint
    storage_uri=SETTINGS.redis_url,
    strategy="fixed-window",
)


_THEMED_MESSAGES = [
    "The cellar is shut. You've poured five tastings this hour — come back when the wax softens.",
    "We only have so many bottles behind the bar. Try again in a bit.",
    "The sommelier has requested an hour of silence. Your next pour is reserved.",
]


def themed_429(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    idx = (sum(map(ord, get_remote_address(request))) % len(_THEMED_MESSAGES))
    body = {
        "error": {
            "code": "rate_limited",
            "message": _THEMED_MESSAGES[idx],
            "detail": f"Limit: {SETTINGS.per_ip_tastings_per_hour} tastings per hour per IP.",
            "retry_after_seconds": 3600,
        }
    }
    resp = JSONResponse(status_code=429, content=body)
    resp.headers["Retry-After"] = "3600"
    return resp


PER_IP_TASTINGS = f"{SETTINGS.per_ip_tastings_per_hour}/hour"
GLOBAL_TASTINGS = f"{SETTINGS.global_tastings_per_hour}/hour"

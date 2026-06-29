"""Security headers and auth rate limiting middleware."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from typing import Callable, DefaultDict, Deque, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import Settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add standard security headers on every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=()",
        )
        if request.url.scheme == "https" or request.headers.get("X-Forwarded-Proto") == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple sliding-window rate limiter for auth endpoints."""

    def __init__(
        self,
        app,
        *,
        max_requests: int = 20,
        window_seconds: int = 60,
        paths: Tuple[str, ...] = ("/api/v1/auth/login", "/api/v1/auth/refresh"),
    ) -> None:
        super().__init__(app)
        self._max = max_requests
        self._window = window_seconds
        self._paths = paths
        self._hits: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def _client_key(self, request: Request) -> str:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path.rstrip("/") or "/"
        normalized_paths = {p.rstrip("/") or "/" for p in self._paths}
        if path not in normalized_paths:
            return await call_next(request)

        now = time.monotonic()
        key = self._client_key(request)
        bucket = self._hits[key]
        while bucket and now - bucket[0] > self._window:
            bucket.popleft()
        if len(bucket) >= self._max:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "Too many authentication attempts. Try again later.",
                    }
                },
                headers={"Retry-After": str(self._window)},
            )
        bucket.append(now)
        return await call_next(request)


def production_rate_limit(settings: Settings) -> int:
    """Tighter auth rate limit in production."""
    return 10 if settings.is_production else 20

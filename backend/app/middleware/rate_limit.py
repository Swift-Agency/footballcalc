import time
from collections import defaultdict

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.services.settings_reader import get_feature_flags, get_rate_limit_per_minute

# client -> list of unix timestamps (last minute)
_buckets: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


class RateLimitAndFeatureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path.startswith("/api/admin") or path.startswith("/admin/"):
            return await call_next(request)

        flags = get_feature_flags()
        section = _path_to_section(path)
        if section and flags.get(section) is False:
            return JSONResponse({"detail": "Section disabled"}, status_code=403)

        limit = get_rate_limit_per_minute()
        if limit <= 0 or not path.startswith("/api/"):
            return await call_next(request)

        now = time.time()
        ip = _client_ip(request)
        window = _buckets[ip]
        cutoff = now - 60.0
        window[:] = [t for t in window if t >= cutoff]
        if len(window) >= limit:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        window.append(now)

        return await call_next(request)


def _path_to_section(path: str) -> str | None:
    if path.startswith("/api/leagues"):
        return "leagues"
    return None

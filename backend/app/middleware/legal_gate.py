from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database import SessionLocal
from app.services import legal
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthError,
    get_telegram_user_id_from_validated,
    validate_init_data,
)

EXEMPT_PATHS = {
    "/api/health",
    "/api/billing/config",
    "/api/billing/yookassa/webhook",
}


class LegalAccessMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        if path in EXEMPT_PATHS or path.startswith("/api/team-logos/"):
            return await call_next(request)

        bot_token = os.getenv("MAIN_BOT_TOKEN", "").strip()
        if not bot_token:
            return await call_next(request)

        init_data = request.headers.get("X-Telegram-Init-Data", "")
        if not init_data:
            return JSONResponse(
                {
                    "code": "auth_required",
                    "message": "Откройте приложение через Telegram, чтобы продолжить.",
                },
                status_code=401,
            )
        try:
            validated = validate_init_data(init_data, bot_token)
            telegram_id = get_telegram_user_id_from_validated(validated)
            if not telegram_id:
                raise TelegramWebAppAuthError("telegram user id missing")
        except TelegramWebAppAuthError as exc:
            return JSONResponse(
                {"code": "auth_required", "message": str(exc)},
                status_code=401,
            )

        db = SessionLocal()
        try:
            if legal.has_current_legal_acceptance(db, int(telegram_id)):
                return await call_next(request)
            return JSONResponse(legal.legal_gate_payload(db), status_code=403)
        finally:
            db.close()

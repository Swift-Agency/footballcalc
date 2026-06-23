import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.telegram_webapp_auth import TelegramWebAppAuthError, validate_init_data

router = APIRouter(prefix="/auth", tags=["auth"])


class TelegramAuthBody(BaseModel):
    init_data: str


@router.post("/telegram")
def verify_telegram_init_data(body: TelegramAuthBody):
    """
    Verify Mini App initData and return parsed user payload.
    Uses MAIN_BOT_TOKEN from environment.
    """
    token = os.getenv("MAIN_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=503, detail="MAIN_BOT_TOKEN not configured")

    try:
        data = validate_init_data(body.init_data.strip(), token)
    except TelegramWebAppAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    user = data.get("user")
    return {
        "ok": True,
        "user": user,
        "auth_date": data.get("auth_date"),
        "query_id": data.get("query_id"),
    }

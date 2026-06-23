import json
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import AppEvent, TelegramUserPing
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthError,
    get_telegram_user_id_from_validated,
    validate_init_data,
)

logger = logging.getLogger("events")

router = APIRouter(prefix="/events", tags=["events"])

EVENT_SECRET_ENV = "EVENTS_INGEST_SECRET"
REQUIRE_INIT_ENV = "EVENTS_REQUIRE_INIT_DATA"


class EventPayload(BaseModel):
    event_type: str
    payload: dict | None = None
    telegram_user_id: int | None = None


def _authorize_event_request(
    x_event_secret: str | None,
    x_telegram_init_data: str | None,
    body: EventPayload,
) -> int | None:
    """Return effective telegram user id for the event (after auth)."""
    expected_secret = os.getenv(EVENT_SECRET_ENV, "").strip()
    if expected_secret:
        if (x_event_secret or "").strip() != expected_secret:
            raise HTTPException(status_code=401, detail="Invalid event secret")
        return body.telegram_user_id

    require_init = os.getenv(REQUIRE_INIT_ENV, "").lower() in {"1", "true", "yes"}
    if not require_init:
        return body.telegram_user_id

    token = os.getenv("MAIN_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(
            status_code=503,
            detail="MAIN_BOT_TOKEN required when EVENTS_REQUIRE_INIT_DATA is enabled",
        )
    raw = (x_telegram_init_data or "").strip()
    if not raw:
        raise HTTPException(status_code=401, detail="X-Telegram-Init-Data required")

    try:
        data = validate_init_data(raw, token)
    except TelegramWebAppAuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e

    uid = get_telegram_user_id_from_validated(data)
    if uid is None:
        raise HTTPException(status_code=401, detail="initData must contain user")

    if body.telegram_user_id is not None and body.telegram_user_id != uid:
        raise HTTPException(status_code=403, detail="telegram_user_id does not match initData")

    return uid


@router.post("")
def ingest_event(
    body: EventPayload,
    x_event_secret: str | None = Header(default=None, alias="X-Event-Secret"),
    x_telegram_init_data: str | None = Header(default=None, alias="X-Telegram-Init-Data"),
):
    effective_uid = _authorize_event_request(x_event_secret, x_telegram_init_data, body)

    db = SessionLocal()
    try:
        ev = AppEvent(
            event_type=body.event_type[:120],
            payload_json=json.dumps(body.payload)[:4000] if body.payload is not None else None,
            telegram_user_id=effective_uid,
            created_at=datetime.now(timezone.utc),
        )
        db.add(ev)
        if effective_uid is not None:
            exists = (
                db.query(TelegramUserPing)
                .filter(TelegramUserPing.telegram_user_id == effective_uid)
                .first()
            )
            if not exists:
                db.add(
                    TelegramUserPing(
                        telegram_user_id=effective_uid,
                        first_seen_at=datetime.now(timezone.utc),
                    )
                )
        db.commit()
        return {"ok": True}
    except Exception as e:
        logger.warning("event ingest failed: %s", e)
        db.rollback()
        raise HTTPException(status_code=500, detail="failed") from e
    finally:
        db.close()

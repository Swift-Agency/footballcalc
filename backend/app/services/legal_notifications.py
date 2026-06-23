"""User notifications for legal document changes."""
from __future__ import annotations

import logging
import os
import threading
from typing import Iterable

import httpx
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import DeletedUserBlock, LegalAcceptance, LegalDocumentVersion, TelegramUserPing

logger = logging.getLogger("legal_notifications")

TELEGRAM_API = "https://api.telegram.org"
PARSE_MODE = "HTML"


def _get_proxy() -> str | None:
    return os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip() or None


def _broadcast_targets(db: Session) -> list[int]:
    accepted = {int(x[0]) for x in db.query(LegalAcceptance.telegram_id).distinct().all()}
    users = {int(x[0]) for x in db.query(TelegramUserPing.telegram_user_id).all()}
    blocked = {int(x[0]) for x in db.query(DeletedUserBlock.telegram_id).distinct().all()}
    return sorted((accepted | users) - blocked)


def _send_many(token: str, chat_ids: Iterable[int], text: str) -> tuple[int, int]:
    sent = 0
    failed = 0
    url = f"{TELEGRAM_API}/bot{token}/sendMessage"
    proxy = _get_proxy()
    with httpx.Client(proxy=proxy, timeout=20.0) as client:
        for chat_id in chat_ids:
            try:
                resp = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text[:4000],
                        "parse_mode": PARSE_MODE,
                        "disable_web_page_preview": True,
                    },
                )
                if resp.is_success and (resp.json().get("ok") is True):
                    sent += 1
                else:
                    failed += 1
            except Exception as exc:
                failed += 1
                logger.warning("Legal notice send failed chat_id=%s: %s", chat_id, exc)
    return sent, failed


def _notice_text(row: LegalDocumentVersion) -> str:
    effective = row.effective_at_msk.strftime("%Y-%m-%d %H:%M") if row.effective_at_msk else "не указано"
    return (
        "<b>Обновление юридических документов</b>\n\n"
        "Юридические документы сервиса изменены. Уведомляем заранее: новая версия вступит в силу "
        f"<b>{effective} МСК</b>.\n\n"
        f"Версия документов: <code>{row.version}</code>\n"
        f"Пользовательское соглашение: {row.terms_url}\n"
        f"Политика конфиденциальности: {row.privacy_url}\n"
        f"Дисклеймер: {row.disclaimer_url}\n\n"
        "После вступления изменений в силу потребуется повторно принять условия для доступа к приложению."
    )


def send_legal_update_notice(document_version_id: int) -> dict[str, int]:
    token = os.getenv("MAIN_BOT_TOKEN", "").strip()
    if not token:
        logger.info("Legal notice skipped: MAIN_BOT_TOKEN is not set")
        return {"sent": 0, "failed": 0}

    db = SessionLocal()
    try:
        row = db.query(LegalDocumentVersion).filter(LegalDocumentVersion.id == document_version_id).first()
        if not row:
            return {"sent": 0, "failed": 0}
        targets = _broadcast_targets(db)
        sent, failed = _send_many(token, targets, _notice_text(row))
        logger.info(
            "Legal update notice sent: document_version_id=%d sent=%d failed=%d",
            document_version_id,
            sent,
            failed,
        )
        return {"sent": sent, "failed": failed}
    finally:
        db.close()


def start_legal_update_notice(document_version_id: int) -> None:
    threading.Thread(
        target=send_legal_update_notice,
        args=(document_version_id,),
        daemon=True,
        name=f"legal-notice-{document_version_id}",
    ).start()

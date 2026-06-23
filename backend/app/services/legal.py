from __future__ import annotations

from datetime import datetime, timedelta
import html
import os
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AdminAuditLog,
    AppEvent,
    DeletedUserBlock,
    LegalAcceptance,
    LegalDocumentVersion,
    Payment,
    PremiumUsageEvent,
    Subscription,
    TelegramUserPing,
    User,
)
from app.services.moscow_time import moscow_now
from app.services import sstats_cache

LEGAL_NOTICE_DAYS = 7


def _web_app_url() -> str:
    return (os.getenv("WEB_APP_URL", "").strip() or "https://footballcal.duckdns.org").rstrip("/")


def public_legal_url(doc_type: str) -> str:
    return f"{_web_app_url()}/legal/{doc_type}"


def public_legal_links() -> dict[str, str]:
    return {
        "terms_url": public_legal_url("terms"),
        "privacy_url": public_legal_url("privacy"),
        "disclaimer_url": public_legal_url("disclaimer"),
    }


PLACEHOLDER_TERMS_URL = public_legal_url("terms")
PLACEHOLDER_PRIVACY_URL = public_legal_url("privacy")
PLACEHOLDER_DISCLAIMER_URL = public_legal_url("disclaimer")


def msk_naive_now() -> datetime:
    return moscow_now().replace(tzinfo=None)


def minimum_effective_at_msk() -> datetime:
    return msk_naive_now() + timedelta(days=LEGAL_NOTICE_DAYS)


def ensure_default_legal_document(db: Session) -> LegalDocumentVersion:
    active = (
        db.query(LegalDocumentVersion)
        .filter(LegalDocumentVersion.is_active.is_(True))
        .order_by(LegalDocumentVersion.created_at.desc())
        .first()
    )
    if active:
        return active

    row = LegalDocumentVersion(
        version="v1",
        terms_url=f"{_web_app_url()}/legal/terms/v1",
        privacy_url=f"{_web_app_url()}/legal/privacy/v1",
        disclaimer_url=f"{_web_app_url()}/legal/disclaimer/v1",
        effective_at_msk=msk_naive_now(),
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def get_active_legal_document(db: Session) -> LegalDocumentVersion:
    return ensure_default_legal_document(db)


def get_effective_legal_document(db: Session) -> LegalDocumentVersion:
    active = get_active_legal_document(db)
    now = msk_naive_now()
    if active.effective_at_msk and active.effective_at_msk > now:
        previous = (
            db.query(LegalDocumentVersion)
            .filter(
                LegalDocumentVersion.id != active.id,
                LegalDocumentVersion.effective_at_msk.isnot(None),
                LegalDocumentVersion.effective_at_msk <= now,
            )
            .order_by(LegalDocumentVersion.effective_at_msk.desc(), LegalDocumentVersion.created_at.desc())
            .first()
        )
        if previous:
            return previous
    return active


def upsert_active_legal_document(
    db: Session,
    *,
    actor_tg_id: int,
    version: str,
    terms_url: str,
    privacy_url: str,
    disclaimer_url: str,
    effective_at_msk: datetime | None = None,
) -> LegalDocumentVersion:
    version = (version or "").strip() or "v1"
    terms_url = (terms_url or "").strip() or f"{_web_app_url()}/legal/terms/v1"
    privacy_url = (privacy_url or "").strip() or f"{_web_app_url()}/legal/privacy/v1"
    disclaimer_url = (disclaimer_url or "").strip() or f"{_web_app_url()}/legal/disclaimer/v1"
    previous_active = get_active_legal_document(db)
    document_changed = (
        previous_active.version != version
        or previous_active.terms_url != terms_url
        or previous_active.privacy_url != privacy_url
        or previous_active.disclaimer_url != disclaimer_url
    )
    min_effective = minimum_effective_at_msk()
    if effective_at_msk is None:
        effective_at_msk = min_effective
    elif document_changed and effective_at_msk < min_effective:
        effective_at_msk = min_effective

    changed = (
        document_changed
        or previous_active.effective_at_msk != effective_at_msk
    )

    db.query(LegalDocumentVersion).update({LegalDocumentVersion.is_active: False})
    row = db.query(LegalDocumentVersion).filter(LegalDocumentVersion.version == version).first()
    if row:
        row.terms_url = terms_url
        row.privacy_url = privacy_url
        row.disclaimer_url = disclaimer_url
        row.effective_at_msk = effective_at_msk
        row.is_active = True
        row.created_by_telegram_id = actor_tg_id
    else:
        row = LegalDocumentVersion(
            version=version,
            terms_url=terms_url,
            privacy_url=privacy_url,
            disclaimer_url=disclaimer_url,
            effective_at_msk=effective_at_msk,
            is_active=True,
            created_by_telegram_id=actor_tg_id,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    if changed:
        from app.services.legal_notifications import start_legal_update_notice

        start_legal_update_notice(row.id)
    return row


def latest_user_deletion(db: Session, telegram_id: int) -> DeletedUserBlock | None:
    return (
        db.query(DeletedUserBlock)
        .filter(DeletedUserBlock.telegram_id == telegram_id)
        .order_by(DeletedUserBlock.deleted_at_msk.desc())
        .first()
    )


def latest_user_acceptance(db: Session, telegram_id: int) -> LegalAcceptance | None:
    return (
        db.query(LegalAcceptance)
        .filter(LegalAcceptance.telegram_id == telegram_id)
        .order_by(LegalAcceptance.accepted_at_msk.desc())
        .first()
    )


def has_current_legal_acceptance(db: Session, telegram_id: int) -> bool:
    active = get_effective_legal_document(db)
    acceptance = latest_user_acceptance(db, telegram_id)
    if not acceptance:
        return False
    if acceptance.document_version_id != active.id:
        return False
    deleted = latest_user_deletion(db, telegram_id)
    if deleted and acceptance.accepted_at_msk <= deleted.deleted_at_msk:
        return False
    return True


def record_legal_acceptance(db: Session, telegram_id: int) -> LegalAcceptance:
    active = get_effective_legal_document(db)
    row = LegalAcceptance(
        telegram_id=telegram_id,
        accepted_at_msk=msk_naive_now(),
        document_version_id=active.id,
        document_version=active.version,
        terms_url_snapshot=active.terms_url,
        privacy_url_snapshot=active.privacy_url,
        disclaimer_url_snapshot=active.disclaimer_url,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def legal_gate_payload(db: Session) -> dict[str, Any]:
    active = get_effective_legal_document(db)
    links = public_legal_links()
    return {
        "code": "legal_acceptance_required",
        "message": "Перед использованием приложения примите условия в боте.",
        "version": active.version,
        **links,
    }


def _extract_doc_version(url: str | None) -> str:
    if not url:
        return "v1"
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] in ("terms", "privacy", "disclaimer"):
        return parts[-1]
    return "v1"


def legal_welcome_text(db: Session) -> str:
    active = get_effective_legal_document(db)
    links = public_legal_links()
    terms_url = html.escape(links["terms_url"], quote=True)
    privacy_url = html.escape(links["privacy_url"], quote=True)
    disclaimer_url = html.escape(links["disclaimer_url"], quote=True)
    return (
        "Добро пожаловать в Football Calculator.\n\n"
        "Сервис предоставляет статистическую информацию по футбольным матчам. "
        "Информация не является инвестиционной рекомендацией и не гарантирует результат.\n\n"
        "Перед продолжением ознакомьтесь с документами:\n"
        f"• <a href=\"{terms_url}\">Пользовательское соглашение</a>\n"
        f"• <a href=\"{privacy_url}\">Политика конфиденциальности</a>\n"
        f"• <a href=\"{disclaimer_url}\">Дисклеймер</a>\n\n"
        f"Версия документов: <code>{html.escape(active.version)}</code>"
    )


def legal_stats(db: Session) -> dict[str, int]:
    accepted_users = db.query(func.count(func.distinct(LegalAcceptance.telegram_id))).scalar() or 0
    return {"accepted_users": int(accepted_users)}


def delete_user_data(db: Session, telegram_id: int, reason: str = "delete_my_data") -> None:
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if user:
        db.query(PremiumUsageEvent).filter(PremiumUsageEvent.user_id == user.id).delete()
        db.query(Payment).filter(Payment.user_id == user.id).delete()
        db.query(Subscription).filter(Subscription.user_id == user.id).delete()
        db.delete(user)

    db.query(LegalAcceptance).filter(LegalAcceptance.telegram_id == telegram_id).delete()
    db.query(TelegramUserPing).filter(TelegramUserPing.telegram_user_id == telegram_id).delete()
    db.query(AppEvent).filter(AppEvent.telegram_user_id == telegram_id).delete()
    db.query(AdminAuditLog).filter(AdminAuditLog.telegram_user_id == telegram_id).delete()
    db.add(DeletedUserBlock(telegram_id=telegram_id, deleted_at_msk=msk_naive_now(), reason=reason))
    db.commit()
    try:
        sstats_cache.clear_all()
    except Exception:
        pass

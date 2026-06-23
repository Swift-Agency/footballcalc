from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.models import AdminUser

DEFAULT_BOOTSTRAP_ADMIN_IDS = (1224325329, 1899077005, 766848138)


def _parse_admin_ids(raw: str) -> set[int]:
    out: set[int] = set()
    for part in (raw or "").split(","):
        token = part.strip()
        if token.isdigit():
            out.add(int(token))
    return out


def bootstrap_admin_ids() -> set[int]:
    env_ids = _parse_admin_ids(os.getenv("ADMIN_TELEGRAM_IDS", ""))
    return set(DEFAULT_BOOTSTRAP_ADMIN_IDS) | env_ids


def ensure_bootstrap_admins(db: Session) -> None:
    now = datetime.utcnow()
    for tg_id in sorted(bootstrap_admin_ids()):
        row = db.query(AdminUser).filter(AdminUser.telegram_id == tg_id).first()
        if row:
            if not row.is_active:
                row.is_active = True
            row.is_superadmin = True
            continue
        db.add(
            AdminUser(
                telegram_id=tg_id,
                is_active=True,
                is_superadmin=True,
                created_at=now,
                created_by_telegram_id=tg_id,
            )
        )
    db.commit()


def is_admin(db: Session, telegram_id: int) -> bool:
    ensure_bootstrap_admins(db)
    row = (
        db.query(AdminUser)
        .filter(AdminUser.telegram_id == telegram_id, AdminUser.is_active.is_(True))
        .first()
    )
    return row is not None


def list_admins(db: Session) -> list[AdminUser]:
    ensure_bootstrap_admins(db)
    return db.query(AdminUser).order_by(AdminUser.is_superadmin.desc(), AdminUser.created_at.asc()).all()


def add_admin(db: Session, actor_tg_id: int, target_tg_id: int, *, superadmin: bool = False) -> AdminUser:
    ensure_bootstrap_admins(db)
    row = db.query(AdminUser).filter(AdminUser.telegram_id == target_tg_id).first()
    if row:
        row.is_active = True
        if superadmin:
            row.is_superadmin = True
        db.commit()
        db.refresh(row)
        return row

    row = AdminUser(
        telegram_id=target_tg_id,
        is_active=True,
        is_superadmin=superadmin,
        created_by_telegram_id=actor_tg_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def disable_admin(db: Session, actor_tg_id: int, target_tg_id: int) -> AdminUser | None:
    ensure_bootstrap_admins(db)
    row = db.query(AdminUser).filter(AdminUser.telegram_id == target_tg_id).first()
    if not row:
        return None
    if row.is_superadmin and actor_tg_id != target_tg_id:
        return row
    row.is_active = False
    db.commit()
    db.refresh(row)
    return row

"""
Process Telegram updates for the admin bot.
Uses admin_ops + DB directly (same process as FastAPI — no self-HTTP).
"""
from __future__ import annotations

import io
from pathlib import Path
import mammoth
import logging
import os
from datetime import datetime
from typing import Any

import httpx

from admin_bot import format_ru as ru
from admin_bot import state as bot_state
from app.database import SessionLocal
from app.services import admin_access, admin_ops
from app.services.crypto_secrets import crypto_configured
from app.services import sstats_cache

logger = logging.getLogger("admin_bot")

TELEGRAM_API = "https://api.telegram.org"
PARSE_MODE = "HTML"

# SStats cache scopes (see app/services/sstats.py _scope_for_path)
CACHE_SCOPES = (
    "leagues",
    "standings",
    "games_list",
    "game_glicko",
    "game_detail",
    "teams",
    "other",
)


def _allowed(uid: int) -> bool:
    db = SessionLocal()
    try:
        return admin_access.is_admin(db, uid)
    finally:
        db.close()


def _get_proxy() -> str | None:
    return os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip() or None


def _tg_post(token: str, method: str, **kwargs: Any) -> dict:
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    payload = {k: v for k, v in kwargs.items() if v is not None}
    proxy = _get_proxy()
    with httpx.Client(proxy=proxy, timeout=45.0) as client:
        r = client.post(url, json=payload)
        try:
            return r.json()
        except Exception:
            return {}


def _truncate(s: str, n: int = 3800) -> str:
    s = s or ""
    return s if len(s) <= n else s[: n - 3] + "..."


def _kb_main() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Ключи API", "callback_data": "m:keys"},
                {"text": "Мониторинг", "callback_data": "m:mon"},
            ],
            [
                {"text": "Кэш", "callback_data": "m:cache"},
                {"text": "Настройки", "callback_data": "m:set"},
            ],
            [
                {"text": "💳 Подписка", "callback_data": "m:sub"},
            ],
            [
                {"text": "⚖️ Юридические документы", "callback_data": "m:legal"},
                {"text": "👮 Админы", "callback_data": "m:admins"},
            ],
        ]
    }


def _kb_sub() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Статистика", "callback_data": "sub:stat"},
                {"text": "Платежи", "callback_data": "sub:pay"},
            ],
            [
                {"text": "Цена (₽)", "callback_data": "sub:price"},
                {"text": "Период (дней)", "callback_data": "sub:period"},
            ],
            [
                {"text": "Бесплатные лиги", "callback_data": "sub:free"},
                {"text": "Retry-окно", "callback_data": "sub:retry"},
            ],
            [
                {"text": "Отменить подписку user_id", "callback_data": "sub:cancel_uid"},
            ],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _kb_keys() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Просмотр", "callback_data": "k:v"},
                {"text": "Проверить", "callback_data": "k:val"},
            ],
            [{"text": "Обновить ключ SStats", "callback_data": "k:s"}],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _kb_mon_window(mon_window: str) -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "За 7 дней", "callback_data": "w:7"},
                {"text": "За всё время", "callback_data": "w:a"},
            ],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _kb_cache() -> dict:
    rows: list[list[dict[str, str]]] = [
        [
            {"text": "Статистика", "callback_data": "c:st"},
            {"text": "Очистить всё", "callback_data": "c:all"},
        ],
        [{"text": "TTL кэша", "callback_data": "c:ttl"}],
    ]
    row: list[dict[str, str]] = []
    for sc in CACHE_SCOPES:
        if len(row) >= 2:
            rows.append(row)
            row = []
        row.append({"text": sc[:16], "callback_data": f"c:s:{sc}"})
    if row:
        rows.append(row)
    rows.append([{"text": "« Назад", "callback_data": "m:main"}])
    return {"inline_keyboard": rows}


def _kb_settings() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Текущие настройки", "callback_data": "s:show"},
                {"text": "Синхронизация", "callback_data": "s:sync"},
            ],
            [
                {"text": "Лимит запросов/мин", "callback_data": "s:rl"},
                {"text": "TTL кэша", "callback_data": "s:ttl"},
            ],
            [
                {"text": "Раздел «Лиги» вкл/выкл", "callback_data": "s:fl"},
                {"text": "Уведомления вкл/выкл", "callback_data": "s:n"},
            ],
            [{"text": "Кэш SStats вкл/выкл", "callback_data": "s:sc"}],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _kb_legal() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Показать документы", "callback_data": "legal:show"},
                {"text": "Статистика акцептов", "callback_data": "legal:stat"},
            ],
            [
                {"text": "Рассылка уведомления", "callback_data": "legal:broadcast"},
                {"text": "Как обновить документы?", "callback_data": "legal:help"},
            ],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _kb_admins() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "Список", "callback_data": "admins:list"},
                {"text": "Добавить", "callback_data": "admins:add"},
            ],
            [
                {"text": "Отключить", "callback_data": "admins:remove"},
            ],
            [{"text": "« Назад", "callback_data": "m:main"}],
        ]
    }


def _extract_doc_version(url: str | None) -> str:
    if not url:
        return "не задано"
    parts = url.rstrip("/").split("/")
    if len(parts) >= 2 and parts[-2] in ("terms", "privacy", "disclaimer"):
        return parts[-1]
    return "не задано"


def _format_legal_current(data: dict[str, Any]) -> str:
    effective = data.get("effective_at_msk") or "не задано"
    terms_ver = _extract_doc_version(data.get("terms_url"))
    privacy_ver = _extract_doc_version(data.get("privacy_url"))
    disclaimer_ver = _extract_doc_version(data.get("disclaimer_url"))
    return (
        "<b>Юридические документы</b>\n\n"
        f"Дата вступления (МСК): <code>{effective}</code>\n\n"
        f"Соглашение ({terms_ver}): {data.get('terms_url')}\n"
        f"Политика ({privacy_ver}): {data.get('privacy_url')}\n"
        f"Дисклеймер ({disclaimer_ver}): {data.get('disclaimer_url')}\n\n"
        "💡 <b>Совет:</b> Вы можете просто отправить боту файл <code>.docx</code>, чтобы автоматически загрузить, сконвертировать в HTML и обновить любой из документов с инкрементом версии!"
    )


def _format_admins(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<b>Админы</b>\n\nСписок пуст."
    lines = ["<b>Админы</b>", ""]
    for row in rows:
        role = "superadmin" if row.get("is_superadmin") else "admin"
        status = "active" if row.get("is_active") else "disabled"
        lines.append(f"• <code>{row.get('telegram_id')}</code> — {role}, {status}")
    return "\n".join(lines)


def _broadcast_legal_notice(db, token: str, text: str) -> dict[str, int]:
    current = admin_ops.legal_current(db)
    payload = (
        f"{text.strip()}\n\n"
        f"Версия: <code>{current['version']}</code>\n"
        f"Вступает в силу (МСК): <code>{current.get('effective_at_msk') or 'не задано'}</code>\n"
        f"Соглашение: {current['terms_url']}\n"
        f"Политика: {current['privacy_url']}\n"
        f"Дисклеймер: {current['disclaimer_url']}"
    )
    sent = 0
    failed = 0
    for chat_id in admin_ops.broadcast_targets(db):
        r = _tg_post(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=_truncate(payload),
            parse_mode=PARSE_MODE,
            disable_web_page_preview=True,
        )
        if r.get("ok"):
            sent += 1
        else:
            failed += 1
    return {"sent": sent, "failed": failed}


def _edit_or_send(
    token: str,
    chat_id: int,
    message_id: int,
    text: str,
    reply_markup: dict | None,
) -> None:
    text = _truncate(text)
    r = _tg_post(
        token,
        "editMessageText",
        chat_id=chat_id,
        message_id=message_id,
        text=text,
        parse_mode=PARSE_MODE,
        reply_markup=reply_markup,
    )
    if not r.get("ok"):
        _tg_post(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode=PARSE_MODE,
            reply_markup=reply_markup,
        )


def _handle_callback(data: str, uid: int, chat_id: int, mid: int, token: str) -> None:
    db = SessionLocal()
    try:
        if data.startswith("upload:"):
            _handle_upload_callback(data, uid, chat_id, mid, token, db)
            return

        if data == "m:main":
            text = ru.main_menu_text()
            if not crypto_configured():
                text += "\n\n⚠️ <code>CRYPTO_KEY</code> не задан — запись ключей в БД недоступна."
            _edit_or_send(token, chat_id, mid, text, _kb_main())
            return

        if data == "m:keys":
            _edit_or_send(token, chat_id, mid, "<b>Ключи API</b>\n\nВыберите действие.", _kb_keys())
            return

        if data == "m:cache":
            _edit_or_send(token, chat_id, mid, "<b>Кэш SStats</b>\n\nСтатистика, очистка или TTL.", _kb_cache())
            return

        if data == "m:set":
            _edit_or_send(token, chat_id, mid, "<b>Настройки системы</b>", _kb_settings())
            return

        if data == "m:legal":
            cur = admin_ops.legal_current(db)
            _edit_or_send(token, chat_id, mid, _format_legal_current(cur), _kb_legal())
            return

        if data == "m:admins":
            rows = admin_ops.admins_list(db)
            _edit_or_send(token, chat_id, mid, _format_admins(rows), _kb_admins())
            return

        if data == "m:mon":
            mon_window = "7d"
            snap = admin_ops.monitoring_dashboard(db, mode=mon_window)
            text = ru.format_monitoring(snap)
            _edit_or_send(token, chat_id, mid, text, _kb_mon_window(mon_window))
            return

        if data == "w:7":
            snap = admin_ops.monitoring_dashboard(db, mode="7d")
            _edit_or_send(token, chat_id, mid, ru.format_monitoring(snap), _kb_mon_window("7d"))
            return

        if data == "w:a":
            snap = admin_ops.monitoring_dashboard(db, mode="all")
            _edit_or_send(token, chat_id, mid, ru.format_monitoring(snap), _kb_mon_window("all"))
            return

        if data == "k:v":
            kv = admin_ops.keys_view()
            _edit_or_send(token, chat_id, mid, ru.format_keys_summary(kv), _kb_keys())
            return

        if data == "k:val":
            out = admin_ops.validate_keys_op(db)
            _edit_or_send(token, chat_id, mid, ru.format_validate_result(out), _kb_keys())
            return

        if data == "k:s":
            if not crypto_configured():
                _edit_or_send(
                    token,
                    chat_id,
                    mid,
                    ru.format_err("Задайте CRYPTO_KEY для записи ключей в БД."),
                    _kb_keys(),
                )
                return
            bot_state.set_state(uid, "sstats_key")
            _edit_or_send(token, chat_id, mid, ru.prompt_sstats_key(), _kb_keys())
            return

        if data == "c:st":
            st = sstats_cache.stats()
            _edit_or_send(token, chat_id, mid, ru.format_cache_stats(st), _kb_cache())
            return

        if data == "c:all":
            out = admin_ops.cache_clear_op(db, None)
            _edit_or_send(token, chat_id, mid, ru.format_cache_clear_result(out), _kb_cache())
            return

        if data.startswith("c:s:"):
            scope = data[4:].strip()
            if scope not in CACHE_SCOPES:
                _edit_or_send(token, chat_id, mid, ru.format_err("Неизвестный scope."), _kb_cache())
                return
            out = admin_ops.cache_clear_op(db, scope)
            _edit_or_send(token, chat_id, mid, ru.format_cache_clear_result(out), _kb_cache())
            return

        if data == "c:ttl":
            bot_state.set_state(uid, "cache_ttl")
            _edit_or_send(token, chat_id, mid, ru.prompt_cache_ttl(), _kb_cache())
            return

        if data == "s:show":
            row = admin_ops.ensure_app_settings(db)
            _edit_or_send(token, chat_id, mid, ru.format_settings_row(row), _kb_settings())
            return

        if data == "s:sync":
            out = admin_ops.run_sync_op(db, uid, True)
            _edit_or_send(token, chat_id, mid, ru.format_sync_result(out), _kb_settings())
            return

        if data == "s:rl":
            bot_state.set_state(uid, "rate_limit")
            _edit_or_send(token, chat_id, mid, ru.prompt_rate_limit(), _kb_settings())
            return

        if data == "s:ttl":
            bot_state.set_state(uid, "cache_ttl")
            _edit_or_send(token, chat_id, mid, ru.prompt_cache_ttl(), _kb_settings())
            return

        if data == "s:fl":
            t = admin_ops.toggle_leagues_section(db, uid)
            on = t.get("leagues", True)
            _edit_or_send(
                token,
                chat_id,
                mid,
                ru.format_ok(f"Раздел «Лиги»: {'включён' if on else 'выключен'}"),
                _kb_settings(),
            )
            return

        if data == "s:n":
            t = admin_ops.toggle_notifications_enabled(db, uid)
            on = t.get("notifications_enabled", True)
            _edit_or_send(
                token,
                chat_id,
                mid,
                ru.format_ok(f"Уведомления: {'вкл' if on else 'выкл'}"),
                _kb_settings(),
            )
            return

        if data == "s:sc":
            t = admin_ops.toggle_sstats_cache_enabled(db, uid)
            on = t.get("sstats_cache_enabled", True)
            _edit_or_send(
                token,
                chat_id,
                mid,
                ru.format_ok(f"Кэш SStats: {'вкл' if on else 'выкл'}"),
                _kb_settings(),
            )
            return

        # ─── Subscription menu ─────────────────────────────────────────────────
        if data == "m:sub":
            _edit_or_send(token, chat_id, mid, "<b>💳 Подписки и платежи</b>", _kb_sub())
            return

        if data == "sub:stat":
            from app.models import Subscription, Payment
            subs_count = db.query(Subscription).filter(Subscription.status == "active").count()
            total_subs = db.query(Subscription).count()
            succeeded_count = db.query(Payment).filter(Payment.status == "succeeded").count()
            settings = db.query(__import__("app.models", fromlist=["AppSettings"]).AppSettings).filter_by(id=1).first()
            from app.services.billing_prices import DEFAULT_PRICE_RUB, get_regular_price
            price = float(get_regular_price(settings))
            mrr = round(subs_count * price, 2)
            text = (
                f"<b>📊 Статистика подписок</b>\n\n"
                f"Активных подписок: <b>{subs_count}</b>\n"
                f"Всего подписок: <b>{total_subs}</b>\n"
                f"Успешных платежей: <b>{succeeded_count}</b>\n"
                f"MRR: <b>{mrr} ₽</b>"
            )
            _edit_or_send(token, chat_id, mid, text, _kb_sub())
            return

        if data == "sub:pay":
            from app.models import Payment, User
            payments = (
                db.query(Payment)
                .order_by(Payment.created_at.desc())
                .limit(10)
                .all()
            )
            lines = ["<b>💳 Последние 10 платежей</b>\n"]
            for p in payments:
                user = db.query(User).filter(User.id == p.user_id).first()
                tg = user.telegram_id if user else "?"
                lines.append(
                    f"#{p.id} | tg={tg} | {p.kind} | {p.status} | {p.amount_value}₽ | "
                    f"{p.created_at.strftime('%d.%m %H:%M') if p.created_at else '?'}"
                )
            _edit_or_send(token, chat_id, mid, "\n".join(lines), _kb_sub())
            return

        if data == "sub:price":
            bot_state.set_state(uid, "sub_price")
            _edit_or_send(token, chat_id, mid, "Введите новую цену подписки в рублях (например: 480):", _kb_sub())
            return

        if data == "sub:period":
            bot_state.set_state(uid, "sub_period")
            _edit_or_send(token, chat_id, mid, "Введите длину периода в днях (например: 30):", _kb_sub())
            return

        if data == "sub:free":
            bot_state.set_state(uid, "sub_free")
            settings = db.query(__import__("app.models", fromlist=["AppSettings"]).AppSettings).filter_by(id=1).first()
            current = settings.free_league_keys_csv if settings else "epl,rpl"
            _edit_or_send(
                token, chat_id, mid,
                f"Текущие бесплатные лиги: <code>{current}</code>\n\nВведите ключи через запятую (например: epl,rpl):",
                _kb_sub(),
            )
            return

        if data == "sub:retry":
            bot_state.set_state(uid, "sub_retry")
            _edit_or_send(token, chat_id, mid, "Введите retry-окно в днях (например: 3):", _kb_sub())
            return

        if data == "sub:cancel_uid":
            bot_state.set_state(uid, "sub_cancel_uid")
            _edit_or_send(token, chat_id, mid, "Введите telegram_id пользователя для отмены подписки:", _kb_sub())
            return

        if data == "legal:show":
            cur = admin_ops.legal_current(db)
            _edit_or_send(token, chat_id, mid, _format_legal_current(cur), _kb_legal())
            return

        if data == "legal:stat":
            st = admin_ops.legal_acceptance_stats(db)
            _edit_or_send(
                token,
                chat_id,
                mid,
                f"<b>Акцепты</b>\n\nПользователей с акцептом: <b>{st['accepted_users']}</b>",
                _kb_legal(),
            )
            return

        if data == "legal:help":
            help_text = (
                "<b>📝 Инструкция по обновлению документов</b>\n\n"
                "Чтобы обновить любой из юридических документов:\n"
                "1. Просто <b>отправьте .docx файл</b> в этот чат.\n"
                "2. Бот предложит выбрать тип документа (Соглашение, Политика, Дисклеймер).\n"
                "3. Бот автоматически:\n"
                "   • Сконвертирует документ в красивый адаптивный HTML с поддержкой темной темы.\n"
                "   • Сохранит его на сервере.\n"
                "   • Автоматически увеличит версию (например, с v1 до v2).\n"
                "   • Сделает новую версию активной с датой вступления минимум через 7 дней.\n"
                "   • Автоматически отправит уведомление активным пользователям."
            )
            _edit_or_send(token, chat_id, mid, help_text, _kb_legal())
            return

        if data == "legal:terms":
            bot_state.set_state(uid, "legal_terms_url")
            _edit_or_send(token, chat_id, mid, "Отправьте новую ссылку на пользовательское соглашение.", _kb_legal())
            return

        if data == "legal:privacy":
            bot_state.set_state(uid, "legal_privacy_url")
            _edit_or_send(token, chat_id, mid, "Отправьте новую ссылку на политику конфиденциальности.", _kb_legal())
            return

        if data == "legal:disclaimer":
            bot_state.set_state(uid, "legal_disclaimer_url")
            _edit_or_send(token, chat_id, mid, "Отправьте новую ссылку на дисклеймер.", _kb_legal())
            return

        if data == "legal:version":
            bot_state.set_state(uid, "legal_version")
            _edit_or_send(token, chat_id, mid, "Отправьте новую версию документов (например: v2).", _kb_legal())
            return

        if data == "legal:effective":
            bot_state.set_state(uid, "legal_effective_at")
            _edit_or_send(
                token,
                chat_id,
                mid,
                "Отправьте дату вступления в формате YYYY-MM-DD HH:MM (МСК).\nПример: <code>2026-07-01 12:00</code>",
                _kb_legal(),
            )
            return

        if data == "legal:broadcast":
            bot_state.set_state(uid, "legal_broadcast_text")
            _edit_or_send(
                token,
                chat_id,
                mid,
                "Отправьте текст рассылки об изменениях документов.",
                _kb_legal(),
            )
            return

        if data == "admins:list":
            rows = admin_ops.admins_list(db)
            _edit_or_send(token, chat_id, mid, _format_admins(rows), _kb_admins())
            return

        if data == "admins:add":
            bot_state.set_state(uid, "admin_add_tg_id")
            _edit_or_send(token, chat_id, mid, "Введите Telegram ID админа для добавления.", _kb_admins())
            return

        if data == "admins:remove":
            bot_state.set_state(uid, "admin_remove_tg_id")
            _edit_or_send(token, chat_id, mid, "Введите Telegram ID админа для отключения.", _kb_admins())
            return

        _edit_or_send(token, chat_id, mid, ru.format_err("Неизвестная команда."), _kb_main())
    finally:
        db.close()


def _handle_private_message(uid: int, chat_id: int, text: str, token: str) -> None:
    bot_state.prune_expired()
    st = bot_state.get_state(uid)
    if not st:
        return

    db = SessionLocal()
    try:
        if st.kind == "sstats_key":
            bot_state.clear_state(uid)
            if not crypto_configured():
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err("CRYPTO_KEY не задан."),
                    parse_mode=PARSE_MODE,
                )
                return
            raw = text.strip()
            sstats_val = "" if raw == "-" else raw
            try:
                admin_ops.put_keys_op(db, sstats_val, uid)
            except ValueError as e:
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err(str(e)),
                    parse_mode=PARSE_MODE,
                )
                return
            _tg_post(
                token,
                "sendMessage",
                chat_id=chat_id,
                text=ru.format_ok("Ключ SStats обновлён в базе."),
                parse_mode=PARSE_MODE,
            )
            return

        if st.kind == "cache_ttl":
            bot_state.clear_state(uid)
            try:
                v = int(text.strip())
            except ValueError:
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err("Нужно целое число секунд."),
                    parse_mode=PARSE_MODE,
                )
                return
            if v < 30 or v > 86400:
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err("Допустимо от 30 до 86400 секунд."),
                    parse_mode=PARSE_MODE,
                )
                return
            admin_ops.put_settings_op(db, uid, cache_ttl_seconds=v)
            _tg_post(
                token,
                "sendMessage",
                chat_id=chat_id,
                text=ru.format_ok(f"TTL кэша: {v} с"),
                parse_mode=PARSE_MODE,
            )
            return

        if st.kind == "rate_limit":
            bot_state.clear_state(uid)
            try:
                v = int(text.strip())
            except ValueError:
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err("Нужно целое число."),
                    parse_mode=PARSE_MODE,
                )
                return
            if v < 0 or v > 10000:
                _tg_post(
                    token,
                    "sendMessage",
                    chat_id=chat_id,
                    text=ru.format_err("Допустимо от 0 до 10000."),
                    parse_mode=PARSE_MODE,
                )
                return
            admin_ops.put_settings_op(db, uid, rate_limit_per_minute=v)
            _tg_post(
                token,
                "sendMessage",
                chat_id=chat_id,
                text=ru.format_ok(f"Лимит: {v} запросов/мин с IP"),
                parse_mode=PARSE_MODE,
            )
            return

        if st.kind == "sub_price":
            bot_state.clear_state(uid)
            from decimal import Decimal
            try:
                v = Decimal(text.strip().replace(",", "."))
                if v <= 0 or v > 100000:
                    raise ValueError("out of range")
            except Exception:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Некорректная цена."), parse_mode=PARSE_MODE)
                return
            from app.models import AppSettings
            settings = db.query(AppSettings).filter_by(id=1).first()
            if settings:
                settings.subscription_price_rub = v
                db.commit()
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Цена подписки: {v} ₽"), parse_mode=PARSE_MODE)
            return

        if st.kind == "sub_period":
            bot_state.clear_state(uid)
            try:
                v = int(text.strip())
                if v < 1 or v > 365:
                    raise ValueError("out of range")
            except Exception:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Нужно число от 1 до 365."), parse_mode=PARSE_MODE)
                return
            from app.models import AppSettings
            settings = db.query(AppSettings).filter_by(id=1).first()
            if settings:
                settings.subscription_period_days = v
                db.commit()
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Период подписки: {v} дней"), parse_mode=PARSE_MODE)
            return

        if st.kind == "sub_free":
            bot_state.clear_state(uid)
            keys_csv = ",".join(k.strip() for k in text.strip().split(",") if k.strip())
            from app.models import AppSettings
            settings = db.query(AppSettings).filter_by(id=1).first()
            if settings:
                settings.free_league_keys_csv = keys_csv
                db.commit()
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Бесплатные лиги: {keys_csv}"), parse_mode=PARSE_MODE)
            return

        if st.kind == "sub_retry":
            bot_state.clear_state(uid)
            try:
                v = int(text.strip())
                if v < 1 or v > 30:
                    raise ValueError("out of range")
            except Exception:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Нужно число от 1 до 30."), parse_mode=PARSE_MODE)
                return
            from app.models import AppSettings
            settings = db.query(AppSettings).filter_by(id=1).first()
            if settings:
                settings.recurring_retry_days = v
                db.commit()
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Retry-окно: {v} дней"), parse_mode=PARSE_MODE)
            return

        if st.kind == "sub_cancel_uid":
            bot_state.clear_state(uid)
            try:
                target_tg_id = int(text.strip())
            except ValueError:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Нужен числовой telegram_id."), parse_mode=PARSE_MODE)
                return
            from app.models import User, Subscription
            from datetime import datetime
            target_user = db.query(User).filter(User.telegram_id == target_tg_id).first()
            if not target_user:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err(f"Пользователь tg={target_tg_id} не найден."), parse_mode=PARSE_MODE)
                return
            sub = db.query(Subscription).filter(Subscription.user_id == target_user.id).first()
            if not sub:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("У пользователя нет подписки."), parse_mode=PARSE_MODE)
                return
            sub.status = "canceled"
            sub.cancel_at_period_end = True
            sub.canceled_at = datetime.utcnow()
            db.commit()
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Подписка пользователя tg={target_tg_id} отменена."), parse_mode=PARSE_MODE)
            return

        if st.kind == "legal_terms_url":
            bot_state.clear_state(uid)
            cur = admin_ops.legal_current(db)
            out = admin_ops.legal_update_active(
                db,
                telegram_user_id=uid,
                version=cur["version"],
                terms_url=text.strip(),
                privacy_url=cur["privacy_url"],
                disclaimer_url=cur["disclaimer_url"],
                effective_at_msk=datetime.fromisoformat(cur["effective_at_msk"]) if cur["effective_at_msk"] else None,
            )
            _tg_post(token, "sendMessage", chat_id=chat_id, text=f"✓ Ссылка обновлена.\n\n{_format_legal_current(out)}", parse_mode=PARSE_MODE, disable_web_page_preview=True)
            return

        if st.kind == "legal_privacy_url":
            bot_state.clear_state(uid)
            cur = admin_ops.legal_current(db)
            out = admin_ops.legal_update_active(
                db,
                telegram_user_id=uid,
                version=cur["version"],
                terms_url=cur["terms_url"],
                privacy_url=text.strip(),
                disclaimer_url=cur["disclaimer_url"],
                effective_at_msk=datetime.fromisoformat(cur["effective_at_msk"]) if cur["effective_at_msk"] else None,
            )
            _tg_post(token, "sendMessage", chat_id=chat_id, text=f"✓ Ссылка обновлена.\n\n{_format_legal_current(out)}", parse_mode=PARSE_MODE, disable_web_page_preview=True)
            return

        if st.kind == "legal_disclaimer_url":
            bot_state.clear_state(uid)
            cur = admin_ops.legal_current(db)
            out = admin_ops.legal_update_active(
                db,
                telegram_user_id=uid,
                version=cur["version"],
                terms_url=cur["terms_url"],
                privacy_url=cur["privacy_url"],
                disclaimer_url=text.strip(),
                effective_at_msk=datetime.fromisoformat(cur["effective_at_msk"]) if cur["effective_at_msk"] else None,
            )
            _tg_post(token, "sendMessage", chat_id=chat_id, text=f"✓ Ссылка обновлена.\n\n{_format_legal_current(out)}", parse_mode=PARSE_MODE, disable_web_page_preview=True)
            return

        if st.kind == "legal_version":
            bot_state.clear_state(uid)
            version = text.strip()
            if not version:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Версия не может быть пустой."), parse_mode=PARSE_MODE)
                return
            cur = admin_ops.legal_current(db)
            out = admin_ops.legal_update_active(
                db,
                telegram_user_id=uid,
                version=version,
                terms_url=cur["terms_url"],
                privacy_url=cur["privacy_url"],
                disclaimer_url=cur["disclaimer_url"],
                effective_at_msk=datetime.fromisoformat(cur["effective_at_msk"]) if cur["effective_at_msk"] else None,
            )
            _tg_post(token, "sendMessage", chat_id=chat_id, text=f"✓ Активирована версия {version}.\n\n{_format_legal_current(out)}", parse_mode=PARSE_MODE, disable_web_page_preview=True)
            return

        if st.kind == "legal_effective_at":
            bot_state.clear_state(uid)
            try:
                dt = datetime.strptime(text.strip(), "%Y-%m-%d %H:%M")
            except ValueError:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Формат даты: YYYY-MM-DD HH:MM"), parse_mode=PARSE_MODE)
                return
            from app.services import legal
            min_allowed = legal.minimum_effective_at_msk()
            if dt < min_allowed:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Дата вступления должна быть минимум через 7 дней."), parse_mode=PARSE_MODE)
                return
            cur = admin_ops.legal_current(db)
            out = admin_ops.legal_update_active(
                db,
                telegram_user_id=uid,
                version=cur["version"],
                terms_url=cur["terms_url"],
                privacy_url=cur["privacy_url"],
                disclaimer_url=cur["disclaimer_url"],
                effective_at_msk=dt,
            )
            _tg_post(token, "sendMessage", chat_id=chat_id, text=f"✓ Дата вступления обновлена.\n\n{_format_legal_current(out)}", parse_mode=PARSE_MODE, disable_web_page_preview=True)
            return

        if st.kind == "legal_broadcast_text":
            bot_state.clear_state(uid)
            out = _broadcast_legal_notice(db, token, text)
            _tg_post(
                token,
                "sendMessage",
                chat_id=chat_id,
                text=ru.format_ok(f"Рассылка завершена. Отправлено: {out['sent']}, ошибок: {out['failed']}"),
                parse_mode=PARSE_MODE,
            )
            return

        if st.kind == "admin_add_tg_id":
            bot_state.clear_state(uid)
            try:
                target_tg_id = int(text.strip())
            except ValueError:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Нужен числовой Telegram ID."), parse_mode=PARSE_MODE)
                return
            out = admin_ops.add_admin_op(db, uid, target_tg_id)
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Админ добавлен: {out['telegram_id']}"), parse_mode=PARSE_MODE)
            return

        if st.kind == "admin_remove_tg_id":
            bot_state.clear_state(uid)
            try:
                target_tg_id = int(text.strip())
            except ValueError:
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Нужен числовой Telegram ID."), parse_mode=PARSE_MODE)
                return
            out = admin_ops.remove_admin_op(db, uid, target_tg_id)
            if not out.get("ok"):
                _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_err("Админ не найден."), parse_mode=PARSE_MODE)
                return
            _tg_post(token, "sendMessage", chat_id=chat_id, text=ru.format_ok(f"Админ отключен: {target_tg_id}"), parse_mode=PARSE_MODE)
            return
    finally:
        db.close()


def process_admin_update(update: dict) -> None:
    token = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    if not token:
        logger.warning("ADMIN_BOT_TOKEN not set")
        return

    if cb := update.get("callback_query"):
        uid = cb.get("from", {}).get("id")
        msg = cb.get("message") or {}
        chat = msg.get("chat") or {}
        if chat.get("type") != "private":
            return
        if uid is None:
            return
        if not _allowed(int(uid)):
            _tg_post(
                token,
                "answerCallbackQuery",
                callback_query_id=cb["id"],
                text="Доступ запрещён",
                show_alert=True,
            )
            return
        _tg_post(token, "answerCallbackQuery", callback_query_id=cb["id"])
        data = (cb.get("data") or "")[:64]
        chat_id = chat["id"]
        mid = msg.get("message_id")
        if mid is None:
            return
        _handle_callback(data, int(uid), int(chat_id), int(mid), token)
        return

    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    chat = msg.get("chat") or {}
    if chat.get("type") != "private":
        return
    uid = msg.get("from", {}).get("id")
    chat_id = chat["id"]
    if uid is None or not _allowed(int(uid)):
        _tg_post(
            token,
            "sendMessage",
            chat_id=chat_id,
            text="Доступ запрещён.",
            parse_mode=PARSE_MODE,
        )
        return

    document = msg.get("document")
    if document:
        _handle_document_upload(int(uid), int(chat_id), document, token)
        return

    text = (msg.get("text") or "").strip()
    if text == "/start":
        body = ru.main_menu_text()
        if not crypto_configured():
            body += "\n\n⚠️ <code>CRYPTO_KEY</code> не задан — запись ключей в БД недоступна."
        _tg_post(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=body,
            parse_mode=PARSE_MODE,
            reply_markup=_kb_main(),
        )
        return

    _handle_private_message(int(uid), int(chat_id), text, token)


_uploaded_files: dict[int, dict[str, Any]] = {}


def _handle_document_upload(uid: int, chat_id: int, document: dict[str, Any], token: str) -> None:
    file_name = document.get("file_name", "")
    if not file_name.lower().endswith(".docx"):
        _tg_post(
            token,
            "sendMessage",
            chat_id=chat_id,
            text=ru.format_err("Пожалуйста, отправьте файл в формате .docx (MS Word)."),
            parse_mode=PARSE_MODE,
        )
        return

    _uploaded_files[uid] = {
        "file_id": document["file_id"],
        "file_name": file_name,
    }

    kb = {
        "inline_keyboard": [
            [
                {"text": "Пользовательское соглашение (Terms)", "callback_data": "upload:terms"},
            ],
            [
                {"text": "Политика конфиденциальности (Privacy)", "callback_data": "upload:privacy"},
            ],
            [
                {"text": "Дисклеймер (Disclaimer)", "callback_data": "upload:disclaimer"},
            ],
            [
                {"text": "❌ Отмена", "callback_data": "upload:cancel"},
            ]
        ]
    }

    _tg_post(
        token,
        "sendMessage",
        chat_id=chat_id,
        text=(
            f"Вы прислали файл <b>{ru.esc(file_name)}</b>.\n\n"
            "Какой юридический документ вы хотите обновить этим файлом?"
        ),
        parse_mode=PARSE_MODE,
        reply_markup=kb,
    )


def _download_file(token: str, file_path: str) -> bytes | None:
    url = f"{TELEGRAM_API}/file/bot{token}/{file_path}"
    proxy = _get_proxy()
    try:
        with httpx.Client(proxy=proxy, timeout=60.0) as client:
            r = client.get(url)
            if r.status_code == 200:
                return r.content
    except Exception as e:
        logger.error("Failed to download file from Telegram: %s", e)
    return None


def _get_next_doc_version(doc_type: str) -> str:
    base_dir = Path("/data/legal") / doc_type
    if not Path("/data").is_dir():
        base_dir = Path(__file__).parent.parent / "data" / "legal" / doc_type
    
    if not base_dir.is_dir():
        return "v1"
        
    max_num = 0
    for f in base_dir.glob("*.html"):
        name = f.stem
        if name.startswith("v") and name[1:].isdigit():
            try:
                num = int(name[1:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"v{max_num + 1}"


def _get_next_version_string(db) -> str:
    from app.models import LegalDocumentVersion
    versions = db.query(LegalDocumentVersion.version).all()
    max_num = 0
    for (v,) in versions:
        if v.startswith("v") and v[1:].isdigit():
            try:
                num = int(v[1:])
                if num > max_num:
                    max_num = num
            except ValueError:
                pass
    return f"v{max_num + 1}"


def _handle_upload_callback(data: str, uid: int, chat_id: int, mid: int, token: str, db) -> None:
    doc_type = data.split(":")[1]
    if doc_type == "cancel":
        _uploaded_files.pop(uid, None)
        _edit_or_send(token, chat_id, mid, "Загрузка документа отменена.", None)
        return

    info = _uploaded_files.pop(uid, None)
    if not info:
        _edit_or_send(token, chat_id, mid, ru.format_err("Файл не найден. Пожалуйста, отправьте файл .docx заново."), None)
        return

    file_id = info["file_id"]
    file_name = info["file_name"]

    _edit_or_send(token, chat_id, mid, f"⏳ Загрузка и обработка файла <b>{ru.esc(file_name)}</b>...", None)

    # 1. Get file path from Telegram
    file_info = _tg_post(token, "getFile", file_id=file_id)
    if not file_info.get("ok"):
        _edit_or_send(token, chat_id, mid, ru.format_err("Не удалось получить информацию о файле от Telegram."), None)
        return

    file_path_tg = file_info.get("result", {}).get("file_path")
    if not file_path_tg:
        _edit_or_send(token, chat_id, mid, ru.format_err("Путь к файлу отсутствует в ответе Telegram."), None)
        return

    # 2. Download file
    file_bytes = _download_file(token, file_path_tg)
    if not file_bytes:
        _edit_or_send(token, chat_id, mid, ru.format_err("Не удалось скачать файл от Telegram."), None)
        return

    # 3. Convert DOCX to HTML
    try:
        result = mammoth.convert_to_html(io.BytesIO(file_bytes))
        html_content = result.value
        
        # Wrap in styled template
        styled_html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{ru.esc(file_name)}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #111827;
            background-color: #ffffff;
            max-width: 680px;
            margin: 0 auto;
            padding: 24px 16px;
        }}
        h1, h2, h3 {{
            color: #0f172a;
            margin-top: 28px;
            margin-bottom: 12px;
            font-weight: 700;
        }}
        h1 {{ font-size: 22px; border-bottom: 1px solid #e2e8f0; padding-bottom: 8px; }}
        h2 {{ font-size: 18px; }}
        h3 {{ font-size: 16px; }}
        p {{
            margin-top: 0;
            margin-bottom: 16px;
            text-align: justify;
        }}
        ol, ul {{
            margin-top: 0;
            margin-bottom: 16px;
            padding-left: 24px;
        }}
        li {{
            margin-bottom: 8px;
        }}
        @media (prefers-color-scheme: dark) {{
            body {{
                color: #e2e8f0;
                background-color: #0f172a;
            }}
            h1, h2, h3 {{
                color: #f8fafc;
            }}
            h1 {{ border-bottom-color: #334155; }}
        }}
    </style>
</head>
<body>
    {html_content}
</body>
</html>
"""
    except Exception as e:
        logger.error("Failed to convert docx to HTML: %s", e, exc_info=True)
        _edit_or_send(token, chat_id, mid, ru.format_err(f"Ошибка конвертации файла: {e}"), None)
        return

    # 4. Save HTML to persistent disk
    from app.services import legal
    
    next_doc_version = _get_next_doc_version(doc_type)
    next_global_version = _get_next_version_string(db)
    
    # Check persistent /data directory first
    base_dir = Path("/data/legal") / doc_type
    if not Path("/data").is_dir():
        base_dir = Path(__file__).parent.parent / "data" / "legal" / doc_type
        
    try:
        os.makedirs(base_dir, exist_ok=True)
        file_path_local = base_dir / f"{next_doc_version}.html"
        file_path_local.write_text(styled_html, encoding="utf-8")
    except Exception as e:
        logger.error("Failed to save HTML file: %s", e, exc_info=True)
        _edit_or_send(token, chat_id, mid, ru.format_err(f"Не удалось сохранить HTML-файл на сервере: {e}"), None)
        return

    # 5. Create new database version
    web_app_url = (os.getenv("WEB_APP_URL", "").strip()).rstrip("/")
    new_url = f"{web_app_url}/legal/{doc_type}/{next_doc_version}"
    
    active = legal.get_active_legal_document(db)
    terms_url = active.terms_url
    privacy_url = active.privacy_url
    disclaimer_url = active.disclaimer_url
    
    if doc_type == "terms":
        terms_url = new_url
    elif doc_type == "privacy":
        privacy_url = new_url
    elif doc_type == "disclaimer":
        disclaimer_url = new_url

    try:
        new_doc = legal.upsert_active_legal_document(
            db,
            actor_tg_id=uid,
            version=next_global_version,
            terms_url=terms_url,
            privacy_url=privacy_url,
            disclaimer_url=disclaimer_url,
            effective_at_msk=legal.minimum_effective_at_msk(),
        )
    except Exception as e:
        logger.error("Failed to save new version to DB: %s", e, exc_info=True)
        _edit_or_send(token, chat_id, mid, ru.format_err(f"Не удалось записать новую версию в БД: {e}"), None)
        return

    # 6. Success message
    doc_type_ru = {
        "terms": "Пользовательское соглашение",
        "privacy": "Политика конфиденциальности",
        "disclaimer": "Дисклеймер"
    }.get(doc_type, doc_type)

    success_text = (
        f"<b>✓ Документ успешно обновлен!</b>\n\n"
        f"Тип: <code>{doc_type_ru}</code>\n"
        f"Версия: <code>{next_doc_version}</code>\n"
        f"Ссылка: {new_url}\n\n"
        f"Вступает в силу: <code>{new_doc.effective_at_msk.strftime('%Y-%m-%d %H:%M') if new_doc.effective_at_msk else 'не указано'} МСК</code>\n"
        f"Уведомление активным пользователям отправлено автоматически."
    )
    _edit_or_send(token, chat_id, mid, success_text, _kb_legal())

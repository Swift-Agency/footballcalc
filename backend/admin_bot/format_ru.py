"""
Russian copy and HTML formatting for Telegram admin bot (parse_mode HTML).
"""
from __future__ import annotations

import html
import json
from typing import Any


def esc(s: str | None) -> str:
    return html.escape(s or "", quote=True)


def format_keys_summary(data: dict[str, Any]) -> str:
    """data from admin_ops.keys_view()."""
    s = data.get("sstats") or {}
    lines = [
        "<b>API-ключи (SStats)</b>",
        "",
        f"Ключ: {'задан' if s.get('set') else 'не задан'} — <code>{esc(s.get('masked') or '—')}</code>",
        "",
        f"Шифрование БД: {'да' if data.get('crypto_configured') else 'нет (нужен CRYPTO_KEY)'}",
        f"Переменная SSTATS_API_KEY: {'да' if data.get('env_sstats_set') else 'нет'}",
    ]
    return "\n".join(lines)


def _window_label(mode: str) -> str:
    return "за 7 дней" if mode == "7d" else "за всё время"


def format_monitoring(data: dict[str, Any]) -> str:
    """data from admin_analytics.monitoring_snapshot + optional error summary."""
    mode = data.get("window", "7d")
    ext = data.get("external") or {}
    users = data.get("telegram_users", 0)
    pv = data.get("page_views_top") or []
    searches = data.get("searches_top") or []
    sorts = data.get("sort_top") or []

    def pack(name: str, d: dict[str, Any]) -> list[str]:
        out = [
            f"\n<b>{name}</b>",
            f"всего запросов: {d.get('total', 0)}",
            f"успешно: {d.get('success', 0)}",
            f"ошибки сети/прочее: {d.get('errors', 0)}",
            f"HTTP 4xx: {d.get('http_4xx', 0)} · 5xx: {d.get('http_5xx', 0)} · 429: {d.get('http_429', 0)}",
            f"средняя задержка: {d.get('avg_latency_ms', 0)} мс",
        ]
        errs = d.get("last_errors") or []
        if errs:
            out.append("последние ошибки:")
            for e in errs[:5]:
                out.append(f"  • <code>{esc(str(e)[:400])}</code>")
        return out

    lines = [
        "<b>Мониторинг</b>",
        f"Период событий: {_window_label(mode)}",
        f"Пользователей (уникальных): {users}",
    ]
    ss = ext.get("sstats") or {}
    lines += pack("SStats", ss)

    lines.append("\n<b>Разделы (page_view)</b>")
    if not pv:
        lines.append("нет данных")
    else:
        for path, n in pv:
            lines.append(f"• <code>{esc(path)}</code> — {n}")

    lines.append("\n<b>Популярные поиски</b>")
    if not searches:
        lines.append("нет данных")
    else:
        for q, n in searches:
            lines.append(f"• {esc(q)} — {n}")

    lines.append("\n<b>Сортировка (события)</b>")
    if not sorts:
        lines.append("нет данных")
    else:
        for label, n in sorts:
            lines.append(f"• <code>{esc(label)}</code> — {n}")

    return "\n".join(lines)


def format_cache_stats(stats: dict[str, Any]) -> str:
    scopes = stats.get("scopes") or {}
    lines = [
        "<b>Кэш SStats</b>",
        f"попадания: {stats.get('hits', 0)}",
        f"промахи: {stats.get('misses', 0)}",
        f"hit rate: {stats.get('hit_rate_pct', 0)}%",
        "",
        "<b>Записей по scope</b>",
    ]
    if not scopes:
        lines.append("(пусто)")
    else:
        for k, v in sorted(scopes.items()):
            lines.append(f"• <code>{esc(k)}</code>: {v}")
    return "\n".join(lines)


def format_settings_row(row: Any) -> str:
    flags = getattr(row, "feature_flags_json", None) or "{}"
    try:
        parsed = json.loads(flags)
        flags_fmt = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        flags_fmt = flags
    return "\n".join(
        [
            "<b>Настройки</b>",
            f"TTL кэша: {row.cache_ttl_seconds} с",
            f"Кэш SStats: {'вкл' if row.sstats_cache_enabled else 'выкл'}",
            f"Лимит запросов/мин (IP): {row.rate_limit_per_minute} (0 = без лимита)",
            f"Уведомления админам: {'вкл' if row.notifications_enabled else 'выкл'}",
            "",
            "<b>Флаги разделов</b> (JSON):",
            f"<pre>{esc(flags_fmt)}</pre>",
        ]
    )


def format_validate_result(data: dict[str, Any]) -> str:
    lines = ["<b>Проверка ключа SStats</b>", "", "<code>GET /Account/Info?apikey=…</code>", ""]
    s = data.get("sstats") or {}
    if s.get("ok") is True:
        lines.append("✓ OK (HTTP 200)")
        if s.get("account_user"):
            lines.append(f"Пользователь: {esc(str(s['account_user']))}")
    elif s.get("ok") is False:
        err = s.get("error")
        if err:
            lines.append(f"✗ {esc(str(err))}")
        else:
            lines.append(f"✗ HTTP {s.get('http_status', '—')}")
    else:
        lines.append(f"HTTP {s.get('http_status', '—')}")
    return "\n".join(lines)


def format_sync_result(data: dict[str, Any]) -> str:
    raw = json.dumps(data, ensure_ascii=False, indent=2)[:3500]
    return "<b>Синхронизация справочников</b>\n<pre>" + esc(raw) + "</pre>"


def format_cache_clear_result(data: dict[str, Any]) -> str:
    if data.get("scope") is not None:
        return (
            f"<b>Очистка кэша</b>\nscope: <code>{esc(str(data.get('scope')))}</code>\n"
            f"удалено записей: {data.get('evicted', 0)}"
        )
    cleared = data.get("cleared") or {}
    parts = ["<b>Очистка кэша (все scope)</b>"]
    for k, v in sorted(cleared.items()):
        parts.append(f"• <code>{esc(k)}</code>: {v}")
    return "\n".join(parts)


def format_ok(msg: str) -> str:
    return f"✓ {esc(msg)}"


def format_err(msg: str) -> str:
    return f"✗ {esc(msg)}"


def main_menu_text() -> str:
    return (
        "<b>Панель администратора</b>\n\n"
        "Выберите раздел. Права админов управляются в БД."
    )


def prompt_sstats_key() -> str:
    return (
        "<b>Новый ключ SStats</b>\n\n"
        "Отправьте одним сообщением значение ключа (или отправьте <code>-</code> чтобы удалить "
        "ключ из БД и использовать только переменную окружения).\n\n"
        "Нужен <code>CRYPTO_KEY</code> для записи в базу."
    )


def prompt_cache_ttl() -> str:
    return (
        "<b>TTL кэша</b>\n\n"
        "Введите число секунд (от 30 до 86400), например <code>300</code>."
    )


def prompt_rate_limit() -> str:
    return (
        "<b>Лимит запросов</b>\n\n"
        "Введите число запросов с одного IP в минуту (0 — без лимита, макс. 10000)."
    )

"""
Telegram bot: menu button + webhook to handle /start and show "Open app" button.
"""
import logging
import os
from typing import Any

import httpx

from app.database import SessionLocal
from app.services import legal

logger = logging.getLogger("main")

TELEGRAM_API = "https://api.telegram.org"
PARSE_MODE = "HTML"


def _get_bot_env() -> tuple[str, str]:
    token = os.getenv("MAIN_BOT_TOKEN", "").strip()
    web_app_url = (os.getenv("WEB_APP_URL", "").strip()).rstrip("/")
    return token, web_app_url


async def set_telegram_menu_button() -> None:
    """Set the bot's menu button to show the commands menu and configure commands list."""
    token, web_app_url = _get_bot_env()
    if not token:
        logger.info("Telegram: MAIN_BOT_TOKEN not set — menu button and commands not configured.")
        return

    # 1. Set menu button to commands
    url = f"{TELEGRAM_API}/bot{token}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "commands"
        }
    }
    logger.info("Telegram: setting menu button to commands")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json=payload)
            data = r.json()
        if not data.get("ok"):
            logger.error("Telegram setChatMenuButton failed: %s", data.get("description", data))
        else:
            logger.info("Telegram: menu button set to commands successfully")
    except Exception as e:
        logger.warning("Telegram: could not set menu button: %s", e, exc_info=True)

    # 2. Set bot commands list
    cmd_url = f"{TELEGRAM_API}/bot{token}/setMyCommands"
    cmd_payload = {
        "commands": [
            {"command": "start", "description": "Запустить бота и принять условия"},
            {"command": "delete_my_data", "description": "Удалить все мои данные из системы"}
        ]
    }
    logger.info("Telegram: setting commands list")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(cmd_url, json=cmd_payload)
            data = r.json()
        if not data.get("ok"):
            logger.error("Telegram setMyCommands failed: %s", data.get("description", data))
        else:
            logger.info("Telegram: commands list set successfully")
    except Exception as e:
        logger.warning("Telegram: could not set commands list: %s", e, exc_info=True)


async def set_telegram_webhook() -> None:
    """Register webhook URL with Telegram so the bot receives /start etc."""
    token, web_app_url = _get_bot_env()
    if not token or not web_app_url:
        return
    webhook_url = f"{web_app_url}/telegram/webhook"
    url = f"{TELEGRAM_API}/bot{token}/setWebhook"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(url, json={"url": webhook_url})
            data = r.json()
        if not data.get("ok"):
            logger.error("Telegram setWebhook failed: %s", data.get("description", data))
            return
        logger.info("Telegram: webhook set → %s", webhook_url)
    except Exception as e:
        logger.warning("Telegram: could not set webhook: %s", e, exc_info=True)


def _open_app_markup(web_app_url: str) -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Открыть приложение", "web_app": {"url": web_app_url}}],
        ]
    }


def _accept_markup() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Принимаю условия", "callback_data": "legal:accept"}],
        ]
    }


def _delete_confirmation_markup() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "Да, удалить", "callback_data": "legal:delete_confirm"}],
            [{"text": "Отмена", "callback_data": "legal:delete_cancel"}],
        ]
    }


async def _tg_post(token: str, method: str, payload: dict[str, Any]) -> None:
    url = f"{TELEGRAM_API}/bot{token}/{method}"
    async with httpx.AsyncClient(timeout=8.0) as client:
        await client.post(url, json=payload)


async def handle_telegram_update(update: dict[str, Any]) -> None:
    """Process incoming updates for legal onboarding + open app actions."""
    token, web_app_url = _get_bot_env()
    if not token or not web_app_url:
        return

    callback = update.get("callback_query")
    if callback:
        uid = callback.get("from", {}).get("id")
        callback_id = callback.get("id")
        message = callback.get("message") or {}
        chat_id = message.get("chat", {}).get("id")
        data = (callback.get("data") or "").strip()
        if callback_id:
            try:
                await _tg_post(token, "answerCallbackQuery", {"callback_query_id": callback_id})
            except Exception:
                pass
        if not uid or not chat_id:
            return
        db = SessionLocal()
        try:
            if data == "legal:accept":
                legal.record_legal_acceptance(db, int(uid))
                await _tg_post(
                    token,
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": "Условия приняты. Теперь можно открыть приложение.",
                        "reply_markup": _open_app_markup(web_app_url),
                    },
                )
                return
            if data == "legal:delete_confirm":
                legal.delete_user_data(db, int(uid), reason="delete_my_data")
                await _tg_post(
                    token,
                    "sendMessage",
                    {
                        "chat_id": chat_id,
                        "text": "Ваши данные удалены. Для повторного доступа потребуется новый акцепт условий.",
                    },
                )
                return
            if data == "legal:delete_cancel":
                await _tg_post(
                    token,
                    "sendMessage",
                    {"chat_id": chat_id, "text": "Удаление отменено."},
                )
                return
        finally:
            db.close()
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return
    chat_id = message.get("chat", {}).get("id")
    uid = message.get("from", {}).get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not uid:
        return

    db = SessionLocal()
    try:
        if text == "/delete_my_data":
            await _tg_post(
                token,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": "Вы уверены, что хотите удалить все данные?",
                    "reply_markup": _delete_confirmation_markup(),
                },
            )
            return

        if text != "/start":
            return

        if legal.has_current_legal_acceptance(db, int(uid)):
            await _tg_post(
                token,
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": "Привет! Нажми кнопку ниже, чтобы открыть приложение.",
                    "reply_markup": _open_app_markup(web_app_url),
                },
            )
            return

        await _tg_post(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": legal.legal_welcome_text(db),
                "parse_mode": PARSE_MODE,
                "reply_markup": _accept_markup(),
                "disable_web_page_preview": True,
            },
        )
    except Exception as e:
        logger.warning("Telegram: handle update failed: %s", e)
    finally:
        db.close()

"""
Telegram Bot Long Polling Service.
Used when webhooks are blocked or unreachable (e.g. in environments/regions with restricted Telegram access).
"""
import asyncio
import logging
import os
from typing import Any

import httpx

from app.telegram_bot import handle_telegram_update

logger = logging.getLogger("telegram_polling")

TELEGRAM_API = "https://api.telegram.org"


def _get_proxy() -> str | None:
    proxy = os.getenv("HTTPS_PROXY", "").strip() or os.getenv("HTTP_PROXY", "").strip()
    return proxy if proxy else None


async def delete_webhook(token: str) -> bool:
    """Delete webhook for a given bot token so long polling (getUpdates) can work."""
    url = f"{TELEGRAM_API}/bot{token}/deleteWebhook"
    proxy = _get_proxy()
    try:
        async with httpx.AsyncClient(proxy=proxy, timeout=15.0) as client:
            r = await client.post(url, json={"drop_pending_updates": True})
            data = r.json()
            if data.get("ok"):
                logger.info("Telegram: deleted webhook successfully for bot ...%s", token[-6:])
                return True
            else:
                logger.error("Telegram deleteWebhook failed: %s", data.get("description", data))
    except Exception as e:
        logger.warning("Telegram: could not delete webhook for bot ...%s: %s", token[-6:], e)
    return False


async def poll_bot_updates(token: str, is_admin: bool = False) -> None:
    """Run an infinite long polling loop for a bot token."""
    logger.info("Telegram: starting long polling loop for %s bot...", "admin" if is_admin else "main")
    
    # Ensure webhook is deleted first
    await delete_webhook(token)

    offset = 0
    timeout = 20
    proxy = _get_proxy()

    if is_admin:
        from admin_bot.dispatcher import process_admin_update
        async def run_admin_handler(update: dict[str, Any]):
            try:
                await asyncio.to_thread(process_admin_update, update)
            except Exception as ex:
                logger.error("Telegram admin: error processing update: %s", ex, exc_info=True)
        handler = run_admin_handler
    else:
        async def run_main_handler(update: dict[str, Any]):
            try:
                await handle_telegram_update(update)
            except Exception as ex:
                logger.error("Telegram main: error processing update: %s", ex, exc_info=True)
        handler = run_main_handler

    url = f"{TELEGRAM_API}/bot{token}/getUpdates"

    # Single client for the loop
    async with httpx.AsyncClient(proxy=proxy, timeout=timeout + 15.0) as client:
        while True:
            try:
                payload = {
                    "offset": offset,
                    "timeout": timeout,
                    "allowed_updates": ["message", "callback_query"],
                }
                r = await client.post(url, json=payload)
                if r.status_code != 200:
                    logger.warning("Telegram polling (%s): HTTP %s. Retrying in 5s...", "admin" if is_admin else "main", r.status_code)
                    await asyncio.sleep(5)
                    continue

                data = r.json()
                if not data.get("ok"):
                    logger.warning("Telegram polling (%s) error: %s. Retrying in 5s...", "admin" if is_admin else "main", data.get("description"))
                    await asyncio.sleep(5)
                    continue

                updates = data.get("result", [])
                for update in updates:
                    offset = update["update_id"] + 1
                    asyncio.create_task(handler(update))

            except asyncio.CancelledError:
                logger.info("Telegram polling (%s) loop stopped.", "admin" if is_admin else "main")
                break
            except Exception as e:
                logger.warning("Telegram polling (%s) exception: %s. Retrying in 5s...", "admin" if is_admin else "main", e)
                await asyncio.sleep(5)


def start_telegram_polling() -> None:
    """Start polling background tasks for active bot tokens."""
    main_token = os.getenv("MAIN_BOT_TOKEN", "").strip()
    admin_token = os.getenv("ADMIN_BOT_TOKEN", "").strip()

    if main_token:
        asyncio.create_task(poll_bot_updates(main_token, is_admin=False))
    else:
        logger.warning("Telegram polling: MAIN_BOT_TOKEN not set — main bot polling skipped.")

    if admin_token:
        asyncio.create_task(poll_bot_updates(admin_token, is_admin=True))
    else:
        logger.info("Telegram polling: ADMIN_BOT_TOKEN not set — admin bot polling skipped.")

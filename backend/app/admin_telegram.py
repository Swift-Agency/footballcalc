"""Register admin bot webhook (separate from MAIN_BOT_TOKEN)."""
import logging
import os

import httpx

logger = logging.getLogger("main")

TELEGRAM_API = "https://api.telegram.org"


async def set_admin_telegram_webhook() -> None:
    token = os.getenv("ADMIN_BOT_TOKEN", "").strip()
    web = (os.getenv("WEB_APP_URL", "").strip()).rstrip("/")
    if not token or not web:
        if not token:
            logger.info("Telegram admin: ADMIN_BOT_TOKEN not set — admin webhook skipped.")
        return

    url = f"{TELEGRAM_API}/bot{token}/setWebhook"
    payload: dict = {"url": f"{web}/admin/telegram/webhook"}
    secret = os.getenv("ADMIN_WEBHOOK_SECRET", "").strip()
    if secret:
        payload["secret_token"] = secret

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(url, json=payload)
            data = r.json()
        if not data.get("ok"):
            logger.error("Telegram admin setWebhook failed: %s", data.get("description", data))
            return
        logger.info("Telegram admin: webhook set → %s", payload["url"])
    except Exception as e:
        logger.warning("Telegram admin: could not set webhook: %s", e, exc_info=True)

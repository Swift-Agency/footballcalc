"""
Validate Telegram Mini App initData (HMAC-SHA256).
https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import time
from typing import Any
from urllib.parse import parse_qsl


class TelegramWebAppAuthError(ValueError):
    pass


def validate_init_data(
    init_data: str,
    bot_token: str,
    max_age_seconds: int = 86400,
) -> dict[str, Any]:
    """
    Parse and verify init_data query string. Returns dict with parsed `user` (if present),
    `auth_date`, `query_id`, etc.
    """
    if not init_data or not bot_token:
        raise TelegramWebAppAuthError("init_data and bot_token required")

    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise TelegramWebAppAuthError("missing hash")

    # Build data_check_string: all fields except hash, sorted by key
    check_pairs = sorted(data.items())
    data_check_string = "\n".join(f"{k}={v}" for k, v in check_pairs)

    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        raise TelegramWebAppAuthError("invalid hash")

    auth_date_raw = data.get("auth_date")
    if auth_date_raw is None:
        raise TelegramWebAppAuthError("missing auth_date")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError) as e:
        raise TelegramWebAppAuthError("invalid auth_date") from e

    now = int(time.time())
    if now - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("auth_date expired")

    out: dict[str, Any] = dict(data)
    out["auth_date"] = auth_date
    if "user" in out and isinstance(out["user"], str):
        try:
            out["user"] = json.loads(out["user"])
        except json.JSONDecodeError as e:
            raise TelegramWebAppAuthError("invalid user json") from e

    return out


def get_telegram_user_id_from_validated(data: dict[str, Any]) -> int | None:
    user = data.get("user")
    if isinstance(user, dict) and "id" in user:
        try:
            return int(user["id"])
        except (TypeError, ValueError):
            return None
    return None

"""
YooKassa API client for initial payment (with card save) and recurring charges.

Requires env vars:
  YOOKASSA_SHOP_ID
  YOOKASSA_SECRET_KEY
  YOOKASSA_RETURN_URL  (e.g. https://app.example.com/billing/return)
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import contextmanager
from decimal import Decimal
from typing import Iterator, Optional

logger = logging.getLogger("yookassa_client")

_PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)


@contextmanager
def _direct_http_env() -> Iterator[None]:
    """
    YooKassa SDK uses requests, which reads HTTP(S)_PROXY from the process env.
    Telegram needs SOCKS proxy on this host, but YooKassa must go direct.
    """
    saved = {key: os.environ.pop(key, None) for key in _PROXY_ENV_KEYS}
    try:
        yield
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value


def _get_configuration():
    """Lazily configure yookassa SDK."""
    try:
        from yookassa import Configuration
        shop_id = os.getenv("YOOKASSA_SHOP_ID", "")
        secret_key = os.getenv("YOOKASSA_SECRET_KEY", "")
        if not shop_id or not secret_key:
            raise ValueError("YOOKASSA_SHOP_ID and YOOKASSA_SECRET_KEY must be set")
        Configuration.configure(account_id=shop_id, secret_key=secret_key)
    except ImportError as exc:
        raise RuntimeError("yookassa package not installed. Run: pip install yookassa") from exc


def create_initial_payment(
    amount: Decimal,
    description: str,
    return_url: str,
    idempotency_key: Optional[str] = None,
    save_payment_method: bool = True,
) -> dict:
    """
    Create a payment, optionally saving the payment method for recurring charges.
    Pass save_payment_method=False for one-time plans (world_cup).
    Returns the raw YooKassa payment dict.
    """
    _get_configuration()
    from yookassa import Payment

    key = idempotency_key or str(uuid.uuid4())
    with _direct_http_env():
        payment = Payment.create(
            {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB",
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": return_url,
                },
                "capture": True,
                "save_payment_method": save_payment_method,
                "description": description,
            },
            idempotency_key=key,
        )
    return payment.json()


def charge_recurring(
    amount: Decimal,
    payment_method_id: str,
    description: str,
    idempotency_key: Optional[str] = None,
) -> dict:
    """
    Charge a saved card without user interaction.
    Returns the raw YooKassa payment dict.
    """
    _get_configuration()
    from yookassa import Payment

    key = idempotency_key or str(uuid.uuid4())
    with _direct_http_env():
        payment = Payment.create(
            {
                "amount": {
                    "value": str(amount),
                    "currency": "RUB",
                },
                "capture": True,
                "payment_method_id": payment_method_id,
                "description": description,
            },
            idempotency_key=key,
        )
    return payment.json()


def parse_notification(body: bytes) -> dict:
    """
    Parse a raw YooKassa webhook body and return the notification dict.
    """
    _get_configuration()
    from yookassa import Webhook

    notification = Webhook.unmarshal(body)
    return notification.json()


def verify_ip(client_ip: str) -> bool:
    """
    YooKassa IP whitelist (https://yookassa.ru/developers/using-api/webhooks#ip).
    Returns True if the IP is from the YooKassa range.
    In production you should also check the 185.71.76.0/27, 185.71.77.0/27 ranges.
    For simplicity we trust all IPs in dev (set YOOKASSA_SKIP_IP_CHECK=1).
    """
    if os.getenv("YOOKASSA_SKIP_IP_CHECK", "").lower() in {"1", "true", "yes"}:
        return True

    # YooKassa official IP ranges (as of 2025)
    ALLOWED_IPS = {
        "185.71.76.",
        "185.71.77.",
        "77.75.153.",
        "77.75.156.",
        "2a02:5180::",
    }
    return any(client_ip.startswith(prefix) for prefix in ALLOWED_IPS)

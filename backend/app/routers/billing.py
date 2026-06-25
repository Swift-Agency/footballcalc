"""
Billing API: checkout, webhook, subscription status, cancel, resume, referrals.

Subscription plans:
  monthly   — price from AppSettings, 30 days, auto-renews.
  world_cup — same price, fixed end date 2026-07-19 23:59:59 UTC, no auto-renewal.

Referral discount:
  Referred users get 50% off the configured subscription price
  if they pay within 24 hours of account creation (discount_expires_at).
  Referral attribution is set only on first signup via start_param in initData.

Referral bonus for inviter:
  After the referred user's first successful payment, the inviter receives
  a free subscription:
    - monthly plan → +30 days extension
    - world_cup plan → access until 2026-07-19
  The bonus is awarded only once per referral (referral_bonus_granted_at is set on User).
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import AppSettings, Payment, Subscription, User, WORLD_CUP_ENDS_AT
from app.schemas import (
    BillingCheckoutRequest,
    BillingCheckoutResponse,
    BillingMeResponse,
    BillingPaymentStatus,
    ReferralClaimRequest,
    UsageQuota,
)
from app.services import access as access_svc
from app.services.moscow_time import format_utc_iso
from app.services.billing_prices import (
    REFERRAL_DISCOUNT_PERCENT,
    get_billing_config_payload,
    get_discount_price,
    get_or_create_settings,
    get_regular_price,
)
from app.services.telegram_webapp_auth import (
    TelegramWebAppAuthError,
    validate_init_data,
)

import threading

logger = logging.getLogger("billing")

_get_bot_username_lock = threading.Lock()

router = APIRouter()

VALID_PLAN_TYPES = {"monthly", "world_cup"}


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _require_user(init_data: Optional[str], db: Session) -> User:
    """Validate initData and return (or create) the User row. Raises 401 on failure."""
    bot_token = os.getenv("MAIN_BOT_TOKEN", "")
    if not bot_token:
        raise HTTPException(status_code=500, detail="Bot token not configured")
    if not init_data:
        raise HTTPException(status_code=401, detail="X-Telegram-Init-Data required")
    try:
        data = validate_init_data(init_data, bot_token)
    except TelegramWebAppAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc))

    user = access_svc.get_or_create_user_from_validated(data, db)
    if not user:
        raise HTTPException(status_code=401, detail="Cannot extract telegram_id")
    return user


def _subscription_end(plan_type: str, period_days: int) -> datetime:
    if plan_type == "world_cup":
        return WORLD_CUP_ENDS_AT
    return datetime.utcnow() + timedelta(days=period_days)


def _grant_referrer_bonus(db: Session, buyer: User, plan_type: str, period_days: int) -> None:
    """
    Give the inviter a free subscription after the referred user paid for the first time.
    Called only once: checks referral_bonus_granted_at to prevent double-grants.
    """
    if not buyer.referred_by_user_id:
        return

    inviter = db.query(User).filter(User.id == buyer.referred_by_user_id).first()
    if not inviter:
        return

    # Idempotency: only grant once (set on the referred user's record)
    if buyer.referral_bonus_granted_at:
        return

    buyer.referral_bonus_granted_at = datetime.utcnow()

    # Extend or create inviter's subscription
    now = datetime.utcnow()
    sub = db.query(Subscription).filter(Subscription.user_id == inviter.id).first()
    bonus_end = _subscription_end(plan_type, period_days)

    if sub and sub.status == "active" and sub.current_period_end > now:
        # Extend existing subscription
        if plan_type == "world_cup":
            sub.current_period_end = max(sub.current_period_end, WORLD_CUP_ENDS_AT)
        else:
            sub.current_period_end = sub.current_period_end + timedelta(days=period_days)
        sub.next_charge_at = sub.current_period_end
        sub.updated_at = now
    else:
        # Create a new bonus subscription
        new_sub = Subscription(
            user_id=inviter.id,
            status="active",
            plan_type=plan_type,
            source="referral_bonus",
            starts_at=now,
            current_period_end=bonus_end,
            next_charge_at=bonus_end if plan_type == "monthly" else None,
            cancel_at_period_end=plan_type != "monthly",
        )
        db.add(new_sub)

    logger.info(
        "Referral bonus granted: inviter user_id=%d, buyer user_id=%d, plan=%s",
        inviter.id, buyer.id, plan_type,
    )


def _build_referral_link(user: User) -> Optional[str]:
    web_app_url = os.getenv("WEB_APP_URL", "").strip()
    if not web_app_url or not user.referral_code:
        return None
    bot_username = os.getenv("MAIN_BOT_USERNAME", "").strip()
    if not bot_username:
        bot_username = _get_bot_username() or ""
    if bot_username:
        return f"https://t.me/{bot_username.lstrip('@')}/?startapp={user.referral_code}"
    return None


def _get_bot_username() -> Optional[str]:
    """Resolve bot @username from env or Telegram getMe (cached per process)."""
    cached = getattr(_get_bot_username, "_cache", None)
    if cached is not None:
        return cached or None

    env_username = os.getenv("MAIN_BOT_USERNAME", "").strip().lstrip("@")
    if env_username:
        _get_bot_username._cache = env_username
        return env_username

    with _get_bot_username_lock:
        cached = getattr(_get_bot_username, "_cache", None)
        if cached is not None:
            return cached or None

        token = os.getenv("MAIN_BOT_TOKEN", "").strip()
        if not token:
            _get_bot_username._cache = ""
            return None
        try:
            import httpx
            resp = httpx.get(f"https://api.telegram.org/bot{token}/getMe", timeout=1.5)
            data = resp.json()
            username = (data.get("result") or {}).get("username") or ""
            _get_bot_username._cache = username
            return username or None
        except Exception as exc:
            logger.debug("getMe failed: %s", exc)
            _get_bot_username._cache = ""
            return None


def warm_bot_username() -> None:
    """Pre-resolve bot username on startup so billing/me stays fast."""
    if os.getenv("MAIN_BOT_USERNAME", "").strip():
        _get_bot_username._cache = os.getenv("MAIN_BOT_USERNAME", "").strip().lstrip("@")
        return
    threading.Thread(target=_get_bot_username, daemon=True).start()


# ─── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/billing/checkout", response_model=BillingCheckoutResponse)
def billing_checkout(
    body: BillingCheckoutRequest = BillingCheckoutRequest(),
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Create an initial payment. Supports monthly and world_cup plan types."""
    user = _require_user(x_telegram_init_data, db)

    plan_type = body.plan_type if body.plan_type in VALID_PLAN_TYPES else "monthly"

    # Check if already active
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if sub and sub.status == "active" and sub.current_period_end > datetime.utcnow():
        raise HTTPException(status_code=409, detail="already_subscribed")

    settings = get_or_create_settings(db)
    period_days = int(settings.subscription_period_days or 30)
    regular_price = get_regular_price(settings)

    # Determine price — apply referral discount if eligible
    discount_percent = 0
    if access_svc.has_referral_discount(user):
        price = get_discount_price(settings)
        discount_percent = REFERRAL_DISCOUNT_PERCENT
    else:
        price = regular_price

    plan_label = "Чемпионат мира 2026" if plan_type == "world_cup" else "месяц"
    description = f"Football Calculator — подписка ({plan_label})"

    return_url = body.return_url or os.getenv(
        "YOOKASSA_RETURN_URL",
        f"{os.getenv('WEB_APP_URL', '').rstrip('/')}/subscription",
    )

    from app.services import yookassa_client as yk
    idempotency_key = f"initial-{user.id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
    try:
        payment_data = yk.create_initial_payment(
            amount=price,
            description=description,
            return_url=return_url,
            idempotency_key=idempotency_key,
            save_payment_method=(plan_type == "monthly"),
            telegram_id=user.telegram_id,
        )
    except Exception as exc:
        logger.error("YooKassa create_initial_payment failed: %s", exc)
        raise HTTPException(status_code=502, detail="payment_gateway_error")

    if isinstance(payment_data, str):
        pd = json.loads(payment_data)
    else:
        pd = payment_data

    yookassa_pid = pd.get("id")
    confirmation_url = (pd.get("confirmation") or {}).get("confirmation_url", "")

    if not yookassa_pid or not confirmation_url:
        raise HTTPException(status_code=502, detail="invalid_payment_response")

    payment = Payment(
        user_id=user.id,
        yookassa_payment_id=yookassa_pid,
        kind="initial",
        status="pending",
        amount_value=price,
        amount_currency="RUB",
        description=description,
        plan_type=plan_type,
        discount_percent=discount_percent,
        referral_user_id=user.referred_by_user_id,
    )
    db.add(payment)
    db.flush()
    db.commit()

    logger.info(
        "Checkout: payment %s created for user_id=%d plan=%s discount=%d%%",
        yookassa_pid, user.id, plan_type, discount_percent,
    )
    return BillingCheckoutResponse(confirmation_url=confirmation_url, payment_id=payment.id)


@router.post("/billing/yookassa/webhook", include_in_schema=False)
async def yookassa_webhook(request: Request, db: Session = Depends(get_db)):
    """YooKassa sends POST with payment/refund notification."""
    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
    client_ip = forwarded or (request.client.host if request.client else "")
    from app.services import yookassa_client as yk
    if not yk.verify_ip(client_ip):
        logger.warning("Webhook from unknown IP: %s", client_ip)
        raise HTTPException(status_code=403, detail="forbidden")

    body = await request.body()
    try:
        notification = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid_json")

    event = notification.get("event", "")
    obj = notification.get("object") or {}
    yookassa_pid = obj.get("id")

    if not yookassa_pid:
        return {"ok": True}

    logger.info("Webhook event=%s payment_id=%s", event, yookassa_pid)

    payment = db.query(Payment).filter(Payment.yookassa_payment_id == yookassa_pid).first()
    if not payment:
        return {"ok": True}

    if event == "payment.succeeded":
        if payment.status == "succeeded":
            return {"ok": True}

        payment.status = "succeeded"
        payment.paid_at = datetime.utcnow()

        pm_data = obj.get("payment_method") or {}
        pm_id = pm_data.get("id") if pm_data.get("saved") else None

        settings = get_or_create_settings(db)
        period_days = int(settings.subscription_period_days or 30)

        plan_type = payment.plan_type or "monthly"
        new_period_end = _subscription_end(plan_type, period_days)

        sub = db.query(Subscription).filter(Subscription.user_id == payment.user_id).first()

        if payment.kind == "initial":
            if sub:
                sub.status = "active"
                sub.plan_type = plan_type
                sub.source = "paid"
                sub.current_period_end = new_period_end
                sub.cancel_at_period_end = (plan_type == "world_cup")
                sub.next_charge_at = new_period_end if plan_type == "monthly" else None
                if pm_id:
                    sub.yookassa_payment_method_id = pm_id
                sub.last_payment_id = payment.id
            else:
                sub = Subscription(
                    user_id=payment.user_id,
                    status="active",
                    plan_type=plan_type,
                    source="paid",
                    starts_at=datetime.utcnow(),
                    current_period_end=new_period_end,
                    cancel_at_period_end=(plan_type == "world_cup"),
                    next_charge_at=new_period_end if plan_type == "monthly" else None,
                    yookassa_payment_method_id=pm_id,
                    last_payment_id=payment.id,
                )
                db.add(sub)
                db.flush()

            payment.subscription_id = sub.id

            # Grant referrer bonus if this is a referred user's first payment
            buyer = db.query(User).filter(User.id == payment.user_id).first()
            if buyer and buyer.referred_by_user_id and not buyer.referral_bonus_granted_at:
                _grant_referrer_bonus(db, buyer, plan_type, period_days)

        elif payment.kind == "recurring":
            if sub and sub.plan_type != "world_cup":
                sub.status = "active"
                sub.current_period_end = sub.current_period_end + timedelta(days=period_days)
                sub.next_charge_at = sub.current_period_end
                sub.last_payment_id = payment.id

    elif event in ("payment.canceled", "payment.failed"):
        payment.status = "canceled" if event == "payment.canceled" else "failed"

        sub = db.query(Subscription).filter(Subscription.user_id == payment.user_id).first()
        if sub and payment.kind == "recurring":
            settings = get_or_create_settings(db)
            retry_days = settings.recurring_retry_days or 3
            sub.status = "past_due"
            if sub.next_charge_at:
                sub.next_charge_at = sub.next_charge_at + timedelta(days=retry_days)

    db.commit()
    return {"ok": True}


@router.get("/billing/me", response_model=BillingMeResponse)
def billing_me(
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Returns current subscription status, quota, and referral info for the authenticated user."""
    user = _require_user(x_telegram_init_data, db)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()

    now = datetime.utcnow()
    is_active = sub is not None and sub.status == "active" and sub.current_period_end > now
    is_unlimited = is_active

    quota_dict = access_svc.get_weekly_quota(db, user)
    quota = UsageQuota(**quota_dict)

    referral_link = _build_referral_link(user)

    if not sub:
        return BillingMeResponse(
            is_subscribed=False,
            is_unlimited=False,
            quota=quota,
            referral_code=user.referral_code,
            referral_link=referral_link,
            has_discount=access_svc.has_referral_discount(user),
            discount_expires_at=format_utc_iso(user.discount_expires_at),
        )

    return BillingMeResponse(
        is_subscribed=is_active,
        is_unlimited=is_unlimited,
        plan_type=sub.plan_type,
        status=sub.status,
        current_period_end=sub.current_period_end.isoformat() if sub.current_period_end else None,
        cancel_at_period_end=sub.cancel_at_period_end,
        quota=quota,
        referral_code=user.referral_code,
        referral_link=referral_link,
        has_discount=access_svc.has_referral_discount(user),
        discount_expires_at=format_utc_iso(user.discount_expires_at),
    )


@router.get("/billing/payments/{payment_id}", response_model=BillingPaymentStatus)
def poll_payment(
    payment_id: int,
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Poll payment status (used after returning from YooKassa form)."""
    user = _require_user(x_telegram_init_data, db)
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.user_id == user.id,
    ).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")
    return BillingPaymentStatus(payment_id=payment.id, status=payment.status)


@router.post("/billing/cancel")
def billing_cancel(
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Cancel auto-renewal. Access remains until current_period_end."""
    user = _require_user(x_telegram_init_data, db)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription")
    if sub.status not in ("active", "past_due"):
        raise HTTPException(status_code=400, detail="Subscription not active")
    sub.cancel_at_period_end = True
    sub.canceled_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.post("/billing/resume")
def billing_resume(
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Re-enable auto-renewal after cancel (if period hasn't ended yet)."""
    user = _require_user(x_telegram_init_data, db)
    sub = db.query(Subscription).filter(Subscription.user_id == user.id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="No subscription")
    now = datetime.utcnow()
    if sub.current_period_end < now:
        raise HTTPException(status_code=400, detail="Subscription period already ended")
    if sub.plan_type == "world_cup":
        raise HTTPException(status_code=400, detail="World Cup plan cannot be resumed for auto-renewal")
    sub.cancel_at_period_end = False
    sub.canceled_at = None
    db.commit()
    return {"ok": True}


@router.get("/billing/config")
def billing_config(db: Session = Depends(get_db)):
    """Return public billing configuration (price, period)."""
    settings = get_or_create_settings(db)
    return get_billing_config_payload(settings)


@router.post("/referrals/claim")
def claim_referral(
    body: ReferralClaimRequest,
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Ensure user exists and return referral status.
    Attribution is applied only at first signup via start_param in Telegram initData.
    Existing users are never re-attributed when opening a referral link again.
    """
    user = _require_user(x_telegram_init_data, db)

    if user.referred_by_user_id:
        return {
            "ok": True,
            "has_discount": access_svc.has_referral_discount(user),
            "message": "already_referred",
        }

    return {
        "ok": True,
        "has_discount": False,
        "message": "not_referred",
    }


@router.get("/referrals/me")
def referrals_me(
    x_telegram_init_data: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """Return the current user's referral stats."""
    user = _require_user(x_telegram_init_data, db)

    referral_link = _build_referral_link(user)

    # Count referred users and how many converted (paid)
    referred_users = db.query(User).filter(User.referred_by_user_id == user.id).all()
    referred_count = len(referred_users)
    converted_count = sum(
        1 for u in referred_users if u.referral_bonus_granted_at is not None
    )

    return {
        "referral_code": user.referral_code,
        "referral_link": referral_link,
        "referred_count": referred_count,
        "converted_count": converted_count,
        "bonus_granted_at": None,  # per-referrer stats aggregated above
    }

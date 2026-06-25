"""
Billing scheduler: runs in background every 5 minutes to process recurring charges.

Logic:
  1. Find Subscriptions where status='active' AND next_charge_at <= now() AND cancel_at_period_end=False.
  2. For each, call charge_recurring() and create a Payment(kind='recurring', status='pending').
  3. Actual status update happens via webhook (payment.succeeded / payment.canceled).
  4. Also expire subscriptions that are past their current_period_end with no pending payment.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from decimal import Decimal

logger = logging.getLogger("billing_scheduler")


async def _run_once():
    from app.database import SessionLocal
    from app.models import Subscription, Payment, AppSettings, User

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        settings = db.query(AppSettings).filter(AppSettings.id == 1).first()
        from app.services.billing_prices import get_or_create_settings, get_regular_price
        if not settings:
            settings = get_or_create_settings(db)
            db.commit()
        price = get_regular_price(settings)

        # Only monthly subscriptions auto-renew; world_cup subscriptions are fixed-term
        due_subs = (
            db.query(Subscription)
            .filter(
                Subscription.status == "active",
                Subscription.cancel_at_period_end.is_(False),
                Subscription.next_charge_at.isnot(None),
                Subscription.next_charge_at <= now,
                Subscription.yookassa_payment_method_id.isnot(None),
            )
            .all()
        )
        # Filter out world_cup plans (they never auto-renew)
        due_subs = [s for s in due_subs if getattr(s, "plan_type", "monthly") != "world_cup"]

        logger.info("Billing scheduler: %d subscriptions due for renewal", len(due_subs))

        for sub in due_subs:
            pending_payment = (
                db.query(Payment)
                .filter(
                    Payment.subscription_id == sub.id,
                    Payment.kind == "recurring",
                    Payment.status == "pending",
                )
                .first()
            )
            if pending_payment:
                logger.info("Skipping sub=%d — pending recurring payment exists", sub.id)
                continue
            try:
                from app.services import yookassa_client as yk

                user = db.query(User).filter(User.id == sub.user_id).first()
                idempotency_key = f"recurring-{sub.id}-{now.strftime('%Y%m%d%H')}"
                payment_data = yk.charge_recurring(
                    amount=price,
                    payment_method_id=sub.yookassa_payment_method_id,
                    description="Подписка Football Calculator (автопродление)",
                    idempotency_key=idempotency_key,
                    telegram_id=user.telegram_id if user else None,
                )

                import json
                if isinstance(payment_data, str):
                    pd = json.loads(payment_data)
                else:
                    pd = payment_data

                yookassa_pid = pd.get("id")
                if not yookassa_pid:
                    logger.error("No payment id in yookassa response for sub=%d", sub.id)
                    continue

                # Check if payment already exists (idempotency)
                existing = db.query(Payment).filter(
                    Payment.yookassa_payment_id == yookassa_pid
                ).first()
                if not existing:
                    payment = Payment(
                        user_id=sub.user_id,
                        subscription_id=sub.id,
                        yookassa_payment_id=yookassa_pid,
                        kind="recurring",
                        status=pd.get("status", "pending"),
                        amount_value=price,
                        amount_currency="RUB",
                        description="Автопродление подписки",
                        plan_type=getattr(sub, "plan_type", "monthly"),
                        discount_percent=0,
                    )
                    db.add(payment)
                    db.flush()
                    logger.info(
                        "Created recurring payment %s for sub=%d user=%d",
                        yookassa_pid, sub.id, sub.user_id,
                    )

            except Exception as exc:
                logger.error("Failed to charge recurring for sub=%d: %s", sub.id, exc)

        # Expire overdue subscriptions that have no active pending payment
        retry_days = settings.recurring_retry_days if settings else 3
        expired_subs = (
            db.query(Subscription)
            .filter(
                Subscription.status.in_(["active", "past_due"]),
                Subscription.current_period_end < now - timedelta(days=retry_days),
            )
            .all()
        )
        for sub in expired_subs:
            # Only expire if no pending recurring payment
            pending_payment = (
                db.query(Payment)
                .filter(
                    Payment.subscription_id == sub.id,
                    Payment.kind == "recurring",
                    Payment.status == "pending",
                )
                .first()
            )
            if not pending_payment:
                logger.info("Expiring subscription id=%d user=%d", sub.id, sub.user_id)
                sub.status = "expired"

        db.commit()

    except Exception as exc:
        logger.error("Billing scheduler error: %s", exc, exc_info=True)
        db.rollback()
    finally:
        db.close()


async def billing_loop():
    """Main scheduler loop — runs every 5 minutes."""
    interval = int(os.getenv("BILLING_SCHEDULER_INTERVAL_SECONDS", "300"))
    logger.info("Billing scheduler started (interval=%ds)", interval)
    while True:
        await _run_once()
        await asyncio.sleep(interval)


def start_billing_scheduler():
    """Start the background task from FastAPI startup."""
    asyncio.create_task(billing_loop())

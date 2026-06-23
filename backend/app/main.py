import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")

from app.database import engine, Base, SessionLocal

import app.models  # noqa: F401 — register all models before create_all
from app.models import League
from app.services import admin_access, legal

Base.metadata.create_all(bind=engine)
logger.info("Database tables ensured.")

# Lightweight ALTER TABLE migration for existing SQLite databases —
# adds new columns that create_all won't add to pre-existing tables.
def _run_column_migrations():
    _migrations = [
        # table, column, ddl
        ("app_settings", "weekly_free_quota", "INTEGER NOT NULL DEFAULT 5"),
        ("users", "referral_code", "VARCHAR"),
        ("users", "referred_by_user_id", "INTEGER REFERENCES users(id)"),
        ("users", "discount_expires_at", "DATETIME"),
        ("users", "referral_bonus_granted_at", "DATETIME"),
        ("payments", "plan_type", "VARCHAR"),
        ("payments", "discount_percent", "INTEGER NOT NULL DEFAULT 0"),
        ("payments", "referral_user_id", "INTEGER REFERENCES users(id)"),
        ("subscriptions", "plan_type", "VARCHAR NOT NULL DEFAULT 'monthly'"),
        ("subscriptions", "source", "VARCHAR NOT NULL DEFAULT 'paid'"),
    ]
    with engine.connect() as conn:
        for table, column, ddl in _migrations:
            try:
                conn.execute(
                    __import__("sqlalchemy").text(
                        f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"
                    )
                )
                conn.commit()
                logger.info("Migration: added %s.%s", table, column)
            except Exception:
                pass  # column already exists — safe to ignore
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_referral_code "
                    "ON users(referral_code)"
                )
            )
            conn.commit()
        except Exception:
            pass


_run_column_migrations()

with engine.connect() as conn:
    try:
        conn.execute(
            __import__("sqlalchemy").text(
                "UPDATE app_settings SET subscription_price_rub = 480.00 "
                "WHERE subscription_price_rub IS NULL OR subscription_price_rub < 480"
            )
        )
        conn.commit()
        logger.info("Migration: normalized subscription_price_rub to 480")
    except Exception as exc:
        logger.warning("Migration subscription_price_rub update skipped: %s", exc)

from app.routers import admin, auth, events, leagues, search, billing, media
from app.telegram_bot import set_telegram_menu_button, set_telegram_webhook, handle_telegram_update
from app.admin_telegram import set_admin_telegram_webhook
from app.middleware.legal_gate import LegalAccessMiddleware
from app.middleware.rate_limit import RateLimitAndFeatureMiddleware

AUTO_SEED_ON_STARTUP = os.getenv("AUTO_SEED_ON_STARTUP", "").lower() in {"1", "true", "yes"}

if AUTO_SEED_ON_STARTUP:
    db = SessionLocal()
    try:
        if db.query(League).count() == 0:
            logger.info("No leagues in DB — running initial seed from SStats…")
            db.close()
            from app.seed import run_seed

            run_seed()
            logger.info("Initial seed completed.")
        else:
            db.close()
    except Exception as e:
        logger.warning("Seed check/run failed: %s", e, exc_info=True)
        db.close()

app = FastAPI(title="Football Calculator API")


class CacheControlMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        path = request.url.path
        if path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif not path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response


app.add_middleware(CacheControlMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(LegalAccessMiddleware)
app.add_middleware(RateLimitAndFeatureMiddleware)

app.include_router(leagues.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(events.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(media.router, prefix="/api")


@app.get("/api/health")
def health():
    has_bot_token = bool(os.getenv("MAIN_BOT_TOKEN", "").strip())
    has_web_app_url = bool(os.getenv("WEB_APP_URL", "").strip())
    return {
        "status": "ok",
        "data_source": "sstats.net",
        "telegram_menu_button_configured": has_bot_token and has_web_app_url,
    }


@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(request: Request):
    try:
        body = await request.json()
        asyncio.create_task(handle_telegram_update(body))
    except Exception:
        pass
    return {}


@app.post("/admin/telegram/webhook", include_in_schema=False)
async def admin_telegram_webhook(request: Request):
    secret = os.getenv("ADMIN_WEBHOOK_SECRET", "").strip()
    if secret:
        got = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if got != secret:
            return Response(status_code=403)
    try:
        body = await request.json()
        from admin_bot.dispatcher import process_admin_update

        await asyncio.to_thread(process_admin_update, body)
    except Exception as e:
        logger.warning("admin webhook failed: %s", e, exc_info=True)
    return {}


from fastapi import HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

@app.get("/legal/{doc_type}", include_in_schema=False)
async def serve_current_legal_document(doc_type: str):
    if doc_type not in ("terms", "privacy", "disclaimer"):
        raise HTTPException(status_code=404, detail="Document type not found")

    db = SessionLocal()
    try:
        row = legal.get_effective_legal_document(db)
        target = {
            "terms": row.terms_url,
            "privacy": row.privacy_url,
            "disclaimer": row.disclaimer_url,
        }[doc_type]
    finally:
        db.close()

    if target.rstrip("/").endswith(f"/legal/{doc_type}"):
        target = f"/legal/{doc_type}/v1"
    return RedirectResponse(target, status_code=302)

@app.get("/legal/{doc_type}/{version}", response_class=HTMLResponse)
async def serve_legal_document(doc_type: str, version: str):
    if doc_type not in ("terms", "privacy", "disclaimer"):
        raise HTTPException(status_code=404, detail="Document type not found")
    
    # Path to file in persistent /data directory
    file_path = Path("/data/legal") / doc_type / f"{version}.html"
    if not file_path.is_file():
        # Fallback to local data directory if /data is not used (e.g. in dev)
        file_path = Path(__file__).parent.parent / "data" / "legal" / doc_type / f"{version}.html"
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Document version not found")
            
    try:
        content = file_path.read_text(encoding="utf-8")
        return HTMLResponse(content=content, status_code=200)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading document: {e}")


_STATIC_DIR = Path(__file__).parent.parent / "static"

if _STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=_STATIC_DIR / "assets"), name="assets")

    _LOGOS_DIR = _STATIC_DIR / "logos"
    if _LOGOS_DIR.is_dir():
        app.mount("/logos", StaticFiles(directory=_LOGOS_DIR), name="logos")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        candidate = _STATIC_DIR / full_path
        if candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_STATIC_DIR / "index.html")


@app.on_event("startup")
async def on_startup():
    logger.info("App startup: data source = SStats.net")
    db = SessionLocal()
    try:
        admin_access.ensure_bootstrap_admins(db)
        legal.ensure_default_legal_document(db)
    finally:
        db.close()
    await set_telegram_menu_button()
    
    use_polling = os.getenv("TELEGRAM_USE_POLLING", "true").lower() in ("1", "true", "yes")
    if use_polling:
        logger.info("Telegram: starting long polling background tasks...")
        from app.services.telegram_polling import start_telegram_polling
        start_telegram_polling()
    else:
        logger.info("Telegram: registering webhooks...")
        await set_telegram_webhook()
        await set_admin_telegram_webhook()
    from app.services.notifications import start_notification_loop
    start_notification_loop()
    from app.services.billing_scheduler import start_billing_scheduler
    start_billing_scheduler()
    logger.info("Billing scheduler started.")
    from app.services.data_sync_scheduler import start_data_sync_scheduler
    start_data_sync_scheduler()
    from app.routers.billing import warm_bot_username
    warm_bot_username()

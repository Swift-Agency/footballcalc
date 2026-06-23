import hashlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Team
from app.services.logo_proxy import fetch_logo_bytes, normalize_logo_source_url

logger = logging.getLogger("media")

router = APIRouter()


@router.get("/team-logos/{team_id}")
def get_team_logo(team_id: int, request: Request, db: Session = Depends(get_db)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team or not team.logo_url:
        raise HTTPException(status_code=404, detail="Team logo not found")

    source_url = normalize_logo_source_url(team.logo_url)
    if not source_url or not source_url.startswith(("https://", "http://")):
        raise HTTPException(status_code=404, detail="Invalid team logo URL")

    etag = f'W/"team-logo-{team_id}-{hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:16]}"'
    if request.headers.get("if-none-match") == etag:
        return Response(
            status_code=304,
            headers={
                "Cache-Control": "public, max-age=86400",
                "ETag": etag,
            },
        )

    try:
        logo = fetch_logo_bytes(source_url)
    except Exception as exc:
        logger.warning("Logo fetch failed team_id=%d url=%s: %s", team_id, source_url, exc)
        raise HTTPException(status_code=404, detail="Team logo is unavailable")

    return Response(
        content=logo.content,
        media_type=logo.content_type,
        headers={
            "Cache-Control": "public, max-age=86400",
            "ETag": etag,
        },
    )

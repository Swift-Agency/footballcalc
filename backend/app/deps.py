import os
from typing import Annotated

from fastapi import Header, HTTPException, status

ADMIN_SECRET_ENV = "ADMIN_API_SECRET"


def verify_admin_secret(
    x_admin_secret: Annotated[str | None, Header(alias="X-Admin-Secret")] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    expected = os.getenv(ADMIN_SECRET_ENV, "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin API not configured (ADMIN_API_SECRET missing)",
        )
    token = (x_admin_secret or "").strip()
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin credentials")

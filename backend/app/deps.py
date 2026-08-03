from fastapi import Header, HTTPException

from .config import DEMO_TOKEN


def require_token(authorization: str | None = Header(default=None)):
    """Single demo workspace: constant bearer token from .env on every route."""
    if authorization != f"Bearer {DEMO_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})

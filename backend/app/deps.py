from fastapi import Header, HTTPException

from .config import DEMO_TOKEN

# "sales" and "manager" were added for configurable approval routes (see
# docs/configurable-approval-routes-report.md) — a route step can require
# either, so the demo role switcher must be able to claim them. Additive
# only; the original four roles are unchanged.
ALLOWED_DEMO_ROLES = frozenset({"business_owner", "legal", "finance", "executive", "sales", "manager"})


def require_token(authorization: str | None = Header(default=None)):
    """Single demo workspace: constant bearer token from .env on every route."""
    if authorization != f"Bearer {DEMO_TOKEN}":
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})


def demo_role(x_demo_role: str | None = Header(default=None)) -> str:
    if x_demo_role in ALLOWED_DEMO_ROLES:
        return x_demo_role
    return "legal"

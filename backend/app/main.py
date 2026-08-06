from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import require_token
from .routers import (
    approvals,
    contract_lifecycle,
    contracts,
    counterparties,
    dashboard,
    negotiation,
    negotiation_monitor,
    obligations,
    placeholders,
    playbooks,
    reviews_internal,
    reviews_public,
    signature,
    signature_public,
    util,
    versions,
)

app = FastAPI(title="ContractOps AI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

protected = [Depends(require_token)]
app.include_router(contracts.router, prefix="/api", dependencies=protected)
app.include_router(contract_lifecycle.router, prefix="/api", dependencies=protected)
app.include_router(dashboard.router, prefix="/api", dependencies=protected)
app.include_router(obligations.router, prefix="/api", dependencies=protected)
app.include_router(util.router, prefix="/api", dependencies=protected)
app.include_router(placeholders.router, prefix="/api", dependencies=protected)
app.include_router(reviews_internal.router, prefix="/api", dependencies=protected)
app.include_router(negotiation.router, prefix="/api", dependencies=protected)
app.include_router(negotiation_monitor.router, prefix="/api", dependencies=protected)
app.include_router(playbooks.router, prefix="/api", dependencies=protected)
app.include_router(counterparties.router, prefix="/api", dependencies=protected)
app.include_router(approvals.router, prefix="/api", dependencies=protected)
app.include_router(signature.router, prefix="/api", dependencies=protected)
app.include_router(versions.router, prefix="/api", dependencies=protected)
app.include_router(reviews_public.router, prefix="/api")
app.include_router(signature_public.router, prefix="/api")


@app.get("/healthz")
def healthz():
    return {"ok": True}

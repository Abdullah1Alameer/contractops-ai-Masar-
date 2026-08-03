from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .deps import require_token
from .routers import contracts, dashboard, obligations, placeholders, util

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
app.include_router(obligations.router, prefix="/api", dependencies=protected)
app.include_router(util.router, prefix="/api", dependencies=protected)
app.include_router(dashboard.router, prefix="/api", dependencies=protected)
app.include_router(placeholders.router, prefix="/api", dependencies=protected)


@app.get("/healthz")
def healthz():
    return {"ok": True}

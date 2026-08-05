"""Dashboard summary aggregate endpoint tests."""
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import event

from app.models import Contract


@pytest.fixture
def db_session():
    from app.db import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_dashboard_summary_shape(db_session):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    c = Contract(id=uuid4(), title="Summary Test", status="ready", stage="negotiation", file_url="k.pdf")
    db_session.add(c)
    db_session.commit()

    res = client.get("/api/dashboard/summary", headers={"Authorization": "Bearer demo-secret-token"})
    assert res.status_code == 200
    body = res.json()
    assert "kpis" in body
    assert "recent_activity" in body
    assert "reviews_summary" in body
    assert "aggregate" in body
    assert isinstance(body["recent_contracts"], list)


def test_dashboard_summary_query_ceiling():
    from fastapi.testclient import TestClient

    from app.db import engine
    from app.main import app

    client = TestClient(app)
    count = {"n": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if statement and statement.lstrip().upper().startswith("SELECT"):
            count["n"] += 1

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        count["n"] = 0
        res = client.get("/api/dashboard/summary", headers={"Authorization": "Bearer demo-secret-token"})
        assert res.status_code == 200
        assert count["n"] <= 15
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


def test_contracts_include_workflow_summary(db_session):
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    c = Contract(id=uuid4(), title="WF", status="ready", stage="negotiation", file_url="k.pdf")
    db_session.add(c)
    db_session.commit()

    res = client.get(
        "/api/contracts?include=workflow_summary",
        headers={"Authorization": "Bearer demo-secret-token"},
    )
    assert res.status_code == 200
    rows = res.json()
    assert len(rows) >= 1
    row = next(r for r in rows if r["id"] == str(c.id))
    assert "workflow_summary" in row
    assert "review_status" in row["workflow_summary"]

"""Executive summary generation (no live OpenAI)."""
import uuid
from unittest.mock import MagicMock, patch

from app.ai.client import AIError
from app.ai.summary_prompt import SECTION_KEYS
from app.services import summary as sum_svc


def _contract(**kwargs):
    defaults = {
        "id": uuid.uuid4(),
        "raw_text": "\n[[PAGE 1]]\nSample contract text for summary testing.",
        "page_layout": [{"page": 1, "blocks": []}],
        "title": "Test",
        "contract_category": "employment",
        "party_a": "A",
        "party_b": "B",
        "value_sar": None,
        "start_date": None,
        "end_date": None,
    }
    defaults.update(kwargs)
    return MagicMock(**defaults)


def test_source_hash_changes_with_layout():
    c = _contract()
    h1 = sum_svc.source_hash(c)
    c.page_layout = [{"page": 1, "blocks": [{"text": "x"}]}]
    h2 = sum_svc.source_hash(c)
    assert h1 != h2


def test_generate_failure_safe_error():
    cid = uuid.uuid4()
    contract = _contract(id=cid)
    db = MagicMock()
    db.get.return_value = contract
    db.query.return_value.filter_by.return_value.first.return_value = None

    with patch("app.services.summary.complete_json", side_effect=AIError("ai_failed")):
        with patch.object(sum_svc, "get_or_create_row") as gor:
            row = MagicMock(status="not_generated", source_hash=None)
            gor.return_value = row
            sum_svc.generate_summary(cid, db, force=True)
    assert row.status == "failed"
    assert row.error_code == "ai_failed"
    assert "OPENAI" not in (row.error_detail or "").upper()


def test_idempotent_ready_skips_llm():
    cid = uuid.uuid4()
    contract = _contract(id=cid)
    h = sum_svc.source_hash(contract)
    row = MagicMock(status="ready", source_hash=h)
    db = MagicMock()
    db.get.return_value = contract

    with patch.object(sum_svc, "get_or_create_row", return_value=row):
        with patch("app.services.summary.complete_json") as cj:
            sum_svc.generate_summary(cid, db, force=False)
            cj.assert_not_called()


def test_verify_sections_drops_bad_citations():
    raw = "The fee is one hundred riyals per month."
    payload = {
        "purpose": {
            "status": "stated",
            "overview_ar": "x",
            "overview_en": "y",
            "items": [
                {
                    "text_ar": "a",
                    "text_en": "b",
                    "citations": [
                        {"clause_ref": "1", "page": 1, "quote": "one hundred riyals"},
                        {"clause_ref": "2", "page": 1, "quote": "invented quote xyz"},
                    ],
                }
            ],
        }
    }
    for key in SECTION_KEYS:
        if key != "purpose":
            payload[key] = {
                "status": "not_stated",
                "overview_ar": "",
                "overview_en": "",
                "items": [],
            }
    ar, _en = sum_svc._verify_sections(raw, payload)
    assert len(ar["purpose"]["items"][0]["citations"]) == 1


def test_serialize_not_generated():
    db = MagicMock()
    c = _contract()
    db.get.return_value = None
    out = sum_svc.serialize_summary(c, db)
    assert out["status"] == "not_generated"

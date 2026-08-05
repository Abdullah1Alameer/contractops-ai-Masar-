"""Three-way comparison shape."""
import uuid
from unittest.mock import MagicMock, patch

from app.services.negotiation_monitor.comparison import run_three_way


@patch("app.services.negotiation_monitor.comparison.ver_svc.compare_versions")
def test_comparison_keys(mock_cmp):
    mock_cmp.return_value = {"diff": {"overall_risk_score": 70}}
    db = MagicMock()
    cid = uuid.uuid4()
    pid = uuid.uuid4()
    vid = uuid.uuid4()
    tpl = uuid.uuid4()
    prev = MagicMock(id=pid, file_path=None, extracted_json=None)
    prop = MagicMock(
        id=vid,
        file_path="x.txt",
        extracted_json=None,
        change_summary="Payment ninety (90) days. Unlimited liability. England governing law.",
    )
    template = MagicMock(
        id=tpl,
        file_path="t.txt",
        extracted_json=None,
        change_summary="thirty (30) days. contract value. Saudi Arabia",
    )
    db.get.side_effect = lambda model, pk: {pid: prev, vid: prop, tpl: template}.get(pk)
    with patch(
        "app.services.negotiation_monitor.comparison._extract_text_from_version",
        side_effect=lambda db, v: v.change_summary or "",
    ):
        out = run_three_way(
            db,
            contract_id=cid,
            previous_version_id=pid,
            proposed_version_id=vid,
            template_version_id=tpl,
        )
    assert "previous_version_comparison" in out
    assert "template_deviations" in out
    assert "overall_risk_score" in out

"""Re-extraction must not be blocked by clause links held by surviving rows.

Reproduces the ForeignKeyViolation raised while creating a new contract version:
the pipeline wipe deleted clauses while deadlines/payment milestones still
referenced them (deadlines_source_clause_id_fkey).
"""
from datetime import date, timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.ai.pipeline import unlink_clause_references
from app.db import SessionLocal
from app.models import (
    ActivityEvent,
    Clause,
    Contract,
    ContractVersion,
    Deadline,
    Extraction,
    Obligation,
    PaymentMilestone,
)
from app.services import versions as ver_svc


@pytest.fixture
def extraction_db():
    db = SessionLocal()
    contract_ids = []

    def create_extracted_contract() -> dict:
        contract = Contract(
            id=uuid4(),
            title="Synthetic re-extraction contract",
            status="ready",
            stage="negotiation",
            supported=True,
            file_url="synthetic/reextraction.pdf",
        )
        db.add(contract)
        db.flush()
        version = ContractVersion(
            id=uuid4(),
            contract_id=contract.id,
            version_number=1,
            version_label="v1",
            source="initial_upload",
            status="ready",
            file_path=contract.file_url,
            is_current=True,
            created_by="synthetic-test",
        )
        clause = Clause(
            id=uuid4(),
            contract_id=contract.id,
            clause_ref="7.1",
            quote="Synthetic clause quote",
            page=1,
            char_start=0,
            char_end=21,
        )
        db.add_all([version, clause])
        db.flush()
        deadline = Deadline(
            id=uuid4(),
            contract_id=contract.id,
            type="notice_deadline",
            title="Synthetic notice deadline",
            deadline_date=date.today() + timedelta(days=30),
            status="done",
            generated=True,
            source_clause_id=clause.id,
        )
        manual_deadline = Deadline(
            id=uuid4(),
            contract_id=contract.id,
            type="notice_deadline",
            title="Synthetic manual deadline",
            deadline_date=date.today() + timedelta(days=60),
            status="pending",
            generated=False,
            source_clause_id=clause.id,
        )
        milestone = PaymentMilestone(
            id=uuid4(),
            contract_id=contract.id,
            seq=1,
            label="Synthetic milestone",
            status="paid",
            paid=True,
            generated=True,
            source_clause_id=clause.id,
        )
        obligation = Obligation(
            id=uuid4(),
            contract_id=contract.id,
            title="Synthetic obligation",
            status="pending",
            source_clause_id=clause.id,
        )
        extraction = Extraction(
            id=uuid4(),
            contract_id=contract.id,
            field_name="governing_law",
            value_json={"value": "KSA"},
            clause_id=clause.id,
            status="auto",
        )
        db.add_all([deadline, manual_deadline, milestone, obligation, extraction])
        db.commit()
        contract_ids.append(contract.id)
        return {
            "contract": contract,
            "clause": clause,
            "deadline": deadline,
            "manual_deadline": manual_deadline,
            "milestone": milestone,
        }

    yield db, create_extracted_contract

    db.rollback()
    for contract_id in contract_ids:
        contract = db.get(Contract, contract_id)
        if contract is not None:
            db.delete(contract)
    db.commit()
    db.close()


def wipe_previous_output(contract_id, db):
    """The exact idempotency wipe run by app.ai.pipeline.run_extraction."""
    unlink_clause_references(contract_id, db)
    db.query(Obligation).filter(Obligation.contract_id == contract_id).delete()
    db.query(Extraction).filter(Extraction.contract_id == contract_id).delete()
    db.query(Clause).filter(Clause.contract_id == contract_id).delete()
    db.flush()


def test_wipe_succeeds_while_deadlines_reference_clauses(extraction_db):
    db, create_extracted_contract = extraction_db
    rows = create_extracted_contract()
    contract = rows["contract"]

    wipe_previous_output(contract.id, db)
    db.commit()

    assert db.query(Clause).filter_by(contract_id=contract.id).count() == 0
    assert db.query(Obligation).filter_by(contract_id=contract.id).count() == 0
    assert db.query(Extraction).filter_by(contract_id=contract.id).count() == 0


def test_wipe_preserves_deadline_and_milestone_state(extraction_db):
    db, create_extracted_contract = extraction_db
    rows = create_extracted_contract()
    contract = rows["contract"]

    wipe_previous_output(contract.id, db)
    db.commit()

    db.refresh(rows["deadline"])
    db.refresh(rows["manual_deadline"])
    db.refresh(rows["milestone"])
    assert rows["deadline"].source_clause_id is None
    assert rows["deadline"].status == "done"
    assert rows["manual_deadline"].source_clause_id is None
    assert rows["manual_deadline"].generated is False
    assert rows["milestone"].source_clause_id is None
    assert rows["milestone"].paid is True
    assert rows["milestone"].status == "paid"
    assert db.query(Deadline).filter_by(contract_id=contract.id).count() == 2
    assert db.query(PaymentMilestone).filter_by(contract_id=contract.id).count() == 1


def test_version_creation_keeps_its_audit_trail_when_extraction_fails(extraction_db):
    db, create_extracted_contract = extraction_db
    contract = create_extracted_contract()["contract"]

    with patch.object(ver_svc.storage, "save", return_value="synthetic/v2.docx"):
        with patch(
            "app.ai.pipeline.run_extraction",
            side_effect=RuntimeError("synthetic extraction failure"),
        ):
            with pytest.raises(RuntimeError):
                ver_svc.create_new_version(
                    contract.id,
                    db,
                    source="client_revision",
                    actor="legal",
                    file_bytes=b"synthetic docx bytes",
                    filename="synthetic.docx",
                    change_summary="Synthetic revision",
                )

    db.rollback()
    versions = (
        db.query(ContractVersion)
        .filter_by(contract_id=contract.id)
        .order_by(ContractVersion.version_number.asc())
        .all()
    )
    created = (
        db.query(ActivityEvent)
        .filter_by(contract_id=contract.id, event_type="version_created")
        .all()
    )
    assert [v.version_number for v in versions] == [1, 2]
    assert len(created) == 1
    assert created[0].event_metadata["version_number"] == 2


def test_unlink_is_idempotent_and_scoped_to_one_contract(extraction_db):
    db, create_extracted_contract = extraction_db
    target = create_extracted_contract()
    other = create_extracted_contract()

    unlink_clause_references(target["contract"].id, db)
    unlink_clause_references(target["contract"].id, db)
    db.commit()

    db.refresh(other["deadline"])
    db.refresh(other["milestone"])
    assert other["deadline"].source_clause_id == other["clause"].id
    assert other["milestone"].source_clause_id == other["clause"].id

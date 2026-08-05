"""Demo negotiation monitor seed data."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...models import Contract, ContractVersion, LegalPlaybook, NegotiationThread
from ...services import versions as ver_svc

DEMO_THREAD_ID = uuid.UUID("b2000000-0000-4000-8000-000000000001")
DEMO_CONTRACT_ID = uuid.UUID("b2000000-0000-4000-8000-000000000002")
DEMO_TEMPLATE_CONTRACT_ID = uuid.UUID("b2000000-0000-4000-8000-000000000003")
DEFAULT_PLAYBOOK_ID = uuid.UUID("a1000000-0000-4000-8000-000000000001")

MSA_TEMPLATE_TEXT = b"""MASTER SERVICE AGREEMENT (STANDARD TEMPLATE)

8. Payment Terms: Client shall pay all invoices within thirty (30) days of receipt.

12. Limitation of Liability: Provider's aggregate liability shall not exceed the total contract value.

19. Governing Law: This Agreement is governed by the laws of the Kingdom of Saudi Arabia.
"""

MSA_BASE_TEXT = b"""MASTER SERVICE AGREEMENT

Parties: Your Company / Al-Falak Ltd

8. Payment Terms: Client shall pay all invoices within thirty (30) days of receipt.

12. Limitation of Liability: Provider's aggregate liability shall not exceed the total contract value.

19. Governing Law: This Agreement is governed by the laws of the Kingdom of Saudi Arabia.
"""


def ensure_demo_data(db: Session) -> NegotiationThread | None:
    existing = db.get(NegotiationThread, DEMO_THREAD_ID)
    if existing:
        return existing

    tpl = db.get(Contract, DEMO_TEMPLATE_CONTRACT_ID)
    if tpl is None:
        tpl = Contract(
            id=DEMO_TEMPLATE_CONTRACT_ID,
            title="Standard MSA Template",
            contract_category="MSA",
            party_a="Your Company",
            party_b="Counterparty",
            status="ready",
            stage="negotiation",
            is_template=True,
            template_category="MSA",
            governing_law="Kingdom of Saudi Arabia",
        )
        db.add(tpl)
        db.commit()
        tpl_v = ver_svc.create_initial_version(tpl, db)
        tpl_v = ver_svc.create_new_version(
            tpl.id,
            db,
            source="approved",
            actor="seed",
            file_bytes=MSA_TEMPLATE_TEXT,
            filename="standard_msa.txt",
            change_summary="Approved standard template",
            make_current=True,
            version_status="ready",
            run_pipeline=False,
        )

    deal = db.get(Contract, DEMO_CONTRACT_ID)
    if deal is None:
        deal = Contract(
            id=DEMO_CONTRACT_ID,
            title="Vendor MSA — Al-Falak Ltd",
            contract_category="MSA",
            party_a="Your Company",
            party_b="Al-Falak Ltd",
            status="ready",
            stage="negotiation",
            governing_law="Kingdom of Saudi Arabia",
        )
        db.add(deal)
        db.commit()
        deal_v = ver_svc.create_initial_version(deal, db)
        deal_v = ver_svc.create_new_version(
            deal.id,
            db,
            source="manual_upload",
            actor="seed",
            file_bytes=MSA_BASE_TEXT,
            filename="msa_alfalak_v1.txt",
            change_summary="Sent to counterparty",
            make_current=True,
            version_status="ready",
            run_pipeline=False,
        )
    else:
        deal_v = ver_svc.current_version(deal.id, db)

    tpl_v = ver_svc.current_version(DEMO_TEMPLATE_CONTRACT_ID, db)
    playbook = db.get(LegalPlaybook, DEFAULT_PLAYBOOK_ID)

    thread = NegotiationThread(
        id=DEMO_THREAD_ID,
        contract_id=DEMO_CONTRACT_ID,
        base_version_id=deal_v.id if deal_v else None,
        current_version_id=deal_v.id if deal_v else None,
        counterparty_name="Sarah Al-Mutairi",
        counterparty_email="legal@alfalak.example",
        subject="Master Service Agreement — Al-Falak Ltd",
        status="monitoring",
        monitoring_enabled=True,
        standard_template_version_id=tpl_v.id if tpl_v else None,
        playbook_id=playbook.id if playbook else None,
        external_thread_id="sim-thread-msa-alfalak-001",
        assigned_lawyer="demo-legal",
        created_by="seed",
        last_message_at=datetime.now(timezone.utc),
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)
    return thread

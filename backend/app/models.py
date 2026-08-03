import uuid

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

from .db import Base


def _uuid_pk():
    return Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Contract(Base):
    __tablename__ = "contracts"
    id = _uuid_pk()
    title = Column(Text)
    type = Column(Text)  # 'main' | 'subcontract'
    parent_main_contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=True)
    party_a = Column(Text)
    party_b = Column(Text)
    value_sar = Column(Numeric, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    governing_law = Column(Text, nullable=True)
    retention_pct = Column(Numeric, nullable=True)
    bond_expiry = Column(Date, nullable=True)
    warranty_end = Column(Date, nullable=True)
    language = Column(Text, nullable=True)  # 'ar' | 'en' | 'mixed'
    calendar = Column(Text, nullable=True)  # 'gregorian' | 'hijri' | 'mixed'
    status = Column(Text, nullable=False, default="processing")
    file_url = Column(Text)
    raw_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Clause(Base):
    __tablename__ = "clauses"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    clause_ref = Column(Text)
    quote = Column(Text)
    page = Column(Integer)
    char_start = Column(Integer)
    char_end = Column(Integer)


class Extraction(Base):
    __tablename__ = "extractions"
    __table_args__ = (UniqueConstraint("contract_id", "field_name"),)
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    field_name = Column(Text, nullable=False)
    value_json = Column(JSONB)
    confidence = Column(Numeric(3, 2))
    clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True)
    status = Column(Text, default="auto")  # 'auto' | 'verified' | 'edited'


class Obligation(Base):
    __tablename__ = "obligations"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    description = Column(Text)
    responsible_party = Column(Text)
    due_date = Column(Date, nullable=True)
    penalty_text = Column(Text, nullable=True)
    reminder_days_before = Column(Integer, default=3)
    status = Column(Text, default="pending")  # 'pending' | 'done' | 'overdue'
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))


# ---- Teammate tables (F2/F3/F4). Models provided for convenience; the AI
# ---- pipeline NEVER writes to these. See docs/README_HANDOFF.md.

class Deadline(Base):
    __tablename__ = "deadlines"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    type = Column(Text)
    label = Column(Text)
    notice_period_days = Column(Integer, nullable=True)
    deadline_date = Column(Date)
    severity = Column(Text)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))
    triggered_by_event_id = Column(UUID(as_uuid=True), nullable=True)


class Event(Base):
    __tablename__ = "events"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    type = Column(Text)
    description = Column(Text)
    event_date = Column(Date)


class PaymentMilestone(Base):
    __tablename__ = "payment_milestones"
    __table_args__ = (UniqueConstraint("contract_id", "seq"),)
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    seq = Column(Integer)
    label = Column(Text)
    amount_sar = Column(Numeric, nullable=True)
    preconditions = Column(JSONB)
    status = Column(Text)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))


class FlowdownFinding(Base):
    __tablename__ = "flowdown_findings"
    id = _uuid_pk()
    main_contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    subcontract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    obligation_summary = Column(Text)
    status = Column(Text)
    main_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))
    sub_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True)
    risk_note = Column(Text)
    severity = Column(Text)


class DemoSettings(Base):
    __tablename__ = "demo_settings"
    id = Column(Integer, primary_key=True, default=1)
    today = Column(Date, nullable=False)

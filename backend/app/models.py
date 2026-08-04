import uuid

from sqlalchemy import (
    Boolean,
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
    type = Column(Text, nullable=True)  # 'main' | 'subcontract' | NULL (derived from category)
    contract_category = Column(Text, nullable=True)
    supported = Column(Boolean, nullable=True)
    classification_confidence = Column(Numeric(3, 2), nullable=True)
    classification_message = Column(Text, nullable=True)
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
    title = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    notice_period_days = Column(Integer, nullable=True)
    deadline_date = Column(Date, nullable=True)
    source_trigger_date = Column(Date, nullable=True)
    severity = Column(Text)
    needs_review = Column(Boolean, nullable=False, default=False)
    review_reason = Column(Text, nullable=True)
    responsible_party = Column(Text, nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    generated = Column(Boolean, nullable=False, default=True)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))
    triggered_by_event_id = Column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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
    type = Column(Text, nullable=True)
    label = Column(Text)
    description = Column(Text, nullable=True)
    amount_sar = Column(Numeric, nullable=True)
    amount_percentage = Column(Numeric, nullable=True)
    due_date = Column(Date, nullable=True)
    preconditions = Column(JSONB)
    status = Column(Text)
    paid = Column(Boolean, nullable=False, default=False)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    generated = Column(Boolean, nullable=False, default=True)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FlowdownFinding(Base):
    __tablename__ = "flowdown_findings"
    id = _uuid_pk()
    main_contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    subcontract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), nullable=False)
    category = Column(Text, nullable=False, default="other")
    obligation_summary = Column(Text)
    status = Column(Text)
    main_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True)
    sub_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id"), nullable=True)
    explanation = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    explanation_ar = Column(Text, nullable=True)
    explanation_en = Column(Text, nullable=True)
    recommendation_ar = Column(Text, nullable=True)
    recommendation_en = Column(Text, nullable=True)
    main_citation = Column(Text, nullable=True)
    sub_citation = Column(Text, nullable=True)
    risk_note = Column(Text, nullable=True)
    severity = Column(Text)
    confidence = Column(Numeric(3, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DemoSettings(Base):
    __tablename__ = "demo_settings"
    id = Column(Integer, primary_key=True, default=1)
    today = Column(Date, nullable=False)

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
    relationship_type = Column(Text, nullable=True)  # parent | child | standalone
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
    execution_date = Column(Date, nullable=True)
    commencement_date = Column(Date, nullable=True)
    date_facts = Column(JSONB, nullable=True)
    governing_law = Column(Text, nullable=True)
    retention_pct = Column(Numeric, nullable=True)
    bond_expiry = Column(Date, nullable=True)
    warranty_end = Column(Date, nullable=True)
    language = Column(Text, nullable=True)  # 'ar' | 'en' | 'mixed'
    calendar = Column(Text, nullable=True)  # 'gregorian' | 'hijri' | 'mixed'
    status = Column(Text, nullable=False, default="processing")
    # Canonical entry stage per docs/contract-lifecycle-policy.md §3 — a
    # freshly created contract has not been through any lifecycle event yet.
    # Was "negotiation" (matching the historical DB column default below,
    # before the canonical lifecycle engine existed); see
    # database/migrations/019_contract_stage_default_draft.sql for the
    # matching DB-level fix (existing rows are untouched — DEFAULT only
    # affects future inserts that don't set `stage` explicitly).
    stage = Column(Text, nullable=False, default="draft")
    file_url = Column(Text)
    raw_text = Column(Text)
    page_layout = Column(JSONB, nullable=True)
    is_template = Column(Boolean, nullable=False, default=False)
    template_category = Column(Text, nullable=True)
    # Set when this contract was created via "Use Template" (see
    # ContractTemplate below / docs/signature-placement-and-template-flow-report.md).
    # NULL for every other creation path (normal upload).
    template_id = Column(UUID(as_uuid=True), ForeignKey("contract_templates.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContractSummary(Base):
    __tablename__ = "contract_summaries"
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id"), primary_key=True)
    status = Column(Text, nullable=False, default="not_generated")
    summary_ar = Column(JSONB, nullable=True)
    summary_en = Column(JSONB, nullable=True)
    error_code = Column(Text, nullable=True)
    error_detail = Column(Text, nullable=True)
    model = Column(Text, nullable=True)
    prompt_version = Column(Text, nullable=True)
    source_hash = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


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
    title = Column(Text, nullable=True)
    beneficiary = Column(Text, nullable=True)
    trigger_type = Column(Text, nullable=True)
    trigger_event = Column(Text, nullable=True)
    temporal_rule = Column(JSONB, nullable=True)
    dependencies = Column(JSONB, nullable=True)
    contract_required_evidence = Column(JSONB, nullable=True)
    suggested_evidence = Column(JSONB, nullable=True)
    completion_criteria = Column(Text, nullable=True)
    manual_status = Column(Boolean, nullable=False, default=False)


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
    event_type = Column(Text, nullable=True)
    status = Column(Text, nullable=True)
    temporal_rule = Column(JSONB, nullable=True)
    condition_key = Column(Text, nullable=True)
    calculation_explanation = Column(Text, nullable=True)
    calculation_explanation_ar = Column(Text, nullable=True)


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
    role = Column(Text, nullable=True)
    parent_seq = Column(Integer, nullable=True)
    frequency = Column(Text, nullable=True)
    due_rule = Column(JSONB, nullable=True)
    next_due_date = Column(Date, nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)
    responsible_party = Column(Text, nullable=True)
    beneficiary = Column(Text, nullable=True)
    trigger_event = Column(Text, nullable=True)
    temporal_rule = Column(JSONB, nullable=True)
    calculation_explanation = Column(Text, nullable=True)
    calculation_explanation_ar = Column(Text, nullable=True)


class RiskFinding(Base):
    __tablename__ = "risk_findings"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    category = Column(Text, nullable=False)
    code = Column(Text, nullable=False)
    points = Column(Integer, nullable=False, default=0)
    count = Column(Integer, nullable=False, default=1)
    explanation = Column(Text, nullable=True)
    explanation_ar = Column(Text, nullable=True)
    link_tab = Column(Text, nullable=True)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id", ondelete="SET NULL"), nullable=True)
    calculation_version = Column(Text, nullable=False, default="risk-v2")
    generated = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NegotiationOpportunity(Base):
    __tablename__ = "negotiation_opportunities"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    category = Column(Text, nullable=False)
    clause_ref = Column(Text, nullable=True)
    current_text = Column(Text, nullable=True)
    issue = Column(Text, nullable=True)
    business_impact = Column(Text, nullable=True)
    legal_impact = Column(Text, nullable=True)
    financial_impact = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    suggested_counterproposal = Column(Text, nullable=True)
    confidence = Column(Numeric(3, 2), nullable=True)
    human_decision_required = Column(Boolean, nullable=False, default=True)
    negotiability = Column(Text, nullable=True)
    source_clause_id = Column(UUID(as_uuid=True), ForeignKey("clauses.id", ondelete="SET NULL"), nullable=True)
    generated = Column(Boolean, nullable=False, default=True)
    human_decision = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


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


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (UniqueConstraint("contract_id", "version_number"),)
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    version_label = Column(Text, nullable=True)
    parent_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    source = Column(Text, nullable=False, default="initial_upload")
    status = Column(Text, nullable=False, default="draft")
    change_summary = Column(Text, nullable=True)
    file_path = Column(Text, nullable=True)
    extracted_json = Column(JSONB, nullable=True)
    ai_summary = Column(Text, nullable=True)
    created_by = Column(Text, nullable=True)
    review_request_id = Column(UUID(as_uuid=True), nullable=True)
    negotiation_id = Column(UUID(as_uuid=True), nullable=True)
    approval_workflow_id = Column(UUID(as_uuid=True), nullable=True)
    signature_request_id = Column(UUID(as_uuid=True), nullable=True)
    hash_sha256 = Column(Text, nullable=True)
    is_current = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class VersionComparison(Base):
    __tablename__ = "version_comparisons"
    __table_args__ = (UniqueConstraint("from_version_id", "to_version_id"),)
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    from_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="CASCADE"), nullable=False)
    to_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="CASCADE"), nullable=False)
    diff_json = Column(JSONB, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReviewRequest(Base):
    __tablename__ = "review_requests"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    token = Column(Text, nullable=True, unique=True)
    token_nonce = Column(Text, nullable=True)
    token_hash = Column(Text, nullable=True, unique=True)
    recipient_name = Column(Text, nullable=False)
    recipient_email = Column(Text, nullable=False)
    sender_name = Column(Text, nullable=True)
    sender_email = Column(Text, nullable=True)
    message = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="sent")
    expires_at = Column(DateTime(timezone=True), nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReviewComment(Base):
    __tablename__ = "review_comments"
    id = _uuid_pk()
    review_request_id = Column(
        UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=False
    )
    clause_ref = Column(Text, nullable=True)
    page = Column(Integer, nullable=True)
    comment = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReviewResponse(Base):
    __tablename__ = "review_responses"
    id = _uuid_pk()
    review_request_id = Column(
        UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    decision = Column(Text, nullable=False)
    overall_comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Negotiation(Base):
    __tablename__ = "negotiations"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    review_request_id = Column(UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="SET NULL"), nullable=True)
    review_comment_id = Column(UUID(as_uuid=True), ForeignKey("review_comments.id", ondelete="SET NULL"), nullable=True)
    clause_ref = Column(Text, nullable=True)
    original_clause = Column(Text, nullable=True)
    reviewer_comment = Column(Text, nullable=True)
    reviewer_decision = Column(Text, nullable=True)
    ai_summary = Column(Text, nullable=True)
    business_impact = Column(Text, nullable=True)
    legal_impact = Column(Text, nullable=True)
    risk_level = Column(Text, nullable=True)
    recommendation = Column(Text, nullable=True)
    reasoning = Column(Text, nullable=True)
    counter_clause = Column(Text, nullable=True)
    counter_clause_ar = Column(Text, nullable=True)
    pros = Column(JSONB, nullable=True)
    cons = Column(JSONB, nullable=True)
    status = Column(Text, nullable=False, default="draft")
    edited_by_lawyer = Column(Boolean, nullable=False, default=False)
    sent_review_request_id = Column(UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="SET NULL"), nullable=True)
    workflow_status = Column(Text, nullable=False, default="pending_analysis")
    lawyer_final_clause = Column(Text, nullable=True)
    lawyer_final_clause_ar = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    final_summary = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NegotiationMessage(Base):
    __tablename__ = "negotiation_messages"
    id = _uuid_pk()
    negotiation_id = Column(UUID(as_uuid=True), ForeignKey("negotiations.id", ondelete="CASCADE"), nullable=False)
    author = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    status = Column(Text, nullable=False, default="in_progress")
    current_step_order = Column(Integer, nullable=False, default=1)
    started_by = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    # Snapshot of the configured route this workflow was started from — see
    # ContractApprovalRoute below / docs/configurable-approval-routes-report.md.
    route_name = Column(Text, nullable=True)
    contract_route_id = Column(UUID(as_uuid=True), ForeignKey("contract_approval_routes.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApprovalStep(Base):
    __tablename__ = "approval_steps"
    __table_args__ = (UniqueConstraint("workflow_id", "step_order"),)
    id = _uuid_pk()
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("approval_workflows.id", ondelete="CASCADE"), nullable=False)
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)
    approver_name = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="locked")
    required = Column(Boolean, nullable=False, default=True)
    comment = Column(Text, nullable=True)
    acted_at = Column(DateTime(timezone=True), nullable=True)
    acted_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApprovalRoute(Base):
    """A reusable, saved approval-route template — never bound to one
    contract. Selecting it for a contract copies its steps into a
    ContractApprovalRoute; later edits here never mutate that copy."""

    __tablename__ = "approval_routes"
    id = _uuid_pk()
    name = Column(Text, nullable=False)
    scope = Column(Text, nullable=False, default="default")
    active = Column(Boolean, nullable=False, default=True)
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ApprovalRouteStep(Base):
    __tablename__ = "approval_route_steps"
    __table_args__ = (UniqueConstraint("route_id", "step_order"),)
    id = _uuid_pk()
    route_id = Column(UUID(as_uuid=True), ForeignKey("approval_routes.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)
    approver_name = Column(Text, nullable=True)
    required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ContractApprovalRoute(Base):
    """The configured route for one contract, before (and then snapshotted
    into) an ApprovalWorkflow. 'draft' while editable; 'started' once a
    workflow has been created from it (locked); 'cancelled' once its
    workflow is cancelled (a fresh configure() call then makes a new draft
    rather than reusing/mutating this row)."""

    __tablename__ = "contract_approval_routes"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=True)
    source_route_id = Column(UUID(as_uuid=True), ForeignKey("approval_routes.id", ondelete="SET NULL"), nullable=True)
    status = Column(Text, nullable=False, default="draft")
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContractApprovalRouteStep(Base):
    __tablename__ = "contract_approval_route_steps"
    __table_args__ = (UniqueConstraint("contract_route_id", "step_order"),)
    id = _uuid_pk()
    contract_route_id = Column(UUID(as_uuid=True), ForeignKey("contract_approval_routes.id", ondelete="CASCADE"), nullable=False)
    step_order = Column(Integer, nullable=False)
    role = Column(Text, nullable=False)
    approver_name = Column(Text, nullable=True)
    required = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    event_type = Column(Text, nullable=False)
    actor = Column(Text, nullable=True)
    role = Column(Text, nullable=True)
    step_order = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class SignatureRequest(Base):
    __tablename__ = "signature_requests"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    provider = Column(Text, nullable=False, default="simulated")
    external_id = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="draft")
    created_by = Column(Text, nullable=True)
    subject = Column(Text, nullable=False)
    message = Column(Text, nullable=True)
    signing_order_enabled = Column(Boolean, nullable=False, default=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    declined_at = Column(DateTime(timezone=True), nullable=True)
    decline_reason = Column(Text, nullable=True)
    original_file_url = Column(Text, nullable=True)
    signed_file_url = Column(Text, nullable=True)
    certificate_file_url = Column(Text, nullable=True)
    original_hash = Column(Text, nullable=True)
    signed_hash = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SignatureSigner(Base):
    __tablename__ = "signature_signers"
    __table_args__ = (UniqueConstraint("signature_request_id", "signer_order"),)
    id = _uuid_pk()
    signature_request_id = Column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False
    )
    signer_order = Column(Integer, nullable=False)
    name = Column(Text, nullable=False)
    email = Column(Text, nullable=False)
    role = Column(Text, nullable=False)
    token_hash = Column(Text, nullable=False, unique=True)
    token_nonce = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="waiting")
    opened_at = Column(DateTime(timezone=True), nullable=True)
    signed_at = Column(DateTime(timezone=True), nullable=True)
    declined_at = Column(DateTime(timezone=True), nullable=True)
    decline_reason = Column(Text, nullable=True)
    signature_type = Column(Text, nullable=True)
    signature_value_url = Column(Text, nullable=True)
    consent_text = Column(Text, nullable=True)
    ip_address = Column(Text, nullable=True)
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SignatureField(Base):
    """A placed field (signature/initials/name/date) for one signer,
    anchored to a specific page and normalized (0..1) position within the
    document that was current when the field was saved. Drives both the
    internal placement UI and where the signer's mark is actually embedded
    in the final signed PDF — see app/services/signature_pdf.py."""

    __tablename__ = "signature_fields"
    id = _uuid_pk()
    signature_request_id = Column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False
    )
    signer_id = Column(UUID(as_uuid=True), ForeignKey("signature_signers.id", ondelete="CASCADE"), nullable=False)
    version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    page_number = Column(Integer, nullable=False)
    x = Column(Numeric(7, 5), nullable=False)
    y = Column(Numeric(7, 5), nullable=False)
    width = Column(Numeric(7, 5), nullable=False)
    height = Column(Numeric(7, 5), nullable=False)
    field_type = Column(Text, nullable=False, default="signature")
    required = Column(Boolean, nullable=False, default=True)
    ai_suggested = Column(Boolean, nullable=False, default=False)
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ContractTemplate(Base):
    """A reusable contract template backing the Templates page's "Use
    Template" flow — real, backend-persisted variables/clauses, not a
    frontend-only seed list."""

    __tablename__ = "contract_templates"
    id = _uuid_pk()
    key = Column(Text, nullable=False, unique=True)
    title_en = Column(Text, nullable=False)
    title_ar = Column(Text, nullable=False)
    category = Column(Text, nullable=True)
    language = Column(Text, nullable=False, default="both")
    industry = Column(Text, nullable=True)
    description_en = Column(Text, nullable=True)
    description_ar = Column(Text, nullable=True)
    variables = Column(JSONB, nullable=False, default=dict)
    clauses = Column(JSONB, nullable=False, default=dict)
    usage_count = Column(Integer, nullable=False, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"
    id = _uuid_pk()
    message_type = Column(Text, nullable=False)
    recipient = Column(Text, nullable=False)
    subject = Column(Text, nullable=False)
    contract_id = Column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    review_request_id = Column(
        UUID(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE"), nullable=True
    )
    signature_request_id = Column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=True
    )
    signer_id = Column(
        UUID(as_uuid=True), ForeignKey("signature_signers.id", ondelete="CASCADE"), nullable=True
    )
    status = Column(Text, nullable=False, default="pending")
    attempt_count = Column(Integer, nullable=False, default=0)
    provider_message_id = Column(Text, nullable=True)
    safe_error_code = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    sent_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)


class LegalPlaybook(Base):
    __tablename__ = "legal_playbooks"
    id = _uuid_pk()
    name = Column(Text, nullable=False)
    contract_category = Column(Text, nullable=True)
    language = Column(Text, nullable=False, default="ar")
    status = Column(Text, nullable=False, default="active")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PlaybookRule(Base):
    __tablename__ = "playbook_rules"
    id = _uuid_pk()
    playbook_id = Column(UUID(as_uuid=True), ForeignKey("legal_playbooks.id", ondelete="CASCADE"), nullable=False)
    clause_category = Column(Text, nullable=False)
    rule_name = Column(Text, nullable=False)
    preferred_position = Column(Text, nullable=True)
    fallback_position = Column(Text, nullable=True)
    unacceptable_position = Column(Text, nullable=True)
    approval_required_role = Column(Text, nullable=True)
    severity = Column(Text, nullable=False, default="medium")
    guidance = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NegotiationThread(Base):
    __tablename__ = "negotiation_threads"
    id = _uuid_pk()
    contract_id = Column(UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False)
    base_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    current_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    counterparty_name = Column(Text, nullable=True)
    counterparty_email = Column(Text, nullable=True)
    subject = Column(Text, nullable=True)
    status = Column(Text, nullable=False, default="draft")
    monitoring_enabled = Column(Boolean, nullable=False, default=True)
    standard_template_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    playbook_id = Column(UUID(as_uuid=True), ForeignKey("legal_playbooks.id", ondelete="SET NULL"), nullable=True)
    assigned_lawyer = Column(Text, nullable=True)
    external_thread_id = Column(Text, nullable=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)
    last_analyzed_at = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NegotiationEmail(Base):
    __tablename__ = "negotiation_emails"
    id = _uuid_pk()
    thread_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_threads.id", ondelete="CASCADE"), nullable=True)
    external_message_id = Column(Text, nullable=True)
    external_thread_id = Column(Text, nullable=True)
    provider = Column(Text, nullable=False, default="simulated")
    direction = Column(Text, nullable=False, default="inbound")
    sender_name = Column(Text, nullable=True)
    sender_email = Column(Text, nullable=True)
    recipients_json = Column(JSONB, nullable=True)
    cc_json = Column(JSONB, nullable=True)
    subject = Column(Text, nullable=True)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    reply_reference = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    classification = Column(Text, nullable=True)
    processing_status = Column(Text, nullable=False, default="received")
    linked_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    requires_response = Column(Boolean, nullable=False, default=False)
    match_confidence = Column(Numeric(4, 3), nullable=True)
    needs_manual_link = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NegotiationAttachment(Base):
    __tablename__ = "negotiation_attachments"
    id = _uuid_pk()
    email_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_emails.id", ondelete="CASCADE"), nullable=False)
    filename = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=True)
    size_bytes = Column(Integer, nullable=True)
    file_url = Column(Text, nullable=True)
    file_hash_sha256 = Column(Text, nullable=True)
    document_type = Column(Text, nullable=True)
    processing_status = Column(Text, nullable=False, default="received")
    created_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NegotiationReviewPackage(Base):
    __tablename__ = "negotiation_review_packages"
    id = _uuid_pk()
    thread_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_threads.id", ondelete="CASCADE"), nullable=False)
    email_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_emails.id", ondelete="SET NULL"), nullable=True)
    base_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    proposed_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    template_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    executive_summary = Column(Text, nullable=True)
    overall_risk_score = Column(Integer, nullable=True)
    recommendation = Column(Text, nullable=True)
    package_json = Column(JSONB, nullable=True)
    status = Column(Text, nullable=False, default="generating")
    generated_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(Text, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    draft_email_subject_en = Column(Text, nullable=True)
    draft_email_subject_ar = Column(Text, nullable=True)
    draft_email_body_en = Column(Text, nullable=True)
    draft_email_body_ar = Column(Text, nullable=True)
    lawyer_edited_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NegotiationRound(Base):
    __tablename__ = "negotiation_rounds"
    __table_args__ = (UniqueConstraint("thread_id", "round_number"),)
    id = _uuid_pk()
    thread_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_threads.id", ondelete="CASCADE"), nullable=False)
    round_number = Column(Integer, nullable=False)
    inbound_email_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_emails.id", ondelete="SET NULL"), nullable=True)
    outbound_email_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_emails.id", ondelete="SET NULL"), nullable=True)
    base_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    proposed_version_id = Column(UUID(as_uuid=True), ForeignKey("contract_versions.id", ondelete="SET NULL"), nullable=True)
    review_package_id = Column(UUID(as_uuid=True), ForeignKey("negotiation_review_packages.id", ondelete="SET NULL"), nullable=True)
    status = Column(Text, nullable=False, default="received")
    opened_at = Column(DateTime(timezone=True), server_default=func.now())
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CounterpartyProfile(Base):
    __tablename__ = "counterparty_profiles"
    id = _uuid_pk()
    counterparty_email = Column(Text, nullable=False, unique=True)
    counterparty_name = Column(Text, nullable=True)
    memory_json = Column(JSONB, nullable=True)
    computed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SignatureEvent(Base):
    __tablename__ = "signature_events"
    id = _uuid_pk()
    signature_request_id = Column(
        UUID(as_uuid=True), ForeignKey("signature_requests.id", ondelete="CASCADE"), nullable=False
    )
    signer_id = Column(UUID(as_uuid=True), ForeignKey("signature_signers.id", ondelete="SET NULL"), nullable=True)
    actor = Column(Text, nullable=True)
    action = Column(Text, nullable=False)
    event_metadata = Column("metadata", JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

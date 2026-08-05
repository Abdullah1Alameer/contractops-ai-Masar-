"""Link inbound emails to negotiation threads."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ...models import Contract, ContractVersion, NegotiationAttachment, NegotiationEmail, NegotiationThread

GENERIC_SUBJECTS = frozenset(
    {"re:", "fwd:", "hello", "hi", "thanks", "thank you", "follow up", "follow-up", "contract", "agreement"}
)


@dataclass
class MatchCandidate:
    thread_id: uuid.UUID
    contract_id: uuid.UUID
    contract_title: str | None
    confidence: float
    reason: str


@dataclass
class MatchResult:
    thread_id: uuid.UUID | None
    confidence: float
    needs_review: bool
    candidates: list[MatchCandidate]


def _norm_subject(subject: str | None) -> str:
    if not subject:
        return ""
    s = re.sub(r"^(re|fwd):\s*", "", subject.strip(), flags=re.I)
    return s.strip().lower()


def _is_generic_subject(subject: str | None) -> bool:
    n = _norm_subject(subject)
    if not n or len(n) < 8:
        return True
    words = set(n.split())
    if words <= GENERIC_SUBJECTS or len(words) <= 2:
        return True
    return False


def _contract_ref_in_subject(subject: str | None, db: Session) -> Contract | None:
    if _is_generic_subject(subject):
        return None
    n = _norm_subject(subject)
    rows = db.query(Contract).filter(Contract.is_template.is_(False)).limit(200).all()
    best: Contract | None = None
    best_len = 0
    for c in rows:
        title = (c.title or "").strip().lower()
        if len(title) >= 10 and title in n:
            if len(title) > best_len:
                best = c
                best_len = len(title)
    return best


def link_email_to_thread(
    db: Session,
    *,
    email: NegotiationEmail,
    external_thread_id: str | None = None,
    reply_reference: str | None = None,
    sender_email: str | None = None,
    subject: str | None = None,
    file_hash: str | None = None,
    explicit_thread_id: uuid.UUID | None = None,
) -> MatchResult:
    if explicit_thread_id:
        t = db.get(NegotiationThread, explicit_thread_id)
        if t:
            return MatchResult(thread_id=t.id, confidence=1.0, needs_review=False, candidates=[])

    ext_tid = external_thread_id or email.external_thread_id
    if ext_tid:
        row = db.query(NegotiationThread).filter_by(external_thread_id=ext_tid).first()
        if row:
            return MatchResult(
                thread_id=row.id,
                confidence=0.98,
                needs_review=False,
                candidates=[
                    MatchCandidate(row.id, row.contract_id, None, 0.98, "external_thread_id"),
                ],
            )

    ref = reply_reference or email.reply_reference
    if ref:
        prior = (
            db.query(NegotiationEmail)
            .filter(NegotiationEmail.reply_reference == ref)
            .order_by(NegotiationEmail.created_at.desc())
            .first()
        )
        if prior and prior.thread_id:
            t = db.get(NegotiationThread, prior.thread_id)
            if t:
                return MatchResult(thread_id=t.id, confidence=0.95, needs_review=False, candidates=[])

    subj = subject or email.subject
    contract = _contract_ref_in_subject(subj, db)
    if contract:
        t = (
            db.query(NegotiationThread)
            .filter_by(contract_id=contract.id, status="monitoring")
            .order_by(NegotiationThread.updated_at.desc())
            .first()
        )
        if t is None:
            t = (
                db.query(NegotiationThread)
                .filter_by(contract_id=contract.id)
                .order_by(NegotiationThread.updated_at.desc())
                .first()
            )
        if t:
            return MatchResult(
                thread_id=t.id,
                confidence=0.85,
                needs_review=False,
                candidates=[MatchCandidate(t.id, contract.id, contract.title, 0.85, "subject_reference")],
            )

    sender = (sender_email or email.sender_email or "").strip().lower()
    if sender:
        threads = (
            db.query(NegotiationThread)
            .filter(NegotiationThread.counterparty_email.ilike(sender))
            .filter(NegotiationThread.status.in_(("monitoring", "awaiting_counterparty", "counterparty_responded")))
            .order_by(NegotiationThread.updated_at.desc())
            .limit(5)
            .all()
        )
        if len(threads) == 1:
            t = threads[0]
            return MatchResult(
                thread_id=t.id,
                confidence=0.75,
                needs_review=False,
                candidates=[MatchCandidate(t.id, t.contract_id, None, 0.75, "counterparty_active")],
            )
        if len(threads) > 1:
            cands = [
                MatchCandidate(t.id, t.contract_id, None, 0.5, "counterparty_ambiguous") for t in threads
            ]
            return MatchResult(thread_id=None, confidence=0.4, needs_review=True, candidates=cands)

    if file_hash:
        att = (
            db.query(NegotiationAttachment)
            .filter_by(file_hash_sha256=file_hash)
            .order_by(NegotiationAttachment.created_at.desc())
            .first()
        )
        if att:
            em = db.get(NegotiationEmail, att.email_id)
            if em and em.thread_id:
                t = db.get(NegotiationThread, em.thread_id)
                if t:
                    return MatchResult(thread_id=t.id, confidence=0.7, needs_review=False, candidates=[])

        for v in db.query(ContractVersion).filter_by(hash_sha256=file_hash).limit(3).all():
            t = (
                db.query(NegotiationThread)
                .filter_by(contract_id=v.contract_id)
                .order_by(NegotiationThread.updated_at.desc())
                .first()
            )
            if t:
                return MatchResult(
                    thread_id=t.id,
                    confidence=0.65,
                    needs_review=False,
                    candidates=[MatchCandidate(t.id, v.contract_id, None, 0.65, "document_hash")],
                )

    if _is_generic_subject(subj) and not sender:
        return MatchResult(thread_id=None, confidence=0.0, needs_review=True, candidates=[])

    return MatchResult(thread_id=None, confidence=0.0, needs_review=True, candidates=[])

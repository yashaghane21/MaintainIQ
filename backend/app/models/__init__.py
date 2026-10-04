"""Persistence-level constants: collection names, enums and ID generation.

Documents are stored as plain dicts in MongoDB; request/response shapes live
in `app.schemas`. Human-readable business IDs (ISS-..., WO-...) are used in
URLs, and Mongo's ObjectId `_id` is never exposed to clients.
"""

import uuid
from datetime import datetime, timezone
from enum import StrEnum


class Collections:
    EQUIPMENT = "equipment"
    ISSUES = "issues"
    WORK_ORDERS = "work_orders"
    KNOWLEDGE_DOCUMENTS = "knowledge_documents"
    # Extracted text kept separately so the vector index can be rebuilt on hosts
    # with ephemeral disks (e.g. Render free tier).
    KNOWLEDGE_TEXTS = "knowledge_document_texts"


class IssueStatus(StrEnum):
    REPORTED = "reported"                      # saved, not yet analysed
    ANALYSIS_FAILED = "analysis_failed"        # last analysis attempt failed; issue preserved
    AWAITING_REVIEW = "awaiting_review"        # analysis done, work order draft awaiting technician
    WORK_ORDER_APPROVED = "work_order_approved"
    WORK_ORDER_REJECTED = "work_order_rejected"


OPEN_ISSUE_STATUSES = [
    IssueStatus.REPORTED, IssueStatus.ANALYSIS_FAILED,
    IssueStatus.AWAITING_REVIEW, IssueStatus.WORK_ORDER_REJECTED,
]


class WorkOrderStatus(StrEnum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"   # replaced by a newer AI draft after re-analysis


# Allowed transitions. Approved and rejected are terminal: decisions are never overwritten.
WORK_ORDER_TRANSITIONS: dict[WorkOrderStatus, set[WorkOrderStatus]] = {
    WorkOrderStatus.PENDING_REVIEW: {WorkOrderStatus.APPROVED, WorkOrderStatus.REJECTED, WorkOrderStatus.SUPERSEDED},
    WorkOrderStatus.APPROVED: set(),
    WorkOrderStatus.REJECTED: set(),
    WorkOrderStatus.SUPERSEDED: set(),
}


class Priority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


PRIORITY_RANK = {Priority.LOW: 0, Priority.MEDIUM: 1, Priority.HIGH: 2, Priority.CRITICAL: 3}


class EquipmentStatus(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    DOWN = "down"
    MAINTENANCE = "maintenance"


class IngestionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"

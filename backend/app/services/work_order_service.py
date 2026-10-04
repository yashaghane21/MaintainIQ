"""Human-in-the-loop work order lifecycle.

State machine (see app.models.WORK_ORDER_TRANSITIONS):

    pending_review --approve--> approved   (terminal)
    pending_review --reject---> rejected   (terminal)
    pending_review --re-analysis--> superseded (terminal)

Transitions use a conditional `find_one_and_update` filtered on the current
status, so two concurrent decisions cannot both succeed. Every change is
appended to `audit_log`; `original_draft` is written once and never changed.

Only the HTTP approve/reject endpoints (driven by a person confirming in the
UI) call `approve`/`reject`. The triage/AI code path never imports them.
"""

from pymongo import ReturnDocument
from pymongo.database import Database

from app.core.errors import ConflictError, NotFoundError
from app.core.logging import get_logger
from app.models import (WORK_ORDER_TRANSITIONS, Collections, IssueStatus, WorkOrderStatus, new_id, utcnow)
from app.schemas.work_order import WorkOrderApprove, WorkOrderReject, WorkOrderUpdate
from app.services.issue_service import status_entry
from app.utils.serialization import serialize_doc

logger = get_logger(__name__)
EDITABLE_FIELDS = ("title", "description", "priority", "checklist", "technician_notes")


def _snapshot(doc: dict) -> dict:
    return {k: doc.get(k) for k in ("title", "description", "priority", "checklist", "technician_notes")}


def _audit(action: str, actor: str, note: str | None = None, changes: dict | None = None) -> dict:
    return {"action": action, "actor": actor, "at": utcnow(), "note": note, "changes": changes}


def get_work_order(db: Database, work_order_id: str) -> dict:
    doc = db[Collections.WORK_ORDERS].find_one({"work_order_id": work_order_id}, {"_id": 0})
    if not doc:
        raise NotFoundError(f"Work order '{work_order_id}' not found")
    return serialize_doc(doc)


def list_work_orders(db: Database, *, status=None, priority=None, equipment_id=None, issue_id=None, limit: int = 200) -> list[dict]:
    query = {k: v for k, v in {"approval_status": status, "priority": priority, "equipment_id": equipment_id,
                                "issue_id": issue_id}.items() if v}
    cursor = db[Collections.WORK_ORDERS].find(query, {"_id": 0, "audit_log": 0, "original_draft": 0}).sort("created_at", -1).limit(limit)
    return [serialize_doc(d) for d in cursor]


def create_from_analysis(db: Database, issue: dict, analysis: dict) -> dict:
    """Create a draft from AI output. The draft always starts in pending_review."""
    output = analysis["output"]
    now = utcnow()
    draft = {
        "title": output["work_order"]["title"],
        "description": output["work_order"]["description"],
        "priority": output["suggested_priority"],
        "checklist": [{"text": item, "done": False} for item in output["work_order"]["checklist"]],
        "technician_notes": "",
    }
    source = f"{analysis['provider']}{' (simulated)' if analysis['is_simulated'] else ''}"
    doc = {
        "work_order_id": new_id("WO"),
        "issue_id": issue["issue_id"],
        "equipment_id": issue["equipment_id"],
        "equipment_name": issue.get("equipment_name"),
        "analysis_version": analysis["version"],
        "is_simulated": analysis["is_simulated"],
        **draft,
        "approval_status": WorkOrderStatus.PENDING_REVIEW.value,
        "reviewer": None,
        "decision_reason": None,
        "original_draft": dict(draft),
        "approved_version": None,
        "audit_log": [_audit("created", f"system: AI draft via {source}", "Draft generated; awaiting technician review")],
        "created_at": now,
        "updated_at": now,
        "reviewed_at": None,
    }
    db[Collections.WORK_ORDERS].insert_one(doc)
    return get_work_order(db, doc["work_order_id"])


def _transition(db: Database, work_order_id: str, target: WorkOrderStatus, update: dict, audit: dict) -> dict:
    current = get_work_order(db, work_order_id)
    status = WorkOrderStatus(current["approval_status"])
    if target not in WORK_ORDER_TRANSITIONS[status]:
        raise ConflictError(
            f"Invalid transition: work order is '{status.value}' and cannot become '{target.value}'.",
            details={"current_status": status.value, "requested": target.value},
        )
    result = db[Collections.WORK_ORDERS].find_one_and_update(
        {"work_order_id": work_order_id, "approval_status": status.value},   # optimistic guard
        {"$set": {**update, "approval_status": target.value, "updated_at": utcnow()}, "$push": {"audit_log": audit}},
        projection={"_id": 1}, return_document=ReturnDocument.BEFORE,
    )
    if result is None:   # guard did not match -> someone else changed the status first
        raise ConflictError("Work order was modified concurrently; reload and try again.")
    return get_work_order(db, work_order_id)


def _set_issue_status(db: Database, issue_id: str, status: IssueStatus, actor: str, note: str | None, priority: str | None = None):
    update = {"status": status.value, "updated_at": utcnow()}
    if priority:
        update["priority"] = priority
    db[Collections.ISSUES].update_one(
        {"issue_id": issue_id}, {"$set": update, "$push": {"status_history": status_entry(status.value, actor, note)}})


def update_work_order(db: Database, work_order_id: str, data: WorkOrderUpdate) -> dict:
    current = get_work_order(db, work_order_id)
    if current["approval_status"] != WorkOrderStatus.PENDING_REVIEW.value:
        raise ConflictError(f"Work order is '{current['approval_status']}' and can no longer be edited.")

    incoming = data.model_dump(exclude_unset=True, exclude={"editor"})
    if "checklist" in incoming and incoming["checklist"] is not None:
        incoming["checklist"] = [dict(item) for item in incoming["checklist"]]
    changes = {f: {"from": current.get(f), "to": v} for f, v in incoming.items() if v is not None and current.get(f) != v}
    if not changes:
        return current

    result = db[Collections.WORK_ORDERS].find_one_and_update(
        {"work_order_id": work_order_id, "approval_status": WorkOrderStatus.PENDING_REVIEW.value},
        {"$set": {**{f: c["to"] for f, c in changes.items()}, "updated_at": utcnow()},
         "$push": {"audit_log": _audit("edited", data.editor, f"Edited: {', '.join(changes)}", changes)}},
        projection={"_id": 1}, return_document=ReturnDocument.BEFORE,
    )
    if result is None:
        raise ConflictError("Work order was reviewed concurrently and can no longer be edited.")
    if "priority" in changes:
        db[Collections.ISSUES].update_one({"issue_id": current["issue_id"]}, {"$set": {"priority": changes["priority"]["to"]}})
    logger.info("Work order edited", extra={"work_order_id": work_order_id, "decision": "edited"})
    return get_work_order(db, work_order_id)


def approve_work_order(db: Database, work_order_id: str, data: WorkOrderApprove) -> dict:
    current = get_work_order(db, work_order_id)
    notes = data.technician_notes if data.technician_notes is not None else current.get("technician_notes")
    approved_version = {**_snapshot(current), "technician_notes": notes}
    now = utcnow()
    result = _transition(
        db, work_order_id, WorkOrderStatus.APPROVED,
        {"reviewer": data.reviewer, "reviewed_at": now, "technician_notes": notes, "approved_version": approved_version},
        _audit("approved", data.reviewer, "Approved by technician after explicit confirmation"),
    )
    _set_issue_status(db, current["issue_id"], IssueStatus.WORK_ORDER_APPROVED, data.reviewer,
                      f"Work order {work_order_id} approved", priority=current["priority"])
    logger.info("Work order approved", extra={"work_order_id": work_order_id, "issue_id": current["issue_id"], "decision": "approved"})
    return result


def reject_work_order(db: Database, work_order_id: str, data: WorkOrderReject) -> dict:
    current = get_work_order(db, work_order_id)
    result = _transition(
        db, work_order_id, WorkOrderStatus.REJECTED,
        {"reviewer": data.reviewer, "reviewed_at": utcnow(), "decision_reason": data.reason},
        _audit("rejected", data.reviewer, data.reason),
    )
    _set_issue_status(db, current["issue_id"], IssueStatus.WORK_ORDER_REJECTED, data.reviewer,
                      f"Work order {work_order_id} rejected: {data.reason}")
    logger.info("Work order rejected", extra={"work_order_id": work_order_id, "issue_id": current["issue_id"], "decision": "rejected"})
    return result


def supersede_pending(db: Database, issue_id: str, reason: str) -> list[str]:
    """Mark pending drafts for an issue as superseded (used before creating a new draft)."""
    ids = [d["work_order_id"] for d in db[Collections.WORK_ORDERS].find(
        {"issue_id": issue_id, "approval_status": WorkOrderStatus.PENDING_REVIEW.value}, {"work_order_id": 1})]
    for wo_id in ids:
        _transition(db, wo_id, WorkOrderStatus.SUPERSEDED, {}, _audit("superseded", "system", reason))
    return ids


def has_approved_work_order(db: Database, issue_id: str) -> bool:
    return db[Collections.WORK_ORDERS].count_documents(
        {"issue_id": issue_id, "approval_status": WorkOrderStatus.APPROVED.value}) > 0

"""Dashboard metrics, computed from live database contents (nothing hard-coded)."""

from datetime import timedelta

from pymongo.database import Database

from app.models import OPEN_ISSUE_STATUSES, Collections, utcnow
from app.utils.serialization import serialize_doc

_OPEN = [str(s) for s in OPEN_ISSUE_STATUSES]


def get_summary(db: Database) -> dict:
    issues = db[Collections.ISSUES]
    wos = db[Collections.WORK_ORDERS]
    equipment = db[Collections.EQUIPMENT]

    priority_distribution = {p: issues.count_documents({"status": {"$in": _OPEN}, "priority": p})
                             for p in ("low", "medium", "high", "critical")}
    priority_distribution["unassessed"] = issues.count_documents({"status": {"$in": _OPEN}, "priority": None})

    equipment_status = {s: equipment.count_documents({"status": s}) for s in ("operational", "degraded", "down", "maintenance")}
    work_order_status = {s: wos.count_documents({"approval_status": s}) for s in ("pending_review", "approved", "rejected", "superseded")}

    # Issues reported per day, last 14 days.
    today = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = today - timedelta(days=13)
    per_day = {(start + timedelta(days=i)).date().isoformat(): 0 for i in range(14)}
    decided_per_day = dict.fromkeys(per_day, 0)
    for doc in issues.find({"created_at": {"$gte": start}}, {"created_at": 1}):
        key = serialize_doc(doc)["created_at"].date().isoformat()
        if key in per_day:
            per_day[key] += 1
    for doc in wos.find({"reviewed_at": {"$gte": start}}, {"reviewed_at": 1}):
        key = serialize_doc(doc)["reviewed_at"].date().isoformat()
        if key in decided_per_day:
            decided_per_day[key] += 1

    recent_issues = [serialize_doc(d) for d in issues.find(
        {}, {"_id": 0, "issue_id": 1, "equipment_id": 1, "equipment_name": 1, "description": 1, "priority": 1,
             "status": 1, "created_at": 1, "threshold_summary.highest_severity": 1},
    ).sort("created_at", -1).limit(6)]
    recent_decisions = [serialize_doc(d) for d in wos.find(
        {"reviewed_at": {"$ne": None}},
        {"_id": 0, "work_order_id": 1, "title": 1, "approval_status": 1, "reviewer": 1, "reviewed_at": 1, "equipment_id": 1},
    ).sort("reviewed_at", -1).limit(5)]

    return {
        "kpis": {
            "total_equipment": equipment.count_documents({}),
            "open_issues": issues.count_documents({"status": {"$in": _OPEN}}),
            "high_priority_issues": issues.count_documents({"status": {"$in": _OPEN}, "priority": {"$in": ["high", "critical"]}}),
            "pending_work_orders": work_order_status["pending_review"],
        },
        "priority_distribution": priority_distribution,
        "equipment_status": equipment_status,
        "work_order_status": work_order_status,
        "activity": [{"date": d, "issues_reported": per_day[d], "work_orders_decided": decided_per_day[d]} for d in per_day],
        "recent_issues": recent_issues,
        "recent_decisions": recent_decisions,
    }

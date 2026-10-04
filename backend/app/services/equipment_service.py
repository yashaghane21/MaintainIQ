import re

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from app.core.errors import ConflictError, NotFoundError
from app.models import OPEN_ISSUE_STATUSES, Collections, utcnow
from app.schemas.equipment import EquipmentCreate
from app.utils.serialization import serialize_doc

_PROJECTION = {"_id": 0}


def get_equipment(db: Database, equipment_id: str) -> dict:
    doc = db[Collections.EQUIPMENT].find_one({"equipment_id": equipment_id}, _PROJECTION)
    if not doc:
        raise NotFoundError(f"Equipment '{equipment_id}' not found")
    return serialize_doc(doc)


def _enrich(db: Database, items: list[dict]) -> list[dict]:
    for item in items:
        issues = db[Collections.ISSUES]
        item["open_issue_count"] = issues.count_documents(
            {"equipment_id": item["equipment_id"], "status": {"$in": [str(s) for s in OPEN_ISSUE_STATUSES]}})
        last = issues.find_one({"equipment_id": item["equipment_id"]}, {"created_at": 1}, sort=[("created_at", -1)])
        item["last_issue_at"] = serialize_doc(last)["created_at"] if last else None
    return items


def list_equipment(db: Database, search: str | None = None, equipment_type: str | None = None, status: str | None = None) -> list[dict]:
    query: dict = {}
    if equipment_type:
        query["equipment_type"] = equipment_type
    if status:
        query["status"] = status
    if search:
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{"equipment_id": rx}, {"name": rx}, {"manufacturer": rx}, {"model": rx}, {"location": rx}]
    docs = [serialize_doc(d) for d in db[Collections.EQUIPMENT].find(query, _PROJECTION).sort("equipment_id", 1)]
    return _enrich(db, docs)


def create_equipment(db: Database, data: EquipmentCreate) -> dict:
    now = utcnow()
    doc = data.model_dump()
    doc["installation_date"] = data.installation_date.isoformat() if data.installation_date else None
    doc.update(created_at=now, updated_at=now)
    try:
        db[Collections.EQUIPMENT].insert_one(doc)
    except DuplicateKeyError as exc:
        raise ConflictError(f"Equipment '{data.equipment_id}' already exists") from exc
    return _enrich(db, [get_equipment(db, data.equipment_id)])[0]


def get_equipment_detail(db: Database, equipment_id: str) -> dict:
    return _enrich(db, [get_equipment(db, equipment_id)])[0]


def get_history(db: Database, equipment_id: str) -> dict:
    """Issues, work orders and a merged chronological timeline for one asset."""
    equipment = get_equipment_detail(db, equipment_id)
    issues = [serialize_doc(d) for d in db[Collections.ISSUES].find(
        {"equipment_id": equipment_id},
        {"_id": 0, "issue_id": 1, "description": 1, "status": 1, "priority": 1, "created_at": 1, "updated_at": 1, "status_history": 1},
    ).sort("created_at", -1)]
    work_orders = [serialize_doc(d) for d in db[Collections.WORK_ORDERS].find(
        {"equipment_id": equipment_id},
        {"_id": 0, "work_order_id": 1, "issue_id": 1, "title": 1, "priority": 1, "approval_status": 1,
         "reviewer": 1, "created_at": 1, "reviewed_at": 1, "audit_log": 1},
    ).sort("created_at", -1)]

    timeline = []
    for issue in issues:
        for entry in issue.pop("status_history", []):
            timeline.append({"at": entry["at"], "kind": "issue", "ref": issue["issue_id"],
                             "text": f"Issue {entry['status'].replace('_', ' ')}", "actor": entry.get("actor"), "note": entry.get("note")})
    for wo in work_orders:
        for entry in wo.pop("audit_log", []):
            timeline.append({"at": entry["at"], "kind": "work_order", "ref": wo["work_order_id"],
                             "text": f"Work order {entry['action']}", "actor": entry.get("actor"), "note": entry.get("note")})
    timeline.sort(key=lambda e: e["at"], reverse=True)
    return {"equipment": equipment, "issues": issues, "work_orders": work_orders, "timeline": timeline}

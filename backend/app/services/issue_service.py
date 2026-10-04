import re
from datetime import datetime, time, timezone

from pymongo.database import Database

from app.core.errors import NotFoundError
from app.core.logging import get_logger
from app.models import Collections, IssueStatus, new_id, utcnow
from app.schemas.issue import IssueCreate
from app.services.equipment_service import get_equipment
from app.services.threshold_service import ThresholdService
from app.utils.serialization import serialize_doc

logger = get_logger(__name__)


def _fmt_reading(r: dict) -> str:
    if r.get("value") is None:
        return f"{r['sensor']}: not provided"
    unit = f" {r['unit']}" if r.get("unit") else ""
    return f"{r['sensor']}: {r['value']}{unit}"


def build_observations(data: IssueCreate) -> list[str]:
    """Only facts supplied by the reporter - no inference."""
    obs = [f"Reported symptom: {data.description}"]
    obs += [f"Operating event: {e.description}" for e in data.operating_events]
    obs += [f"Sensor reading - {_fmt_reading(r.model_dump())}" for r in data.sensor_readings]
    return obs


def status_entry(status: str, actor: str, note: str | None = None) -> dict:
    return {"status": status, "at": utcnow(), "actor": actor, "note": note}


def create_issue(db: Database, data: IssueCreate, threshold_service: ThresholdService | None = None) -> dict:
    equipment = get_equipment(db, data.equipment_id)
    threshold_service = threshold_service or ThresholdService()
    now = utcnow()
    evaluation = threshold_service.evaluate(equipment["equipment_type"], data.sensor_readings, reference_time=now)

    doc = {
        "issue_id": new_id("ISS"),
        "equipment_id": equipment["equipment_id"],
        "equipment_name": equipment["name"],
        "equipment_type": equipment["equipment_type"],
        "description": data.description,
        "operating_events": [e.model_dump() for e in data.operating_events],
        "sensor_readings": [r.model_dump() for r in data.sensor_readings],
        "observations": build_observations(data),
        "threshold_findings": [f.model_dump() for f in evaluation.findings],
        "threshold_summary": {"highest_severity": evaluation.highest_severity, "profile": evaluation.profile,
                              "evaluated_at": evaluation.evaluated_at, "disclaimer": evaluation.disclaimer},
        "analysis": None,
        "analysis_history": [],
        "priority": None,
        "status": IssueStatus.REPORTED.value,
        "status_history": [status_entry(IssueStatus.REPORTED.value, data.reported_by or "Demo Technician")],
        "reported_by": data.reported_by or "Demo Technician",
        "last_error": None,
        "created_at": now,
        "updated_at": now,
    }
    db[Collections.ISSUES].insert_one(doc)
    logger.info("Issue created", extra={"issue_id": doc["issue_id"], "equipment_id": doc["equipment_id"],
                                         "threshold_summary": evaluation.highest_severity})
    return get_issue(db, doc["issue_id"])


def get_issue(db: Database, issue_id: str) -> dict:
    doc = db[Collections.ISSUES].find_one({"issue_id": issue_id}, {"_id": 0})
    if not doc:
        raise NotFoundError(f"Issue '{issue_id}' not found")
    issue = serialize_doc(doc)
    wo = db[Collections.WORK_ORDERS].find_one(
        {"issue_id": issue_id}, {"_id": 0, "work_order_id": 1, "approval_status": 1}, sort=[("created_at", -1)])
    issue["current_work_order"] = serialize_doc(wo)
    return issue


def _parse_date(value: str, end: bool) -> datetime:
    d = datetime.fromisoformat(value)
    if d.tzinfo is None and len(value) <= 10:   # plain date -> whole day
        d = datetime.combine(d.date(), time.max if end else time.min)
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def list_issues(db: Database, *, equipment_id=None, priority=None, status=None, date_from=None, date_to=None,
                search=None, limit: int = 100) -> list[dict]:
    query: dict = {}
    if equipment_id:
        query["equipment_id"] = equipment_id
    if priority:
        query["priority"] = priority
    if status:
        query["status"] = status
    if date_from or date_to:
        query["created_at"] = {}
        if date_from:
            query["created_at"]["$gte"] = _parse_date(date_from, end=False)
        if date_to:
            query["created_at"]["$lte"] = _parse_date(date_to, end=True)
    if search:
        rx = {"$regex": re.escape(search.strip()), "$options": "i"}
        query["$or"] = [{"description": rx}, {"issue_id": rx}, {"equipment_name": rx}]
    projection = {"_id": 0, "analysis_history": 0, "observations": 0, "analysis.evidence": 0}
    cursor = db[Collections.ISSUES].find(query, projection).sort("created_at", -1).limit(limit)
    return [serialize_doc(d) for d in cursor]

"""Seed demo data: equipment, fictional manuals and sample issue scenarios.

Usage (from backend/):
    python -m app.seed            # seed only if the database is empty
    python -m app.seed --reset    # drop MaintainIQ collections + vector index, then seed

Sample analyses are produced with the DEMO provider and are labelled as
simulated, regardless of the configured AI_PROVIDER, so seeding never spends
API quota. The one pre-approved work order is attributed to a seed reviewer.
"""

import argparse
from datetime import timedelta
from pathlib import Path

from pymongo.database import Database

from app.core.config import BACKEND_ROOT, get_settings
from app.core.database import get_db_manager
from app.core.logging import configure_logging, get_logger
from app.models import Collections, utcnow
from app.schemas.equipment import EquipmentCreate
from app.schemas.issue import IssueCreate
from app.schemas.work_order import WorkOrderApprove
from app.services import ai_service, equipment_service, issue_service, knowledge_service, triage_service, work_order_service
from app.services.demo_provider import DemoProvider
from app.services.retrieval_service import get_retrieval_service

logger = get_logger("seed")
MANUALS_DIR = BACKEND_ROOT / "data" / "manuals"

EQUIPMENT = [
    dict(equipment_id="PUMP-001", name="Industrial Water Pump", equipment_type="pump", manufacturer="AquaFlow (fictional)",
         model="CP-200", installation_date="2019-04-12", location="Plant A - Pump House 1", status="degraded"),
    dict(equipment_id="HVAC-002", name="Commercial HVAC Unit", equipment_type="hvac", manufacturer="ClimaCore (fictional)",
         model="RT-50", installation_date="2020-08-03", location="Building 2 - Roof", status="operational"),
    dict(equipment_id="MOTOR-003", name="Conveyor Motor", equipment_type="conveyor_motor", manufacturer="DriveMax (fictional)",
         model="CM-75", installation_date="2018-11-20", location="Packaging Line 3", status="operational"),
    dict(equipment_id="PUMP-004", name="Cooling Tower Pump", equipment_type="pump", manufacturer="AquaFlow (fictional)",
         model="CP-200", installation_date="2021-02-15", location="Plant A - Cooling Tower", status="operational"),
    dict(equipment_id="MOTOR-005", name="Sorting Conveyor Motor", equipment_type="conveyor_motor", manufacturer="DriveMax (fictional)",
         model="CM-75", installation_date="2022-06-30", location="Warehouse - Sorter", status="maintenance"),
]

MANUALS = [
    ("aquaflow_cp200_pump_manual.txt", "AquaFlow CP-200 Pump Manual (fictional sample)", "pump"),
    ("climacore_rt50_hvac_manual.txt", "ClimaCore RT-50 HVAC Manual (fictional sample)", "hvac"),
    ("drivemax_cm75_conveyor_motor_manual.txt", "DriveMax CM-75 Conveyor Motor Manual (fictional sample)", "conveyor_motor"),
]


def _scenarios():
    now = utcnow()
    recent = now - timedelta(minutes=10)
    return [
        # 1. Critical threshold
        ("critical", IssueCreate(
            equipment_id="PUMP-001",
            description="Loud grinding noise and strong vibration from the drive-end bearing housing. Housing is too hot to touch.",
            operating_events=[{"description": "Vibration alarm acknowledged by operator at start of shift", "occurred_at": now - timedelta(hours=3)},
                              {"description": "Pump was re-greased two days ago", "occurred_at": now - timedelta(days=2)}],
            sensor_readings=[{"sensor": "temperature", "value": 94, "unit": "C", "recorded_at": recent},
                             {"sensor": "pressure", "value": 6.8, "unit": "bar", "recorded_at": recent},
                             {"sensor": "vibration", "value": 9.2, "unit": "mm/s", "recorded_at": recent},
                             {"sensor": "operating_hours", "value": 3900, "unit": "h", "recorded_at": recent}],
            reported_by="Seed data")),
        # 2. Warning threshold
        ("warning", IssueCreate(
            equipment_id="HVAC-002",
            description="Unit runs continuously but supply air feels warm. Occupants on floor 3 report it is not cooling.",
            operating_events=[{"description": "Filters last replaced 3 months ago"},
                              {"description": "High ambient temperature this week"}],
            sensor_readings=[{"sensor": "temperature", "value": 38, "unit": "C", "recorded_at": recent},
                             {"sensor": "pressure", "value": 23, "unit": "bar", "recorded_at": recent},
                             {"sensor": "vibration", "value": 2.1, "unit": "mm/s", "recorded_at": recent}],
            reported_by="Seed data")),
        # 3. Normal readings
        ("normal", IssueCreate(
            equipment_id="MOTOR-003",
            description="Operator reports an occasional humming noise from the conveyor motor during start-up.",
            operating_events=[{"description": "Noise noticed during morning start-up only"}],
            sensor_readings=[{"sensor": "temperature", "value": 62, "unit": "C", "recorded_at": recent},
                             {"sensor": "vibration", "value": 2.4, "unit": "mm/s", "recorded_at": recent},
                             {"sensor": "operating_hours", "value": 2100, "unit": "h", "recorded_at": recent}],
            reported_by="Seed data")),
        # 4. Missing (and stale) sensor data
        ("missing", IssueCreate(
            equipment_id="PUMP-004",
            description="Crackling noise like gravel inside the pump and discharge flow seems lower than usual.",
            operating_events=[{"description": "Suction tank level was low overnight"}],
            sensor_readings=[{"sensor": "pressure", "value": 5.1, "unit": "bar", "recorded_at": now - timedelta(hours=5)}],
            reported_by="Seed data")),
    ]


def reset(db: Database) -> None:
    for name in (Collections.EQUIPMENT, Collections.ISSUES, Collections.WORK_ORDERS,
                 Collections.KNOWLEDGE_DOCUMENTS, Collections.KNOWLEDGE_TEXTS):
        db.drop_collection(name)
    retrieval = get_retrieval_service()
    collection = retrieval._get_collection()
    ids = collection.get(include=[])["ids"]
    if ids:
        collection.delete(ids=ids)
    from app.core.database import ensure_indexes
    ensure_indexes(db)


def seed(db: Database) -> dict:
    settings = get_settings()
    retrieval = get_retrieval_service()

    for item in EQUIPMENT:
        equipment_service.create_equipment(db, EquipmentCreate(**item))

    for filename, title, etype in MANUALS:
        data = Path(MANUALS_DIR / filename).read_bytes()
        doc = knowledge_service.create_document(db, filename=filename, data=data, title=title, equipment_type=etype,
                                                max_bytes=settings.upload_max_bytes, is_sample=True)
        knowledge_service.ingest_document(db, retrieval, doc["document_id"])

    # Use the demo provider for seed analyses so they are clearly simulated.
    previous = ai_service._provider_override
    ai_service.set_ai_provider(DemoProvider())
    created = {}
    try:
        for label, payload in _scenarios():
            issue = issue_service.create_issue(db, payload)
            created[label] = issue["issue_id"]
            if label in ("critical", "warning", "normal"):
                triage_service.analyze_issue(db, issue["issue_id"], retrieval)
    finally:
        ai_service.set_ai_provider(previous)

    # One historical human decision so dashboards/history show an approved order.
    normal_wo = db[Collections.WORK_ORDERS].find_one({"issue_id": created["normal"]})
    if normal_wo:
        work_order_service.approve_work_order(db, normal_wo["work_order_id"], WorkOrderApprove(
            reviewer="Seed data (demo reviewer)", confirm=True,
            technician_notes="Seeded example of a technician-approved work order."))
    return created


def seed_if_empty(db: Database) -> bool:
    if db[Collections.EQUIPMENT].count_documents({}) > 0:
        return False
    seed(db)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed MaintainIQ demo data")
    parser.add_argument("--reset", action="store_true", help="Delete existing MaintainIQ data first")
    args = parser.parse_args()
    configure_logging("WARNING")

    manager = get_db_manager()
    db = manager.get_db()
    if args.reset:
        reset(db)
    elif db[Collections.EQUIPMENT].count_documents({}) > 0:
        print("Database already contains data. Use --reset to re-seed.")
        return
    created = seed(db)
    print(f"Seeded {len(EQUIPMENT)} equipment, {len(MANUALS)} fictional manuals, scenarios: {created}")
    print(f"Database backend: {manager.backend_label}; embeddings: {get_retrieval_service().embedder.name}")


if __name__ == "__main__":
    main()

from app.core.errors import AIProviderError
from app.models import Collections
from app.services import ai_service
from app.tests.conftest import issue_payload


class FailingProvider:
    name = "gemini"

    def generate(self, context):
        raise AIProviderError("Gemini request failed (ServerError 503).")


def test_health_reports_non_persistent_memory_db(client):
    body = client.get("/api/health").json()
    assert body["database"]["status"] == "ok"
    assert body["database"]["persistent"] is False
    assert body["ai"]["is_simulated"] is True


def test_issue_is_persisted_with_threshold_findings(seeded, db):
    resp = seeded.post("/api/issues", json=issue_payload())
    assert resp.status_code == 201
    issue = resp.json()
    stored = db[Collections.ISSUES].find_one({"issue_id": issue["issue_id"]})
    assert stored is not None and stored["status"] == "reported"
    assert stored["threshold_summary"]["highest_severity"] == "critical"
    assert stored["analysis"] is None   # AI not run automatically
    # pressure & operating hours were not supplied -> explicitly missing
    missing = {f["sensor"] for f in stored["threshold_findings"] if f["status"] == "missing"}
    assert missing == {"pressure", "operating_hours"}
    assert seeded.get(f"/api/issues/{issue['issue_id']}").status_code == 200


def test_issue_validation_errors(seeded):
    resp = seeded.post("/api/issues", json=issue_payload(description="short", operating_events=[]))
    assert resp.status_code == 422
    fields = {d["field"] for d in resp.json()["error"]["details"]}
    assert {"description", "operating_events"} <= fields
    bad_value = issue_payload(sensor_readings=[{"sensor": "temperature", "value": "very hot", "unit": "C"}])
    assert seeded.post("/api/issues", json=bad_value).status_code == 422


def test_issue_for_unknown_equipment_returns_404(seeded):
    assert seeded.post("/api/issues", json=issue_payload(equipment_id="NOPE-999")).status_code == 404


def test_analyze_creates_analysis_and_draft_work_order(seeded):
    issue_id = seeded.post("/api/issues", json=issue_payload()).json()["issue_id"]
    resp = seeded.post(f"/api/issues/{issue_id}/analyze")
    assert resp.status_code == 200, resp.text
    issue = resp.json()
    analysis = issue["analysis"]
    assert issue["status"] == "awaiting_review"
    assert analysis["is_simulated"] is True and analysis["provider"] == "demo"
    assert analysis["output"]["suggested_priority"] in ("high", "critical")   # critical rule floor
    assert issue["current_work_order"]["approval_status"] == "pending_review"

    # Every cited evidence id must exist in the stored evidence catalogue.
    known = {e["evidence_id"] for e in analysis["evidence"]}
    for section in ("possible_causes", "inspection_steps"):
        for item in analysis["output"][section]:
            assert set(item["evidence_ids"]) <= known

    evidence = seeded.get(f"/api/issues/{issue_id}/evidence").json()
    types = {e["evidence_type"] for e in evidence["evidence"]}
    assert {"USER_REPORT", "OPERATING_EVENT", "SENSOR_RULE", "MANUAL"} <= types
    manual = [e for e in evidence["evidence"] if e["evidence_type"] == "MANUAL"]
    assert all(e["chunk_id"] and e["document_id"] == "DOC-TEST" for e in manual)


def test_analysis_with_empty_knowledge_base_states_it(client):
    client.post("/api/equipment", json={"equipment_id": "PUMP-009", "name": "Spare Pump", "equipment_type": "pump",
                                        "manufacturer": "X", "model": "Y"})
    issue_id = client.post("/api/issues", json=issue_payload(equipment_id="PUMP-009")).json()["issue_id"]
    analysis = client.post(f"/api/issues/{issue_id}/analyze").json()["analysis"]
    assert analysis["retrieval"]["status"] == "empty"
    assert not [e for e in analysis["evidence"] if e["evidence_type"] == "MANUAL"]
    assert any("Manual retrieval" in lim for lim in analysis["output"]["limitations"])


def test_ai_failure_preserves_issue_and_allows_retry(seeded, db):
    issue_id = seeded.post("/api/issues", json=issue_payload()).json()["issue_id"]
    ai_service.set_ai_provider(FailingProvider())
    resp = seeded.post(f"/api/issues/{issue_id}/analyze")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "ai_provider_error"

    stored = db[Collections.ISSUES].find_one({"issue_id": issue_id})
    assert stored["status"] == "analysis_failed"
    assert stored["analysis"] is None                      # no fake output substituted
    assert stored["analysis_history"][0]["status"] == "failed"
    assert db[Collections.WORK_ORDERS].count_documents({"issue_id": issue_id}) == 0

    ai_service.set_ai_provider(None)                       # provider recovers -> retry succeeds
    retry = seeded.post(f"/api/issues/{issue_id}/analyze")
    assert retry.status_code == 200
    assert [h["status"] for h in retry.json()["analysis_history"]] == ["failed", "completed"]


def test_issue_history_filters(seeded):
    seeded.post("/api/issues", json=issue_payload())
    issue_id = seeded.post("/api/issues", json=issue_payload()).json()["issue_id"]
    seeded.post(f"/api/issues/{issue_id}/analyze")
    assert len(seeded.get("/api/issues").json()) == 2
    assert [i["issue_id"] for i in seeded.get("/api/issues?status=awaiting_review").json()] == [issue_id]
    assert len(seeded.get("/api/issues?equipment_id=PUMP-001&priority=high").json()) == 1
    assert len(seeded.get("/api/issues?date_from=2000-01-01&date_to=2000-01-02").json()) == 0
    assert seeded.get("/api/issues?priority=urgent").status_code == 422


def test_dashboard_metrics_come_from_data(seeded):
    k0 = seeded.get("/api/dashboard/summary").json()["kpis"]
    assert k0 == {"total_equipment": 1, "open_issues": 0, "high_priority_issues": 0, "pending_work_orders": 0}
    issue_id = seeded.post("/api/issues", json=issue_payload()).json()["issue_id"]
    seeded.post(f"/api/issues/{issue_id}/analyze")
    k1 = seeded.get("/api/dashboard/summary").json()["kpis"]
    assert k1 == {"total_equipment": 1, "open_issues": 1, "high_priority_issues": 1, "pending_work_orders": 1}


def test_database_unavailable_returns_503(client, db_manager):
    db_manager._db = None
    db_manager.connect = lambda: False
    resp = client.get("/api/equipment")
    assert resp.status_code == 503
    assert resp.json()["error"]["code"] == "database_unavailable"


def test_equipment_crud_and_history(seeded):
    assert seeded.post("/api/equipment", json={"equipment_id": "PUMP-001", "name": "dup", "equipment_type": "pump",
                                               "manufacturer": "x", "model": "y"}).status_code == 409
    assert seeded.get("/api/equipment?search=water").json()[0]["equipment_id"] == "PUMP-001"
    assert seeded.get("/api/equipment?equipment_type=hvac").json() == []
    assert seeded.get("/api/equipment/NOPE").status_code == 404
    seeded.post("/api/issues", json=issue_payload())
    history = seeded.get("/api/equipment/PUMP-001/history").json()
    assert len(history["issues"]) == 1 and history["timeline"]


def test_unknown_route_reports_received_path(client):
    """404s use the standard error shape and echo the received path (helps diagnose proxy rewrites)."""
    body = client.get("/nope/here").json()["error"]
    assert body["code"] == "not_found" and body["details"]["path"] == "/nope/here"

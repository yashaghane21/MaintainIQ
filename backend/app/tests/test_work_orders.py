import pytest

from app.models import Collections
from app.tests.conftest import issue_payload


@pytest.fixture
def draft(seeded):
    issue_id = seeded.post("/api/issues", json=issue_payload()).json()["issue_id"]
    issue = seeded.post(f"/api/issues/{issue_id}/analyze").json()
    return seeded, issue_id, issue["current_work_order"]["work_order_id"]


def test_edit_work_order_records_audit_and_keeps_original(draft):
    client, issue_id, wo_id = draft
    original = client.get(f"/api/work-orders/{wo_id}").json()
    resp = client.patch(f"/api/work-orders/{wo_id}", json={
        "title": "Replace drive-end bearing on PUMP-001", "priority": "critical",
        "checklist": [{"text": "LOTO", "done": False}, {"text": "Replace bearing", "done": False}],
        "technician_notes": "Bearing noise confirmed on site.", "editor": "Alex Tech"})
    assert resp.status_code == 200
    wo = resp.json()
    assert wo["title"] == "Replace drive-end bearing on PUMP-001" and wo["priority"] == "critical"
    assert wo["original_draft"]["title"] == original["original_draft"]["title"] != wo["title"]
    edit = wo["audit_log"][-1]
    assert edit["action"] == "edited" and edit["actor"] == "Alex Tech" and "title" in edit["changes"]
    assert client.get(f"/api/issues/{issue_id}").json()["priority"] == "critical"


def test_approval_requires_explicit_confirmation(draft):
    client, _, wo_id = draft
    assert client.post(f"/api/work-orders/{wo_id}/approve", json={"reviewer": "Alex", "confirm": False}).status_code == 422
    assert client.post(f"/api/work-orders/{wo_id}/approve", json={"reviewer": "Alex"}).status_code == 422
    assert client.get(f"/api/work-orders/{wo_id}").json()["approval_status"] == "pending_review"


def test_approve_work_order(draft, db):
    client, issue_id, wo_id = draft
    client.patch(f"/api/work-orders/{wo_id}", json={"title": "Edited title for approval", "editor": "Alex"})
    resp = client.post(f"/api/work-orders/{wo_id}/approve",
                       json={"reviewer": "Alex Tech", "confirm": True, "technician_notes": "Parts in stock."})
    assert resp.status_code == 200
    wo = resp.json()
    assert wo["approval_status"] == "approved" and wo["reviewer"] == "Alex Tech" and wo["reviewed_at"]
    assert wo["approved_version"]["title"] == "Edited title for approval"
    assert wo["approved_version"]["technician_notes"] == "Parts in stock."
    assert wo["original_draft"]["title"] != wo["approved_version"]["title"]
    assert [a["action"] for a in wo["audit_log"]] == ["created", "edited", "approved"]
    issue = db[Collections.ISSUES].find_one({"issue_id": issue_id})
    assert issue["status"] == "work_order_approved"     # still linked to the original issue
    assert wo["issue_id"] == issue_id


def test_reject_work_order_requires_reason(draft):
    client, issue_id, wo_id = draft
    assert client.post(f"/api/work-orders/{wo_id}/reject", json={"reviewer": "Alex", "confirm": True}).status_code == 422
    resp = client.post(f"/api/work-orders/{wo_id}/reject",
                       json={"reviewer": "Alex", "confirm": True, "reason": "Root cause is electrical, not mechanical."})
    assert resp.status_code == 200
    wo = resp.json()
    assert wo["approval_status"] == "rejected" and wo["decision_reason"].startswith("Root cause")
    assert client.get(f"/api/issues/{issue_id}").json()["status"] == "work_order_rejected"


@pytest.mark.parametrize("first,second", [("approve", "reject"), ("reject", "approve"), ("approve", "approve")])
def test_terminal_states_cannot_transition(draft, first, second):
    client, _, wo_id = draft
    body = {"reviewer": "Alex", "confirm": True, "reason": "Not needed at this time."}
    assert client.post(f"/api/work-orders/{wo_id}/{first}", json=body).status_code == 200
    resp = client.post(f"/api/work-orders/{wo_id}/{second}", json=body)
    assert resp.status_code == 409 and resp.json()["error"]["code"] == "conflict"
    # The first decision is preserved
    assert client.get(f"/api/work-orders/{wo_id}").json()["approval_status"] == ("approved" if first == "approve" else "rejected")


def test_cannot_edit_after_decision(draft):
    client, _, wo_id = draft
    client.post(f"/api/work-orders/{wo_id}/approve", json={"reviewer": "Alex", "confirm": True})
    assert client.patch(f"/api/work-orders/{wo_id}", json={"title": "Sneaky late edit"}).status_code == 409


def test_reanalysis_supersedes_pending_draft(draft):
    client, issue_id, wo_id = draft
    issue = client.post(f"/api/issues/{issue_id}/analyze").json()
    assert issue["superseded_work_orders"] == [wo_id]
    assert client.get(f"/api/work-orders/{wo_id}").json()["approval_status"] == "superseded"
    assert issue["current_work_order"]["work_order_id"] != wo_id
    assert issue["analysis"]["version"] == 2


def test_reanalysis_after_rejection_creates_new_draft(draft):
    client, issue_id, wo_id = draft
    client.post(f"/api/work-orders/{wo_id}/reject", json={"reviewer": "Alex", "confirm": True, "reason": "Wrong scope entirely."})
    issue = client.post(f"/api/issues/{issue_id}/analyze").json()
    assert issue["current_work_order"]["approval_status"] == "pending_review"
    assert client.get(f"/api/work-orders/{wo_id}").json()["approval_status"] == "rejected"   # decision kept


def test_reanalysis_blocked_after_approval(draft):
    client, issue_id, wo_id = draft
    client.post(f"/api/work-orders/{wo_id}/approve", json={"reviewer": "Alex", "confirm": True})
    assert client.post(f"/api/issues/{issue_id}/analyze").status_code == 409


def test_unknown_work_order_404(seeded):
    assert seeded.get("/api/work-orders/WO-NOPE").status_code == 404

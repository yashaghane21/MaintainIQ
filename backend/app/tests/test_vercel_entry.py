"""The Vercel entry point must route requests by their ORIGINAL path.

vercel.json rewrites `/<path>?<query>` to `/api/index?__path=/<path>&<query>`.
"""

from fastapi.testclient import TestClient


def test_rewritten_requests_reach_the_original_route(client):
    from api.index import app

    vercel = TestClient(app)
    health = vercel.get("/api/index", params={"__path": "/api/health"})
    assert health.status_code == 200 and health.json()["database"]["status"] == "ok"

    # Original query parameters survive; the helper parameter is removed.
    filtered = vercel.get("/api/index?__path=/api/equipment&equipment_type=hvac")
    assert filtered.status_code == 200 and filtered.json() == []


def test_requests_without_helper_param_pass_through(client):
    from api.index import app

    assert TestClient(app).get("/api/health").status_code == 200

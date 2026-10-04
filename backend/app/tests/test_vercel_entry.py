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


def test_runtime_root_path_does_not_break_routing(client):
    """Some ASGI hosts set root_path to the function path; the wrapper must neutralise it."""
    import asyncio

    from api.index import app

    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "GET", "scheme": "https",
             "path": "/api/index", "raw_path": b"/api/index", "root_path": "/api/index",
             "query_string": b"__path=/api/health", "headers": [(b"host", b"example.vercel.app")],
             "client": ("1.2.3.4", 1), "server": ("example.vercel.app", 443)}
    asyncio.run(app(scope, receive, send))
    assert sent[0]["status"] == 200


def test_unknown_route_reports_received_path(client):
    body = client.get("/nope/here").json()["error"]
    assert body["code"] == "not_found" and body["details"]["path"] == "/nope/here"

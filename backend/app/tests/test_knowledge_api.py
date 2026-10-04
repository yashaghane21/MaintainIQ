def test_upload_txt_ingests_and_is_searchable(client):
    resp = client.post("/api/knowledge/upload", data={"equipment_type": "hvac", "title": "HVAC Notes"},
                       files={"file": ("notes.txt", b"Clean the condenser coil when head pressure is high.", "text/plain")})
    assert resp.status_code == 202
    doc_id = resp.json()["document_id"]
    # TestClient runs background tasks before returning, so ingestion is finished.
    doc = client.get(f"/api/knowledge/{doc_id}").json()
    assert doc["ingestion_status"] == "completed" and doc["chunk_count"] == 1
    chunks = client.get(f"/api/knowledge/{doc_id}/chunks").json()
    assert chunks[0]["text"].startswith("Clean the condenser")
    found = client.post("/api/knowledge/search", json={"query": "condenser coil head pressure", "equipment_type": "hvac"}).json()
    assert found["status"] == "ok" and found["chunks"][0]["document_id"] == doc_id


def test_upload_rejects_bad_files(client):
    bad_type = client.post("/api/knowledge/upload", data={"equipment_type": "hvac"},
                           files={"file": ("x.docx", b"data", "application/octet-stream")})
    assert bad_type.status_code == 400 and bad_type.json()["error"]["code"] == "upload_error"
    empty = client.post("/api/knowledge/upload", data={"equipment_type": "hvac"}, files={"file": ("x.txt", b"", "text/plain")})
    assert empty.status_code == 400
    bad_equipment = client.post("/api/knowledge/upload", data={"equipment_type": "rocket"},
                                files={"file": ("x.txt", b"some text", "text/plain")})
    assert bad_equipment.status_code == 400
    assert client.get("/api/knowledge").json() == []


def test_search_on_empty_kb(client):
    body = client.post("/api/knowledge/search", json={"query": "anything at all"}).json()
    assert body["status"] == "empty" and body["chunks"] == []


def test_memory_store_rebuilds_from_mongodb_on_cold_start(client, db, retrieval):
    """Simulates a serverless cold start: a fresh in-memory store is rebuilt from stored text."""
    from app.core.config import get_settings
    from app.services.knowledge_service import ensure_index_loaded
    from app.services.retrieval_service import HashingEmbedder, RetrievalService, set_retrieval_service

    doc_id = client.post("/api/knowledge/upload", data={"equipment_type": "pump"},
                         files={"file": ("m.txt", b"Cavitation sounds like gravel; clean the suction strainer.", "text/plain")}).json()["document_id"]

    cold = RetrievalService(get_settings().model_copy(update={"vector_store": "memory", "retrieval_min_score": 0.05}),
                            embedder=HashingEmbedder())
    assert cold.warmed is False and cold.status()["indexed_chunks"] == 0
    set_retrieval_service(cold)
    found = client.post("/api/knowledge/search", json={"query": "gravel noise suction strainer", "equipment_type": "pump"}).json()
    assert found["status"] == "ok" and found["chunks"][0]["document_id"] == doc_id
    assert cold.warmed is True
    before = cold.status()["indexed_chunks"]
    ensure_index_loaded(db, cold)              # idempotent: second call is a no-op
    assert cold.status()["indexed_chunks"] == before


def test_serverless_upload_ingests_within_request(client, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.get_settings(), "serverless", True)
    resp = client.post("/api/knowledge/upload", data={"equipment_type": "hvac"},
                       files={"file": ("n.txt", b"Replace the fan belt when it squeals.", "text/plain")})
    assert resp.status_code == 202
    assert resp.json()["ingestion_status"] == "completed"   # already indexed when the response is returned

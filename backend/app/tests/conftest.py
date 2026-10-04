"""Test fixtures: in-memory MongoDB (mongomock), hashing embeddings, ephemeral Chroma.

External services (MongoDB, Gemini, HuggingFace) are never contacted by tests.
"""

import os

os.environ.update({
    "APP_ENV": "test",
    "DB_BACKEND": "memory",
    "AI_PROVIDER": "demo",
    "EMBEDDING_PROVIDER": "hashing",
    "CHROMA_MODE": "ephemeral",
    "GEMINI_API_KEY": "",
    "LOG_LEVEL": "WARNING",
})

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.database import DatabaseManager, set_db_manager
from app.services import ai_service
from app.services.retrieval_service import HashingEmbedder, RetrievalService, set_retrieval_service
from app.utils.text import Page


@pytest.fixture
def db_manager():
    manager = DatabaseManager(get_settings().model_copy(update={"mongodb_db": f"test_{uuid.uuid4().hex[:8]}"}))
    manager.connect()
    set_db_manager(manager)
    yield manager
    set_db_manager(None)


@pytest.fixture
def db(db_manager):
    return db_manager.get_db()


@pytest.fixture
def retrieval():
    # Unique collection per test so the shared in-process Chroma system stays isolated.
    settings = get_settings().model_copy(update={"chroma_collection": f"t_{uuid.uuid4().hex[:12]}", "retrieval_min_score": 0.05})
    service = RetrievalService(settings, embedder=HashingEmbedder())
    set_retrieval_service(service)
    yield service
    set_retrieval_service(None)


@pytest.fixture(autouse=True)
def reset_provider():
    ai_service.set_ai_provider(None)
    yield
    ai_service.set_ai_provider(None)


@pytest.fixture
def client(db_manager, retrieval):
    from app.main import app

    with TestClient(app) as c:
        yield c


PUMP = {"equipment_id": "PUMP-001", "name": "Industrial Water Pump", "equipment_type": "pump",
        "manufacturer": "AquaFlow (fictional)", "model": "CP-200", "installation_date": "2019-04-12", "status": "operational"}

PUMP_MANUAL = (
    "Section 1. Safety\nApply lockout/tagout to the pump motor before inspection.\n\n"
    "Section 3. Vibration\nRising vibration with grinding noise from the bearing housing indicates bearing wear "
    "or lubrication breakdown. Check grease condition and bearing temperature."
)


@pytest.fixture
def seeded(client, retrieval):
    """Pump equipment + one indexed fictional manual."""
    assert client.post("/api/equipment", json=PUMP).status_code == 201
    retrieval.ingest(document_id="DOC-TEST", title="Test Pump Manual (fictional)", equipment_type="pump",
                     source="test_manual.txt", pages=[Page(None, PUMP_MANUAL)])
    return client


def issue_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "equipment_id": "PUMP-001",
        "description": "Grinding noise and strong vibration from the bearing housing.",
        "operating_events": [{"description": "Vibration alarm at shift start", "occurred_at": (now - timedelta(hours=1)).isoformat()}],
        "sensor_readings": [
            {"sensor": "temperature", "value": 95, "unit": "C", "recorded_at": now.isoformat()},
            {"sensor": "vibration", "value": 9.0, "unit": "mm/s", "recorded_at": now.isoformat()},
        ],
    }
    payload.update(overrides)
    return payload

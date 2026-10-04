"""Knowledge base documents: upload, ingestion status, listing and re-indexing."""

from pymongo.database import Database

from app.core.errors import NotFoundError, UploadError
from app.core.logging import get_logger
from app.models import Collections, IngestionStatus, new_id, utcnow
from app.services.retrieval_service import RetrievalService
from app.utils.serialization import serialize_doc
from app.utils.text import Page, extract_pages

logger = get_logger(__name__)
ALLOWED_EQUIPMENT_TYPES = {"pump", "hvac", "conveyor_motor", "general"}


def create_document(db: Database, *, filename: str, data: bytes, title: str | None, equipment_type: str,
                    max_bytes: int, is_sample: bool = False) -> dict:
    """Validate + extract text synchronously, persist record as `pending`. Embedding happens in `ingest_document`."""
    if equipment_type not in ALLOWED_EQUIPMENT_TYPES:
        raise UploadError(f"equipment_type must be one of {sorted(ALLOWED_EQUIPMENT_TYPES)}")
    if not data:
        raise UploadError("Uploaded file is empty.")
    if len(data) > max_bytes:
        raise UploadError(f"File exceeds the {max_bytes // (1024 * 1024)} MB limit.")
    try:
        pages = extract_pages(filename, data)
    except ValueError as exc:
        raise UploadError(str(exc)) from exc

    now = utcnow()
    doc = {
        "document_id": new_id("DOC"),
        "title": (title or filename.rsplit(".", 1)[0]).strip()[:200],
        "equipment_type": equipment_type,
        "source": filename,
        "document_type": "pdf" if filename.lower().endswith(".pdf") else "txt",
        "page_count": len(pages),
        "character_count": sum(len(p.text) for p in pages),
        "is_sample": is_sample,
        "ingestion_status": IngestionStatus.PENDING.value,
        "chunk_count": 0,
        "error": None,
        "created_at": now,
        "updated_at": now,
    }
    db[Collections.KNOWLEDGE_DOCUMENTS].insert_one(doc)
    db[Collections.KNOWLEDGE_TEXTS].insert_one(
        {"document_id": doc["document_id"], "pages": [{"page_number": p.page_number, "text": p.text} for p in pages]})
    return get_document(db, doc["document_id"])


def ingest_document(db: Database, retrieval: RetrievalService, document_id: str) -> None:
    """Chunk + embed + index. Records status transitions; never raises (runs as a background task)."""
    docs = db[Collections.KNOWLEDGE_DOCUMENTS]
    meta = docs.find_one({"document_id": document_id})
    text = db[Collections.KNOWLEDGE_TEXTS].find_one({"document_id": document_id})
    if not meta or not text:
        return
    docs.update_one({"document_id": document_id}, {"$set": {"ingestion_status": IngestionStatus.PROCESSING.value, "updated_at": utcnow()}})
    try:
        count = retrieval.ingest(
            document_id=document_id, title=meta["title"], equipment_type=meta["equipment_type"], source=meta["source"],
            pages=[Page(p["page_number"], p["text"]) for p in text["pages"]],
        )
        docs.update_one({"document_id": document_id}, {"$set": {
            "ingestion_status": IngestionStatus.COMPLETED.value, "chunk_count": count, "error": None, "updated_at": utcnow()}})
    except Exception as exc:  # noqa: BLE001 - status must reflect any failure
        logger.exception("Ingestion failed", extra={"document_id": document_id})
        docs.update_one({"document_id": document_id}, {"$set": {
            "ingestion_status": IngestionStatus.FAILED.value, "error": f"{type(exc).__name__}: {exc}"[:500], "updated_at": utcnow()}})


def get_document(db: Database, document_id: str) -> dict:
    doc = db[Collections.KNOWLEDGE_DOCUMENTS].find_one({"document_id": document_id}, {"_id": 0})
    if not doc:
        raise NotFoundError(f"Document '{document_id}' not found")
    return serialize_doc(doc)


def list_documents(db: Database, equipment_type: str | None = None) -> list[dict]:
    query = {"equipment_type": equipment_type} if equipment_type else {}
    return [serialize_doc(d) for d in db[Collections.KNOWLEDGE_DOCUMENTS].find(query, {"_id": 0}).sort("created_at", -1)]


def delete_document(db: Database, retrieval: RetrievalService, document_id: str) -> None:
    get_document(db, document_id)
    retrieval.delete_document(document_id)
    db[Collections.KNOWLEDGE_DOCUMENTS].delete_one({"document_id": document_id})
    db[Collections.KNOWLEDGE_TEXTS].delete_one({"document_id": document_id})


def reindex_missing(db: Database, retrieval: RetrievalService) -> int:
    """Re-embed documents whose vectors are missing (e.g. after a redeploy on an ephemeral disk)."""
    rebuilt = 0
    for meta in db[Collections.KNOWLEDGE_DOCUMENTS].find({"ingestion_status": {"$in": ["completed", "pending", "processing"]}}):
        if meta["ingestion_status"] == "completed" and retrieval.chunk_count(meta["document_id"]) > 0:
            continue
        ingest_document(db, retrieval, meta["document_id"])
        rebuilt += 1
    if rebuilt:
        logger.info("Re-indexed documents", extra={"event": f"reindexed {rebuilt}"})
    return rebuilt

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile, status
from pymongo.database import Database

from app.core.config import get_settings
from app.core.database import get_database
from app.schemas.knowledge import RetrievalQuery
from app.services import knowledge_service
from app.services.retrieval_service import get_retrieval_service

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    equipment_type: str = Form(...),
    title: str | None = Form(default=None),
    db: Database = Depends(get_database),
):
    """Extracts text immediately; chunking + embedding run in the background (poll the list for status)."""
    settings = get_settings()
    data = await file.read(settings.upload_max_bytes + 1)
    doc = knowledge_service.create_document(
        db, filename=file.filename or "upload.txt", data=data, title=title,
        equipment_type=equipment_type, max_bytes=settings.upload_max_bytes,
    )
    if settings.serverless:
        # No reliable post-response work on serverless: index within the request.
        knowledge_service.ingest_document(db, get_retrieval_service(), doc["document_id"])
        return knowledge_service.get_document(db, doc["document_id"])
    background.add_task(knowledge_service.ingest_document, db, get_retrieval_service(), doc["document_id"])
    return doc


@router.get("")
def list_documents(equipment_type: str | None = None, db: Database = Depends(get_database)):
    return knowledge_service.list_documents(db, equipment_type)


@router.post("/search")
def search(payload: RetrievalQuery, db: Database = Depends(get_database)):
    """Semantic retrieval endpoint. Scores are text similarity, not diagnostic probability."""
    retrieval = get_retrieval_service()
    knowledge_service.ensure_index_loaded(db, retrieval)
    result = retrieval.retrieve(payload.query, payload.equipment_type, payload.top_k)
    return {"status": result.status, "message": result.message, "chunks": [c.__dict__ for c in result.chunks]}


@router.get("/{document_id}")
def get_document(document_id: str, db: Database = Depends(get_database)):
    return knowledge_service.get_document(db, document_id)


@router.get("/{document_id}/chunks")
def get_chunks(document_id: str, db: Database = Depends(get_database)):
    knowledge_service.get_document(db, document_id)
    retrieval = get_retrieval_service()
    knowledge_service.ensure_index_loaded(db, retrieval)
    return retrieval.get_document_chunks(document_id)


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex(document_id: str, background: BackgroundTasks, db: Database = Depends(get_database)):
    doc = knowledge_service.get_document(db, document_id)
    if get_settings().serverless:
        knowledge_service.ingest_document(db, get_retrieval_service(), document_id)
        return knowledge_service.get_document(db, document_id)
    background.add_task(knowledge_service.ingest_document, db, get_retrieval_service(), document_id)
    return doc


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: str, db: Database = Depends(get_database)):
    knowledge_service.delete_document(db, get_retrieval_service(), document_id)

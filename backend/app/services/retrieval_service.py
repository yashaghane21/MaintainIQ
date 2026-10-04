"""Semantic retrieval over maintenance documents (Sentence Transformers + ChromaDB).

Pipeline: extracted pages -> chunks -> embeddings -> Chroma upsert.
Query:    text -> embedding -> Chroma cosine search filtered by equipment type.

Retrieval scores are cosine similarities of text, not probabilities of a
diagnosis, and are labelled that way everywhere they are shown.
"""

import hashlib
import math
import re
import threading
from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.utils.text import Page, chunk_pages

logger = get_logger(__name__)


# ---------------------------------------------------------------- embedders
class SentenceTransformerEmbedder:
    """Real semantic embeddings. The model is loaded lazily on first use."""

    def __init__(self, model_name: str):
        self.model_name = model_name
        self.name = f"sentence-transformers:{model_name}"
        self.default_min_score = 0.25
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                from sentence_transformers import SentenceTransformer

                logger.info("Loading embedding model", extra={"event": "embedding_model_load"})
                self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32)
        return [v.tolist() for v in vectors]


class HashingEmbedder:
    """Lexical feature-hashing embeddings (no ML model).

    Used for automated tests and memory-constrained hosts. It matches shared
    words, not meaning, and is reported as such by /api/health.
    """

    name = "hashing (lexical fallback, non-semantic)"
    default_min_score = 0.10

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            vec = [0.0] * self.dim
            for token in re.findall(r"[a-z0-9]{3,}", text.lower()):
                h = int(hashlib.md5(token.encode()).hexdigest(), 16)
                vec[h % self.dim] += 1.0 if (h >> 8) & 1 else -1.0
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


def _installed(module: str) -> bool:
    import importlib.util

    return importlib.util.find_spec(module) is not None


def build_embedder(settings: Settings):
    provider = settings.embedding_provider
    if provider == "auto":
        provider = "sentence-transformers" if _installed("sentence_transformers") else "hashing"
    if provider == "hashing":
        return HashingEmbedder()
    return SentenceTransformerEmbedder(settings.embedding_model)


# ---------------------------------------------------------------- results
@dataclass
class RetrievedChunk:
    chunk_id: str
    document_id: str
    document_title: str
    equipment_type: str
    source: str
    page_number: int | None
    text: str
    score: float


@dataclass
class RetrievalResult:
    status: str                     # ok | empty | error
    chunks: list[RetrievedChunk] = field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------- service
class RetrievalService:
    def __init__(self, settings: Settings | None = None, embedder=None, chroma_client=None):
        self.settings = settings or get_settings()
        self.embedder = embedder or build_embedder(self.settings)
        self._client = chroma_client
        self._collection = None
        self._lock = threading.Lock()
        store = self.settings.vector_store
        if store == "auto":
            store = "chroma" if (chroma_client is not None or _installed("chromadb")) else "memory"
        self.store_kind = store
        # True once the in-process index has been (re)built for this process.
        self.warmed = store == "chroma"

    # -- storage -------------------------------------------------------------
    def _get_collection(self):
        if self._collection is not None:
            return self._collection
        with self._lock:
            if self._collection is None and self.store_kind == "memory":
                from app.services.vector_store import InMemoryCollection

                self._collection = InMemoryCollection()
            if self._collection is None:
                import chromadb

                if self._client is None:
                    if self.settings.chroma_mode == "ephemeral":
                        self._client = chromadb.EphemeralClient()
                    else:
                        self._client = chromadb.PersistentClient(path=self.settings.chroma_persist_dir)
                self._collection = self._client.get_or_create_collection(
                    name=self.settings.chroma_collection, metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    def status(self) -> dict:
        try:
            count = self._get_collection().count()
            return {"status": "ok", "embedder": self.embedder.name, "vector_store": self.store_label, "indexed_chunks": count}
        except Exception as exc:  # noqa: BLE001 - surfaced in health check
            return {"status": "error", "embedder": self.embedder.name, "vector_store": self.store_label, "error": type(exc).__name__}

    @property
    def store_label(self) -> str:
        return "chromadb" if self.store_kind == "chroma" else "in-memory (rebuilt from MongoDB per instance)"

    def chunk_count(self, document_id: str) -> int:
        result = self._get_collection().get(where={"document_id": document_id}, include=[])
        return len(result["ids"])

    def get_document_chunks(self, document_id: str) -> list[dict]:
        result = self._get_collection().get(where={"document_id": document_id}, include=["documents", "metadatas"])
        rows = [
            {"chunk_id": cid, "text": doc, "page_number": meta.get("page_number"), "chunk_index": meta.get("chunk_index")}
            for cid, doc, meta in zip(result["ids"], result["documents"], result["metadatas"])
        ]
        return sorted(rows, key=lambda r: r["chunk_index"] or 0)

    def delete_document(self, document_id: str) -> None:
        self._get_collection().delete(where={"document_id": document_id})

    # -- ingestion -----------------------------------------------------------
    def ingest(self, *, document_id: str, title: str, equipment_type: str, source: str, pages: list[Page]) -> int:
        chunks = chunk_pages(pages, self.settings.chunk_size, self.settings.chunk_overlap)
        if not chunks:
            raise ValueError("Document produced no text chunks")
        ids, metadatas, texts = [], [], []
        for chunk in chunks:
            page_part = f"p{chunk.page_number}" if chunk.page_number else "p0"
            ids.append(f"{document_id}:{page_part}:c{chunk.chunk_index}")
            meta = {
                "document_id": document_id, "document_title": title, "equipment_type": equipment_type,
                "source": source, "chunk_index": chunk.chunk_index,
            }
            if chunk.page_number is not None:   # Chroma metadata values cannot be None
                meta["page_number"] = chunk.page_number
            metadatas.append(meta)
            texts.append(chunk.text)
        embeddings = self.embedder.embed(texts)
        collection = self._get_collection()
        collection.delete(where={"document_id": document_id})   # idempotent re-ingest
        collection.upsert(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
        logger.info("Document indexed", extra={"document_id": document_id, "event": f"indexed {len(ids)} chunks"})
        return len(ids)

    # -- retrieval -----------------------------------------------------------
    def retrieve(self, query: str, equipment_type: str | None = None, top_k: int | None = None) -> RetrievalResult:
        top_k = top_k or self.settings.retrieval_top_k
        try:
            collection = self._get_collection()
            if collection.count() == 0:
                return RetrievalResult("empty", message="The knowledge base contains no indexed documents.")
            where = {"equipment_type": {"$in": [equipment_type, "general"]}} if equipment_type else None
            embedding = self.embedder.embed([query])[0]
            res = collection.query(query_embeddings=[embedding], n_results=top_k, where=where,
                                   include=["documents", "metadatas", "distances"])
        except Exception as exc:  # noqa: BLE001 - retrieval failure must not break triage
            logger.exception("Retrieval failed", extra={"retrieval_status": "error"})
            return RetrievalResult("error", message=f"Retrieval failed: {type(exc).__name__}")

        min_score = self.settings.retrieval_min_score
        if min_score is None:
            min_score = self.embedder.default_min_score
        chunks = []
        for cid, doc, meta, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0]):
            score = round(1.0 - float(dist), 4)   # cosine distance -> similarity
            if score < min_score:
                continue
            chunks.append(RetrievedChunk(
                chunk_id=cid, document_id=meta["document_id"], document_title=meta["document_title"],
                equipment_type=meta["equipment_type"], source=meta.get("source", ""),
                page_number=meta.get("page_number"), text=doc, score=score,
            ))
        if not chunks:
            return RetrievalResult("empty", message="No sufficiently relevant manual content was found for this issue.")
        return RetrievalResult("ok", chunks)


_retrieval_service: RetrievalService | None = None


def get_retrieval_service() -> RetrievalService:
    global _retrieval_service
    if _retrieval_service is None:
        _retrieval_service = RetrievalService()
    return _retrieval_service


def set_retrieval_service(service: RetrievalService | None) -> None:
    global _retrieval_service
    _retrieval_service = service

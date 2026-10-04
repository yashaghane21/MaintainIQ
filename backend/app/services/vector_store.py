"""Dependency-free in-memory vector store for serverless hosts.

Implements the small subset of the ChromaDB collection API that
`RetrievalService` uses (count/get/delete/upsert/query), so the service code
is identical for both stores. Embeddings are L2-normalised, so cosine
similarity is a dot product; cosine *distance* (1 - similarity) is returned to
match Chroma's `hnsw:space=cosine` semantics.

Data lives in process memory only. On serverless platforms each cold start
begins empty and the index is rebuilt from document text stored in MongoDB
(see `knowledge_service.ensure_index_loaded`). This brute-force search is
intended for small corpora (hundreds to a few thousand chunks).
"""

import threading


def _matches(meta: dict, where: dict | None) -> bool:
    if not where:
        return True
    for key, cond in where.items():
        value = meta.get(key)
        if isinstance(cond, dict):
            if "$in" in cond and value not in cond["$in"]:
                return False
            if "$eq" in cond and value != cond["$eq"]:
                return False
        elif value != cond:
            return False
    return True


class InMemoryCollection:
    def __init__(self):
        self._rows: dict[str, tuple[list[float], str, dict]] = {}
        self._lock = threading.Lock()

    def count(self) -> int:
        return len(self._rows)

    def get(self, where: dict | None = None, ids: list[str] | None = None, include: list[str] | None = None) -> dict:
        with self._lock:
            items = [(i, r) for i, r in self._rows.items() if (ids is None or i in ids) and _matches(r[2], where)]
        return {"ids": [i for i, _ in items], "documents": [r[1] for _, r in items], "metadatas": [r[2] for _, r in items]}

    def delete(self, where: dict | None = None, ids: list[str] | None = None) -> None:
        with self._lock:
            for i in [i for i, r in self._rows.items() if (ids is None or i in ids) and (where is None or _matches(r[2], where))]:
                del self._rows[i]

    def upsert(self, ids: list[str], embeddings: list[list[float]], documents: list[str], metadatas: list[dict]) -> None:
        with self._lock:
            for i, e, d, m in zip(ids, embeddings, documents, metadatas):
                self._rows[i] = (list(e), d, dict(m))

    def query(self, query_embeddings: list[list[float]], n_results: int, where: dict | None = None, include=None) -> dict:
        q = query_embeddings[0]
        with self._lock:
            scored = [
                (1.0 - sum(a * b for a, b in zip(q, emb)), i, doc, meta)
                for i, (emb, doc, meta) in self._rows.items() if _matches(meta, where)
            ]
        scored.sort(key=lambda s: s[0])
        top = scored[:n_results]
        return {
            "ids": [[t[1] for t in top]],
            "documents": [[t[2] for t in top]],
            "metadatas": [[t[3] for t in top]],
            "distances": [[t[0] for t in top]],
        }

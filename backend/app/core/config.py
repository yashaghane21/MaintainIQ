"""Application configuration loaded from environment variables (and an optional .env file)."""

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "MaintainIQ API"
    app_env: Literal["development", "production", "test"] = "development"
    log_level: str = "INFO"

    # --- Database -----------------------------------------------------------
    # "mongo"  -> real MongoDB (local or Atlas) via MONGODB_URI.
    # "memory" -> in-process mongomock. NOT persistent; intended for tests and
    #             throwaway demos only. /api/health reports this explicitly.
    db_backend: Literal["mongo", "memory"] = "mongo"
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "maintainiq"
    mongodb_timeout_ms: int = 3000

    # --- CORS -----------------------------------------------------------------
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- AI provider -----------------------------------------------------------
    # "gemini" -> live Google Gemini (requires GEMINI_API_KEY)
    # "demo"   -> deterministic, clearly-labelled SIMULATED analysis
    ai_provider: Literal["gemini", "demo"] = "demo"
    gemini_api_key: str | None = Field(default=None, repr=False)
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: int = 60
    gemini_temperature: float = 0.2

    # --- Retrieval / RAG -------------------------------------------------------
    # "auto" -> sentence-transformers if installed, otherwise hashing (reported by /api/health)
    # "sentence-transformers" -> real semantic embeddings
    # "hashing" -> lightweight lexical hashing embeddings for tests / low-memory / serverless hosts
    embedding_provider: Literal["auto", "sentence-transformers", "hashing"] = "auto"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # "auto" -> ChromaDB if installed, otherwise the in-memory store (rebuilt from MongoDB on cold start)
    vector_store: Literal["auto", "chroma", "memory"] = "auto"
    chroma_mode: Literal["persistent", "ephemeral"] = "persistent"
    chroma_persist_dir: str = str(BACKEND_ROOT / "data" / "chroma")
    chroma_collection: str = "maintenance_manuals"
    retrieval_top_k: int = 4
    # Minimum cosine similarity for a chunk to count as evidence. Unset -> embedder default
    # (0.25 for sentence-transformers, 0.10 for lexical hashing, whose scores run lower).
    retrieval_min_score: float | None = None
    chunk_size: int = 900
    chunk_overlap: int = 150
    upload_max_bytes: int = 10 * 1024 * 1024

    # --- Threshold engine ------------------------------------------------------
    threshold_profiles_path: str = str(BACKEND_ROOT / "data" / "threshold_profiles.json")
    stale_reading_minutes: int = 120
    conflict_tolerance_ratio: float = 0.10

    # --- Misc -------------------------------------------------------------------
    # Serverless (e.g. Vercel, which sets VERCEL=1): no background threads/tasks, so
    # document ingestion runs inside the upload request and startup tasks are skipped.
    serverless: bool = Field(default_factory=lambda: bool(os.environ.get("VERCEL")))
    seed_on_startup: bool = False
    reindex_on_startup: bool = True

    @field_validator("gemini_api_key")
    @classmethod
    def _blank_key_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None

    @property
    def cors_origin_list(self) -> list[str]:
        # Browsers send origins without a trailing slash; tolerate "https://x.app/" in config.
        return [o.strip().rstrip("/") for o in self.cors_origins.split(",") if o.strip().rstrip("/")]


@lru_cache
def get_settings() -> Settings:
    return Settings()

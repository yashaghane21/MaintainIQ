"""Application configuration loaded from environment variables (and an optional .env file)."""

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
    # "sentence-transformers" -> real semantic embeddings (default)
    # "hashing" -> lightweight lexical hashing embeddings for tests / low-memory hosts
    embedding_provider: Literal["sentence-transformers", "hashing"] = "sentence-transformers"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chroma_mode: Literal["persistent", "ephemeral"] = "persistent"
    chroma_persist_dir: str = str(BACKEND_ROOT / "data" / "chroma")
    chroma_collection: str = "maintenance_manuals"
    retrieval_top_k: int = 4
    retrieval_min_score: float = 0.25
    chunk_size: int = 900
    chunk_overlap: int = 150
    upload_max_bytes: int = 10 * 1024 * 1024

    # --- Threshold engine ------------------------------------------------------
    threshold_profiles_path: str = str(BACKEND_ROOT / "data" / "threshold_profiles.json")
    stale_reading_minutes: int = 120
    conflict_tolerance_ratio: float = 0.10

    # --- Misc -------------------------------------------------------------------
    seed_on_startup: bool = False
    reindex_on_startup: bool = True

    @field_validator("gemini_api_key")
    @classmethod
    def _blank_key_is_none(cls, v: str | None) -> str | None:
        return v.strip() or None if v else None

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()

from fastapi import APIRouter, Depends
from pymongo.database import Database

from app.core.config import get_settings
from app.core.database import get_database, get_db_manager
from app.services import dashboard_service
from app.services.retrieval_service import get_retrieval_service
from app.services.threshold_service import load_profiles

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health():
    """Reports real component status. Never exposes secrets."""
    settings = get_settings()
    manager = get_db_manager()
    db_ok = manager.ping() or manager.connect()
    ai = {"provider": settings.ai_provider, "model": settings.gemini_model if settings.ai_provider == "gemini" else "deterministic-demo-v1",
          "is_simulated": settings.ai_provider == "demo",
          "configured": settings.ai_provider == "demo" or bool(settings.gemini_api_key)}
    return {
        "status": "ok" if db_ok else "degraded",
        "environment": settings.app_env,
        "database": {"status": "ok" if db_ok else "unavailable", "backend": manager.backend_label,
                     "persistent": settings.db_backend == "mongo", "error": None if db_ok else manager.last_error},
        "ai": ai,
        "retrieval": get_retrieval_service().status(),
    }


@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard_summary(db: Database = Depends(get_database)):
    return dashboard_service.get_summary(db)


@router.get("/thresholds", tags=["system"])
def thresholds():
    """The configured (fictional, demonstration-only) threshold profiles."""
    return load_profiles()

import threading
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import equipment, health, issues, knowledge, work_orders
from app.core.config import get_settings
from app.core.database import get_db_manager
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger, request_id_ctx

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger("app")


def _background_startup():
    """Seeding / re-indexing can take a while (model download), so it must not block the health check."""
    from app.services.knowledge_service import ensure_index_loaded, reindex_missing
    from app.services.retrieval_service import get_retrieval_service

    manager = get_db_manager()
    try:
        db = manager.get_db()
        if settings.seed_on_startup:
            from app.seed import seed_if_empty
            seed_if_empty(db)
        if settings.reindex_on_startup:
            retrieval = get_retrieval_service()
            if retrieval.store_kind == "chroma":
                reindex_missing(db, retrieval)
            else:
                ensure_index_loaded(db, retrieval)
    except Exception:  # noqa: BLE001 - logged; the API stays up and reports status via /api/health
        logger.exception("Background startup task failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting MaintainIQ API", extra={"event": "startup", "ai_provider": settings.ai_provider})
    get_db_manager().connect()
    # Serverless platforms freeze the process between requests, so no background thread there;
    # the database connects lazily and the vector index loads on first retrieval.
    if settings.app_env != "test" and not settings.serverless:
        threading.Thread(target=_background_startup, daemon=True).start()
    yield
    get_db_manager().close()


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="AI-assisted equipment maintenance triage. AI output is advisory; technicians approve all work orders.",
    lifespan=lifespan,
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:16]
    token = request_id_ctx.set(rid)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-ID"] = rid
    logger.info("request", extra={"method": request.method, "endpoint": request.url.path,
                                  "status_code": response.status_code, "duration_ms": duration})
    request_id_ctx.reset(token)
    return response


register_exception_handlers(app)
for module in (health, equipment, issues, work_orders, knowledge):
    app.include_router(module.router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "docs": "/docs", "health": "/api/health"}

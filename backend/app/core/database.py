"""MongoDB connection management.

The app never pretends to persist data: if MongoDB is unreachable, every
database-backed request fails with HTTP 503 and /api/health reports it.
"""

import threading

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database
from pymongo.errors import PyMongoError

from app.core.config import Settings, get_settings
from app.core.errors import DatabaseUnavailableError
from app.core.logging import get_logger
from app.models import Collections

logger = get_logger(__name__)


class DatabaseManager:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = None
        self._db: Database | None = None
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def backend_label(self) -> str:
        return "mongomock (in-memory, NOT persistent)" if self.settings.db_backend == "memory" else "mongodb"

    def connect(self) -> bool:
        with self._lock:
            try:
                if self.settings.db_backend == "memory":
                    import mongomock

                    client = mongomock.MongoClient()
                else:
                    client = MongoClient(
                        self.settings.mongodb_uri,
                        serverSelectionTimeoutMS=self.settings.mongodb_timeout_ms,
                        connectTimeoutMS=self.settings.mongodb_timeout_ms,
                        tz_aware=True,
                    )
                    client.admin.command("ping")
                self._client = client
                self._db = client[self.settings.mongodb_db]
                ensure_indexes(self._db)
                self.last_error = None
                logger.info("Database connected", extra={"event": "db_connected"})
                return True
            except PyMongoError as exc:
                self._client = None
                self._db = None
                # str(exc) for connection errors does not include credentials.
                self.last_error = type(exc).__name__
                logger.error("Database connection failed", extra={"event": "db_connect_failed"}, exc_info=False)
                return False

    def ping(self) -> bool:
        if self._db is None:
            return False
        if self.settings.db_backend == "memory":
            return True
        try:
            self._client.admin.command("ping")
            return True
        except PyMongoError as exc:
            self.last_error = type(exc).__name__
            return False

    def get_db(self) -> Database:
        if self._db is None and not self.connect():
            raise DatabaseUnavailableError(
                "Database is unavailable. The request was not saved.",
                details={"reason": self.last_error},
            )
        return self._db

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._client = None
        self._db = None


def ensure_indexes(db: Database) -> None:
    db[Collections.EQUIPMENT].create_index("equipment_id", unique=True)
    db[Collections.EQUIPMENT].create_index("equipment_type")
    db[Collections.ISSUES].create_index("issue_id", unique=True)
    db[Collections.ISSUES].create_index([("equipment_id", ASCENDING), ("created_at", DESCENDING)])
    db[Collections.ISSUES].create_index("status")
    db[Collections.ISSUES].create_index("priority")
    db[Collections.WORK_ORDERS].create_index("work_order_id", unique=True)
    db[Collections.WORK_ORDERS].create_index("issue_id")
    db[Collections.WORK_ORDERS].create_index("approval_status")
    db[Collections.KNOWLEDGE_DOCUMENTS].create_index("document_id", unique=True)
    db[Collections.KNOWLEDGE_TEXTS].create_index("document_id", unique=True)


_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    global _manager
    if _manager is None:
        _manager = DatabaseManager(get_settings())
    return _manager


def set_db_manager(manager: DatabaseManager | None) -> None:
    """Used by tests to inject an isolated database."""
    global _manager
    _manager = manager


def get_database() -> Database:
    """FastAPI dependency."""
    return get_db_manager().get_db()

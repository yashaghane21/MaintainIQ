"""Helpers to turn MongoDB documents into JSON-safe dicts."""

from datetime import datetime, timezone
from typing import Any

from bson import ObjectId


def _ensure_utc(value: datetime) -> datetime:
    # mongomock and some drivers return naive datetimes that are actually UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def serialize(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return _ensure_utc(value)
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [serialize(v) for v in value]
    return value


def serialize_doc(doc: dict | None) -> dict | None:
    """Convert a Mongo document: `_id` (ObjectId) becomes the string field `id`."""
    if doc is None:
        return None
    out = serialize(doc)
    if "_id" in out:
        out["id"] = out.pop("_id")
    return out

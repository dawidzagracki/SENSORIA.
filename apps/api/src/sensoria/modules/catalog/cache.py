"""Short process-local cache for complete public catalog list responses."""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from sensoria.config import get_settings

_entries: dict[tuple[object, ...], tuple[float, Any]] = {}
_MAX_ENTRIES = 2048
_CATALOG_TABLES = {
    "products",
    "product_images",
    "product_voucher",
    "product_voucher_variants",
    "product_book",
    "product_audiobook",
    "product_audiobook_chapters",
    "product_digital",
    "categories",
    "audience_tags",
    "product_categories",
    "product_audience_tags",
}


def _now() -> float:
    """Return monotonic time through a seam that is deterministic in TTL tests."""

    return time.monotonic()


def get_cached(key: tuple[object, ...]) -> Any | None:
    """Return an unexpired response for a normalized request key."""

    cached = _entries.get(key)
    if cached is None:
        return None
    expires_at, response = cached
    if expires_at <= _now():
        _entries.pop(key, None)
        return None
    return response


def set_cached(key: tuple[object, ...], response: Any) -> None:
    """Store a complete response using configured short TTL; zero disables cache."""

    ttl = get_settings().CATALOG_CACHE_TTL_SECONDS
    if ttl == 0:
        return
    now = _now()
    if key not in _entries and len(_entries) >= _MAX_ENTRIES:
        expired_keys = [
            entry_key for entry_key, (expires_at, _) in _entries.items() if expires_at <= now
        ]
        for expired_key in expired_keys:
            _entries.pop(expired_key, None)
        if len(_entries) >= _MAX_ENTRIES:
            _entries.pop(next(iter(_entries)))
    _entries[key] = (now + ttl, response)


def clear_cache() -> None:
    """Clear all list variants, used on committed ORM writes and in tests."""

    _entries.clear()


@event.listens_for(Session, "before_flush")
def _mark_catalog_changes(session: Session, _flush_context: object, _instances: object) -> None:
    """Mark ORM writes to catalog data for invalidation after transaction commit."""

    objects = (*session.new, *session.dirty, *session.deleted)
    if any(
        getattr(getattr(type(item), "__table__", None), "name", None) in _CATALOG_TABLES
        for item in objects
    ):
        session.info["sensoria_catalog_cache_dirty"] = True


@event.listens_for(Session, "after_commit")
def _invalidate_after_commit(session: Session) -> None:
    """Invalidate only after commit; rollback leaves cached responses untouched."""

    if session.info.pop("sensoria_catalog_cache_dirty", False):
        clear_cache()


@event.listens_for(Session, "after_rollback")
def _forget_rolled_back_changes(session: Session) -> None:
    """Forget pending invalidation when the transaction rolls back."""

    session.info.pop("sensoria_catalog_cache_dirty", None)


@event.listens_for(Session, "after_bulk_update")
@event.listens_for(Session, "after_bulk_delete")
def _mark_legacy_bulk_write(execute_state: object) -> None:
    """Legacy ORM bulk writes do not pass through ``before_flush``."""

    session = getattr(execute_state, "session", None)
    if isinstance(session, Session):
        session.info["sensoria_catalog_cache_dirty"] = True


@event.listens_for(Session, "do_orm_execute")
def _invalidate_after_statement_bulk_write(execute_state: object) -> None:
    """Invalidate on ORM UPDATE/DELETE statements, including association changes."""

    if getattr(execute_state, "is_update", False) or getattr(execute_state, "is_delete", False):
        session = getattr(execute_state, "session", None)
        if isinstance(session, Session):
            session.info["sensoria_catalog_cache_dirty"] = True

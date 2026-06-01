# -*- coding: utf-8 -*-
"""Read-only class-aware learning resources loading."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import urlparse

from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.config import logger

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def get_learning_resources(
    db=None,
    class_context=None,
    *,
    section: str | None = None,
    subject_id: str | None = None,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, Any]]:
    """Load active learning resources for the class active term."""
    if not db or not class_context or getattr(class_context, "is_legacy_fallback", False):
        return []

    normalized_limit = _normalize_limit(limit)
    if normalized_limit <= 0:
        return []

    try:
        term_id = _get_active_term_id(db, class_context)
        if not term_id:
            return []

        docs = (
            db.collection("classes")
            .document(class_context.class_id)
            .collection("terms")
            .document(term_id)
            .collection("resources")
            .stream()
        )
        resources = [
            resource
            for doc in docs
            for resource in [_normalize_resource(doc.to_dict() or {}, term_id)]
            if resource
        ]
    except Exception as e:
        logger.warning("Could not load learning resources: %s", e)
        return []

    if section:
        resources = [resource for resource in resources if resource.get("section") == section]
    if subject_id:
        resources = [resource for resource in resources if resource.get("subject_id") == subject_id]

    resources.sort(key=lambda resource: (resource["sort_order"], resource["title"]))
    return resources[:normalized_limit]


def _get_active_term_id(db, class_context) -> str | None:
    registry = get_class_registry_entry(db, class_context.class_id)
    return registry.active_term_id if registry and registry.active_term_id else None


def _normalize_resource(data: Mapping[str, Any], term_id: str) -> dict[str, Any] | None:
    if not isinstance(data, Mapping):
        return None
    if data.get("status") != "active":
        return None

    title = _clean_str(data.get("title"))
    url = _clean_str(data.get("url"))
    if not title or not url or not _is_valid_resource_url(url):
        return None

    return {
        "section": _clean_str(data.get("section")),
        "type": _clean_str(data.get("type")),
        "subject_id": _clean_str(data.get("subject_id")),
        "subject_label": _clean_str(data.get("subject_label")),
        "grade_level": _clean_str(data.get("grade_level")),
        "term_label": _clean_str(data.get("term_label")),
        "book_label": _clean_str(data.get("book_label")),
        "title": title,
        "url": url,
        "sort_order": _normalize_sort_order(data.get("sort_order")),
        "notes": _clean_str(data.get("notes")),
        "term_id": _clean_str(data.get("term_id")) or term_id,
    }


def _is_valid_resource_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clean_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    return text or None


def _normalize_sort_order(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    return 0


def _normalize_limit(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return DEFAULT_LIMIT
    return min(value, MAX_LIMIT)

# -*- coding: utf-8 -*-
"""Class-aware links config loading."""

from __future__ import annotations

from typing import Any, Mapping

from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.config import (
    ABSENCE_LINK,
    GRADE_LINK,
    SCHOOL_LINK,
    WORKSHEET_LINK,
    logger,
)

WORKSHEET_URL = "worksheet_url"
SCHOOL_URL = "school_url"
GRADE_URL = "grade_url"
ABSENCE_FORM_URL = "absence_form_url"

LINK_KEYS = (
    WORKSHEET_URL,
    SCHOOL_URL,
    GRADE_URL,
    ABSENCE_FORM_URL,
)

SAFE_FALLBACK_KEYS = (
    SCHOOL_URL,
    GRADE_URL,
    ABSENCE_FORM_URL,
)


def get_legacy_links() -> dict[str, str]:
    """Return current hardcoded MTC12 general links used for legacy behavior."""
    return {
        SCHOOL_URL: SCHOOL_LINK,
        GRADE_URL: GRADE_LINK,
        ABSENCE_FORM_URL: ABSENCE_LINK,
        WORKSHEET_URL: WORKSHEET_LINK,
    }


def get_safe_fallback_links(include_worksheet: bool) -> dict[str, str]:
    """Return fallback links that are safe for the current class context."""
    fallback = {key: get_legacy_links()[key] for key in SAFE_FALLBACK_KEYS}
    if include_worksheet:
        fallback[WORKSHEET_URL] = WORKSHEET_LINK
    return fallback


def get_links_config(db=None, class_context=None) -> dict[str, str]:
    """Load class links from Firestore and merge valid values over fallback."""
    is_legacy = not class_context or getattr(class_context, "is_legacy_fallback", False)
    links = get_safe_fallback_links(include_worksheet=is_legacy)
    if not db or not class_context or getattr(class_context, "is_legacy_fallback", False):
        return links

    try:
        registry = get_class_registry_entry(db, class_context.class_id)
        term_id = registry.active_term_id if registry else None
        if not term_id:
            return links

        doc = (
            db.collection("classes")
            .document(class_context.class_id)
            .collection("terms")
            .document(term_id)
            .collection("config")
            .document("links")
            .get()
        )
        if not getattr(doc, "exists", False):
            return links

        return merge_link_values(links, doc.to_dict() or {})
    except Exception as e:
        logger.warning("Could not load links config: %s", e)
        return links


def merge_link_values(fallback: Mapping[str, str], overrides: Mapping[str, Any]) -> dict[str, str]:
    """Merge non-empty string override values into known link keys only."""
    merged = dict(fallback)
    if not isinstance(overrides, Mapping):
        return merged

    for key in LINK_KEYS:
        value = overrides.get(key)
        if isinstance(value, str) and value.strip():
            merged[key] = value.strip()
    return merged

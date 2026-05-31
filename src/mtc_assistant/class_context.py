# -*- coding: utf-8 -*-
"""Class context resolution for LINE users."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from mtc_assistant.config import ADMIN_USER_IDS, logger
from mtc_assistant.firestore_paths import DEFAULT_CLASS_ID
from mtc_assistant.invite_codes import is_valid_class_id


@dataclass(frozen=True)
class ClassContext:
    class_id: str
    user_id: str
    role: str = "student"
    feature_flags: Mapping[str, bool] | None = None
    is_legacy_fallback: bool = False


@dataclass(frozen=True)
class ClassRegistryEntry:
    class_id: str
    display_name: str
    status: str
    active_term_id: str | None
    grade_level: str | None
    room_label: str | None


@dataclass(frozen=True)
class ActiveTermMetadata:
    class_id: str
    term_id: str
    display_name: str | None = None
    status: str | None = None


def get_class_registry_entry(db, class_id: str) -> ClassRegistryEntry | None:
    """Read /system/class_registry/{classId} without changing runtime behavior."""
    if not db or not is_valid_class_id(class_id):
        return None

    try:
        doc = db.collection("system").document("class_registry").collection(class_id).document("main").get()
    except Exception as e:
        logger.error("Could not read class registry for %s: %s", class_id, e)
        return None

    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    return parse_class_registry_entry(class_id, data)


def get_active_term_metadata(db, class_id: str) -> ActiveTermMetadata | None:
    """Read active term metadata using the class registry active_term_id."""
    registry = get_class_registry_entry(db, class_id)
    if not registry or not registry.active_term_id:
        return None

    try:
        doc = (
            db.collection("classes")
            .document(class_id)
            .collection("terms")
            .document(registry.active_term_id)
            .collection("metadata")
            .document("main")
            .get()
        )
    except Exception as e:
        logger.error("Could not read active term metadata for %s: %s", class_id, e)
        return None

    if not getattr(doc, "exists", False):
        return None

    data = doc.to_dict() or {}
    return ActiveTermMetadata(
        class_id=class_id,
        term_id=registry.active_term_id,
        display_name=_optional_str(data.get("display_name")),
        status=_optional_str(data.get("status")),
    )


def parse_class_registry_entry(class_id: str, data: Mapping[str, Any]) -> ClassRegistryEntry | None:
    if not is_valid_class_id(class_id):
        return None

    display_name = _required_str(data.get("display_name"))
    status = _required_str(data.get("status"))
    if not display_name or not status:
        return None

    active_term_id = _optional_str(data.get("active_term_id"))
    if active_term_id and not _is_valid_term_id(active_term_id):
        return None

    return ClassRegistryEntry(
        class_id=class_id,
        display_name=display_name,
        status=status,
        active_term_id=active_term_id,
        grade_level=_optional_str(data.get("grade_level")),
        room_label=_optional_str(data.get("room_label")),
    )


def resolve_line_class_context(db, user_id: str) -> ClassContext | None:
    """
    Resolve a LINE user's active class.

    During migration, an existing root /users/{userId} document without
    active_class_id is treated as MTC12. A missing user returns None so the
    handler can prompt for an invite code.
    """
    if not user_id:
        return None

    role = "super_admin" if user_id in ADMIN_USER_IDS else "student"

    if not db:
        return ClassContext(DEFAULT_CLASS_ID, user_id, role, {}, is_legacy_fallback=True)

    try:
        user_doc = db.collection("users").document(user_id).get()
    except Exception as e:
        logger.error("Could not resolve class context for %s: %s", user_id, e)
        return ClassContext(DEFAULT_CLASS_ID, user_id, role, {}, is_legacy_fallback=True)

    if not getattr(user_doc, "exists", False):
        return None

    data = user_doc.to_dict() or {}
    active_class_id = str(data.get("active_class_id") or "").strip()
    if active_class_id:
        if not is_valid_class_id(active_class_id):
            logger.warning("Ignoring invalid active_class_id for %s", user_id)
            return None
        return ClassContext(active_class_id, user_id, str(data.get("role") or role), {})

    return ClassContext(DEFAULT_CLASS_ID, user_id, role, {}, is_legacy_fallback=True)


def onboarding_prompt() -> str:
    return (
        "ยังไม่ได้เข้าห้องในระบบ MTC Assistant\n\n"
        "พิมพ์ JOIN <code> หรือ เข้าห้อง <code> เพื่อเข้าห้องของตัวเอง\n"
        "ถ้าไม่มีโค้ด ให้ติดต่อแอดมินห้อง"
    )


def _required_str(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _optional_str(value) -> str | None:
    text = str(value or "").strip()
    return text or None


def _is_valid_term_id(term_id: str) -> bool:
    return bool(term_id) and all(ch.isalnum() or ch in "-_" for ch in term_id) and len(term_id) <= 40

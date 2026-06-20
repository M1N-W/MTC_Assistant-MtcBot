# -*- coding: utf-8 -*-
"""Student-facing account DTO assembly."""

from __future__ import annotations

from mtc_assistant.account_flex import build_account_flex
from mtc_assistant.class_context import get_active_term_metadata, get_class_registry_entry
from mtc_assistant.line_profile_service import _is_https_url, sync_line_profile_if_stale
from mtc_assistant.teacher_identity import teacher_assignment_labels


ROLE_LABELS = {"student": "นักเรียน", "teacher": "คุณครู MTC", "class_admin": "ผู้ดูแลห้อง", "super_admin": "ผู้ดูแลระบบ"}


def build_account_message(db, user_id: str, line_api=None):
    if line_api:
        sync_line_profile_if_stale(db, user_id, line_api)
    account = build_account_dto(db, user_id)
    return build_account_flex(account)


def build_account_dto(db, user_id: str) -> dict:
    user = _read_doc(db, f"users/{user_id}") if db else {}
    active_class_id = str(user.get("active_class_id") or "").strip()
    registry = get_class_registry_entry(db, active_class_id) if active_class_id else None
    term = get_active_term_metadata(db, active_class_id) if active_class_id else None
    class_user = _read_doc(db, f"classes/{active_class_id}/users/{user_id}") if active_class_id else {}
    verification_status = class_user.get("verification_status") or user.get("identity_status") or "unverified"
    identity_type = user.get("identity_type") or ("student" if verification_status == "verified" and class_user.get("role") == "student" else "general_user")
    class_ids = _as_string_list(user.get("class_ids"))
    assignment_labels = teacher_assignment_labels(_as_string_list(class_user.get("assignment_roles")))
    return {
        "identity_type": identity_type,
        "line_display_name": user.get("line_display_name") or class_user.get("line_display_name") or "LINE User",
        "line_picture_url": _safe_picture_url(user.get("line_picture_url")),
        "verification_status": verification_status,
        "full_name": class_user.get("full_name") or class_user.get("display_name"),
        "class_number": class_user.get("class_number"),
        "class_display": registry.display_name if registry else None,
        "grade_level": registry.grade_level if registry else None,
        "room_label": registry.room_label if registry else None,
        "active_class_label": registry.display_name if registry else None,
        "term_label": term.display_name if term and term.display_name else None,
        "role_label": ROLE_LABELS.get(str(class_user.get("role") or "student"), "นักเรียน"),
        "assignment_labels": assignment_labels,
        "can_switch_class": len(class_ids) > 1,
    }


def _read_doc(db, path: str) -> dict:
    parts = path.split("/")
    ref = db.collection(parts[0]).document(parts[1])
    index = 2
    while index < len(parts):
        ref = ref.collection(parts[index]).document(parts[index + 1])
        index += 2
    snapshot = ref.get()
    return snapshot.to_dict() if getattr(snapshot, "exists", False) else {}


def _as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _safe_picture_url(value) -> str | None:
    text = str(value or "").strip()
    return text if _is_https_url(text) else None

# -*- coding: utf-8 -*-
"""Safe active-class selection for existing LINE memberships."""

from __future__ import annotations

from dataclasses import dataclass

from linebot.v3.messaging import TextMessage

from firebase_admin import firestore

from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.identity_verification import ACTIVE_CLASS_MATRIX, normalize_identity_text
from mtc_assistant.invite_codes import is_valid_class_id


@dataclass(frozen=True)
class ClassSelectionResult:
    success: bool
    message: TextMessage
    class_id: str | None = None


def select_active_class(db, user_id: str, requested_class: str | None = None) -> ClassSelectionResult:
    if not db:
        return _result(False, "ระบบเลือกห้องยังไม่พร้อม ลองใหม่อีกครั้งภายหลัง")
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    if not getattr(user_doc, "exists", False):
        return _result(False, "ยังไม่พบห้องที่ใช้งานได้ พิมพ์ JOIN <code> หรือ ยืนยันตัวตน ก่อน")
    user = user_doc.to_dict() or {}
    authorized = [class_id for class_id in _as_string_list(user.get("class_ids")) if _is_active_membership(db, class_id, user_id)]
    if not authorized:
        return _result(False, "ยังไม่มีห้องที่เลือกได้ กรุณาเข้าห้องหรือยืนยันตัวตนก่อน")
    if requested_class:
        class_id = _class_id_from_display_token(requested_class)
        if class_id not in authorized:
            return _result(False, "เลือกได้เฉพาะห้องที่บัญชีนี้มีสิทธิ์ใช้งานอยู่")
        _set_active_class(db, user_ref, class_id)
        registry = get_class_registry_entry(db, class_id)
        label = registry.display_name if registry else class_id.upper()
        return _result(True, f"เปลี่ยนห้องที่ใช้งานเป็น {label} แล้ว", class_id)
    if len(authorized) == 1:
        registry = get_class_registry_entry(db, authorized[0])
        label = registry.display_name if registry else authorized[0].upper()
        _set_active_class(db, user_ref, authorized[0])
        return _result(True, f"ตอนนี้ใช้งาน {label} อยู่แล้ว", authorized[0])
    labels = []
    for class_id in authorized:
        registry = get_class_registry_entry(db, class_id)
        labels.append(registry.display_name if registry else class_id.upper())
    return _result(True, "เลือกห้องได้โดยพิมพ์ เลือกห้อง " + " หรือ ".join(labels))


def _is_active_membership(db, class_id: str, user_id: str) -> bool:
    if not is_valid_class_id(class_id):
        return False
    registry = get_class_registry_entry(db, class_id)
    if not registry or registry.status != "active":
        return False
    snapshot = db.collection("classes").document(class_id).collection("users").document(user_id).get()
    if not getattr(snapshot, "exists", False):
        return False
    data = snapshot.to_dict() or {}
    return data.get("status", "active") == "active"


def _class_id_from_display_token(value: str) -> str:
    token = normalize_identity_text(value).lower().replace(" ", "")
    if token in ACTIVE_CLASS_MATRIX:
        return token
    if token.startswith("mtc") and token[3:].isdigit():
        return token
    if token.isdigit():
        return f"mtc{token}"
    return token


def _as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _set_active_class(db, user_ref, class_id: str) -> None:
    if db and hasattr(db, "transaction") and not hasattr(db, "store"):
        transaction = db.transaction()

        @firestore.transactional
        def update_in_transaction(transaction):
            transaction.set(user_ref, {"active_class_id": class_id}, merge=True)

        update_in_transaction(transaction)
        return
    user_ref.set({"active_class_id": class_id}, merge=True)


def _result(success: bool, text: str, class_id: str | None = None) -> ClassSelectionResult:
    return ClassSelectionResult(success, TextMessage(text=text), class_id)

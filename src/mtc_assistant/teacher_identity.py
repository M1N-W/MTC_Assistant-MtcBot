# -*- coding: utf-8 -*-
"""MTC teacher directory verification and class assignment binding."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any

from firebase_admin import firestore

from mtc_assistant.config import LOCAL_TZ, logger
from mtc_assistant.dashboard_auth_models import verify_password
from mtc_assistant.identity_verification import normalize_identity_text
from mtc_assistant.invite_codes import is_valid_class_id


TEACHER_DIRECTORY_ROOT = "system/teacher_directory/records"
TEACHER_VERIFICATION_ROOT = "system/teacher_verification/records"
TEACHER_ASSIGNMENT_ROLES = frozenset({"mtc_math_adviser", "homeroom_teacher"})
TEACHER_ROLE_LABELS = {
    "mtc_math_adviser": "ครูคณิตศาสตร์ที่ปรึกษา MTC",
    "homeroom_teacher": "ครูประจำชั้น",
}
MAX_TEACHER_FAILED_ATTEMPTS = 5


@dataclass(frozen=True)
class TeacherLookup:
    teacher_id: str
    data: dict[str, Any]


@dataclass(frozen=True)
class TeacherVerificationResult:
    success: bool
    message: str


def find_teacher_by_display_name(db, display_name: str) -> TeacherLookup | None:
    normalized = normalize_identity_text(display_name)
    if not db or not normalized:
        return None
    for snapshot in _teacher_collection(db).stream():
        if not getattr(snapshot, "exists", False):
            continue
        data = snapshot.to_dict() or {}
        if data.get("status", "active") != "active":
            continue
        candidate = normalize_identity_text(data.get("normalized_full_name") or data.get("display_name"))
        if candidate == normalized:
            teacher_id = str(data.get("teacher_id") or getattr(snapshot, "id", "")).strip()
            if teacher_id:
                return TeacherLookup(teacher_id, data)
    return None


def verify_teacher_code_and_bind(db, user_id: str, teacher_id: str, code: str, *, now_provider=None) -> TeacherVerificationResult:
    if not db:
        return TeacherVerificationResult(False, "ระบบยืนยันคุณครูยังไม่พร้อม")
    now_provider = now_provider or (lambda: datetime.datetime.now(tz=LOCAL_TZ))
    try:
        if _supports_firestore_transaction(db):
            transaction = db.transaction()

            @firestore.transactional
            def bind_in_transaction(transaction):
                return _verify_teacher_code_and_bind_once(db, user_id, teacher_id, code, now_provider, transaction)

            return bind_in_transaction(transaction)
        return _verify_teacher_code_and_bind_once(db, user_id, teacher_id, code, now_provider, None)
    except Exception as exc:
        logger.exception("Teacher identity binding failed: %s", exc)
        return TeacherVerificationResult(False, "ยืนยันตัวตนคุณครูไม่สำเร็จ กรุณาติดต่อแอดมิน")


def teacher_assignment_labels(assignment_roles: list[str]) -> list[str]:
    ordered = []
    for role in ("homeroom_teacher", "mtc_math_adviser"):
        if role in assignment_roles and role in TEACHER_ROLE_LABELS:
            ordered.append(TEACHER_ROLE_LABELS[role])
    return ordered


def _verify_teacher_code_and_bind_once(db, user_id: str, teacher_id: str, code: str, now_provider, transaction) -> TeacherVerificationResult:
    teacher_ref = _doc_ref(db, f"{TEACHER_DIRECTORY_ROOT}/{teacher_id}")
    verification_ref = _doc_ref(db, f"{TEACHER_VERIFICATION_ROOT}/{teacher_id}")
    teacher_doc = _txn_get(teacher_ref, transaction)
    verification_doc = _txn_get(verification_ref, transaction)
    if not getattr(teacher_doc, "exists", False) or not getattr(verification_doc, "exists", False):
        return TeacherVerificationResult(False, "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ")
    teacher = teacher_doc.to_dict() or {}
    verification = verification_doc.to_dict() or {}
    if teacher.get("status", "active") != "active" or verification.get("status", "active") != "active":
        return TeacherVerificationResult(False, "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ")
    if str(teacher.get("bound_user_id") or "") not in ("", user_id):
        return TeacherVerificationResult(False, "บัญชีคุณครูนี้ถูกผูกกับ LINE อื่นแล้ว กรุณาติดต่อแอดมิน")
    if verification.get("used_at") and str(teacher.get("bound_user_id") or "") != user_id:
        return TeacherVerificationResult(False, "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ")
    if _is_expired(verification.get("expires_at"), now_provider()):
        return TeacherVerificationResult(False, "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ")
    password_hash = str(verification.get("verification_code_hash") or "")
    if not verify_password(password_hash, str(code or "")):
        attempts = int(verification.get("failed_attempts", 0) or 0) + 1
        payload = {"failed_attempts": attempts, "updated_at": now_provider().isoformat()}

        raw_max = verification.get("max_attempts")
        try:
            max_attempts = int(raw_max) if raw_max is not None else MAX_TEACHER_FAILED_ATTEMPTS
        except (ValueError, TypeError):
            max_attempts = MAX_TEACHER_FAILED_ATTEMPTS

        effective_max = min(max(max_attempts, 1), 10)
        if attempts >= effective_max:
            payload["status"] = "disabled"

        _txn_set(verification_ref, payload, merge=True, transaction=transaction)
        return TeacherVerificationResult(False, "รหัสยืนยันไม่ถูกต้องหรือหมดอายุ")

    assignments = _valid_assignments(teacher.get("assignments"))
    class_ids = [assignment["class_id"] for assignment in assignments]
    now = now_provider().isoformat()
    _txn_set(teacher_ref, {
        "bound_user_id": user_id,
        "bound_at": now,
        "verification_status": "verified",
        "updated_at": now,
    }, merge=True, transaction=transaction)
    _txn_set(verification_ref, {
        "used_at": now,
        "status": "used",
        "updated_at": now,
    }, merge=True, transaction=transaction)
    _txn_set(_doc_ref(db, f"users/{user_id}"), {
        "user_id": user_id,
        "identity_type": "mtc_teacher",
        "verification_status": "verified",
        "identity_status": "verified",
        "teacher_id": teacher_id,
        "class_ids": class_ids,
        "active_class_id": class_ids[0] if len(class_ids) == 1 else "",
        "last_seen_at": now,
    }, merge=True, transaction=transaction)
    for assignment in assignments:
        _txn_set(_doc_ref(db, f"classes/{assignment['class_id']}/users/{user_id}"), {
            "user_id": user_id,
            "display_name": teacher.get("display_name"),
            "role": "teacher",
            "status": "active",
            "assignment_roles": assignment["assignment_roles"],
            "verification_status": "verified",
            "verified_at": now,
            "last_seen_at": now,
        }, merge=True, transaction=transaction)
    return TeacherVerificationResult(True, "ยืนยันตัวตนคุณครูสำเร็จ")


def _valid_assignments(value) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    assignments = []
    for item in value:
        if not isinstance(item, dict):
            continue
        class_id = str(item.get("class_id") or "").strip()
        roles = [str(role) for role in item.get("assignment_roles") or [] if str(role) in TEACHER_ASSIGNMENT_ROLES]
        if is_valid_class_id(class_id):
            assignments.append({"class_id": class_id, "assignment_roles": roles})
    return assignments


def _teacher_collection(db):
    return db.collection("system").document("teacher_directory").collection("records")


def _doc_ref(db, path: str):
    parts = path.split("/")
    ref = db.collection(parts[0]).document(parts[1])
    index = 2
    while index < len(parts):
        ref = ref.collection(parts[index]).document(parts[index + 1])
        index += 2
    return ref


def _supports_firestore_transaction(db) -> bool:
    return bool(db and hasattr(db, "transaction") and not hasattr(db, "store"))


def _txn_get(ref, transaction=None):
    if transaction is not None:
        return ref.get(transaction=transaction)
    return ref.get()


def _txn_set(ref, data: dict, *, merge: bool, transaction=None) -> None:
    if transaction is not None:
        transaction.set(ref, data, merge=merge)
        return
    ref.set(data, merge=merge)


def _is_expired(expires_at, now: datetime.datetime) -> bool:
    if not expires_at:
        return False
    try:
        parsed = datetime.datetime.fromisoformat(str(expires_at))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=LOCAL_TZ)
    return parsed <= now

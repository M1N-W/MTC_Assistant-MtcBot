# -*- coding: utf-8 -*-
"""Roster-based LINE identity proofing without storing raw student IDs."""

from __future__ import annotations

import datetime
import hashlib
import hmac
import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from firebase_admin import firestore
from linebot.v3.messaging import TextMessage

from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.config import LOCAL_TZ, logger
from mtc_assistant.invite_codes import is_valid_class_id


IDENTITY_SESSION_DOC_ID = "identity_verification"
SESSION_TTL_MINUTES = 20
MAX_FAILED_ATTEMPTS = 5
MIN_PEPPER_LENGTH = 16

ACTIVE_CLASS_MATRIX = {
    "mtc11": {"display_name": "MTC11", "grade_level": "m6"},
    "mtc12": {"display_name": "MTC12", "grade_level": "m5"},
    "mtc13": {"display_name": "MTC13", "grade_level": "m4"},
}


@dataclass(frozen=True)
class IdentityResult:
    success: bool
    message: TextMessage


def normalize_identity_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", text)


def build_student_key(student_id: str, pepper: str | None = None) -> str:
    pepper = _require_pepper(pepper)
    normalized = normalize_identity_text(student_id)
    if not normalized:
        raise ValueError("student_id is required")
    return hmac.new(
        pepper.encode("utf-8"),
        normalized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def redacted_message_for_logging(db, user_id: str, user_message: str) -> str:
    if has_identity_session(user_id, db=db) or _looks_like_inline_identity_command(user_message):
        return "[identity input redacted]"
    return str(user_message or "")[:100]


def has_identity_session(user_id: str, db=None) -> bool:
    if not db or not user_id:
        return False
    try:
        snapshot = _session_ref(db, user_id).get()
    except Exception as exc:
        logger.warning("Identity session read failed: %s", exc)
        return False
    return bool(getattr(snapshot, "exists", False))


class IdentitySessionService:
    def __init__(self, db, *, pepper: str | None = None, now_provider=None):
        self.db = db
        self.pepper = pepper
        self.now_provider = now_provider or (lambda: datetime.datetime.now(tz=LOCAL_TZ))

    def start(self, user_id: str) -> IdentityResult:
        if not self.db:
            return _result(False, "ระบบยืนยันตัวตนยังไม่พร้อม ลองใหม่อีกครั้งภายหลัง")
        session = {
            "state": "choose_identity_type",
            "failed_attempts": 0,
            "created_at": self._now_iso(),
            "updated_at": self._now_iso(),
            "expires_at": self._expires_at_iso(),
        }
        _session_ref(self.db, user_id).set(session)
        return _result(True, "เลือกประเภทการยืนยันตัวตน: นักเรียน หรือ คุณครู MTC")

    def handle_message(self, user_id: str, user_message: str) -> IdentityResult | None:
        session = self._load(user_id)
        if not session:
            return None
        if self._is_expired(session):
            self._clear(user_id)
            return _result(False, "ขั้นตอนยืนยันตัวตนหมดเวลาแล้ว พิมพ์ ยืนยันตัวตน เพื่อเริ่มใหม่")

        text = normalize_identity_text(user_message)
        if text == "ยกเลิก":
            self._clear(user_id)
            return _result(True, "ยกเลิกการยืนยันตัวตนแล้ว")
        if text == "เริ่มใหม่":
            return self.start(user_id)

        state = session.get("state")
        if state == "choose_identity_type":
            if _is_teacher_identity_choice(text):
                session.update({"state": "teacher_name"})
                self._save(user_id, session)
                return _result(True, "พิมพ์ชื่อคุณครู MTC ตามรายการที่ผู้ดูแลตั้งค่าไว้")
            if _is_student_identity_choice(text):
                session.update({"state": "choose_class"})
                self._save(user_id, session)
                return _result(True, "เลือกห้องที่ต้องการยืนยันตัวตน: MTC11, MTC12 หรือ MTC13")
            class_id = _class_id_from_user_text(text)
            if class_id:
                session.update({"state": "choose_class"})
                self._save(user_id, session)
            else:
                return self._fail_step(user_id, session, "เลือก นักเรียน หรือ คุณครู MTC")

        if session.get("state") == "choose_class":
            class_id = _class_id_from_user_text(text)
            if not class_id:
                return self._fail_step(user_id, session, "เลือกได้เฉพาะ MTC11, MTC12 หรือ MTC13")
            registry = get_class_registry_entry(self.db, class_id)
            if not registry or registry.status != "active":
                return self._fail_step(user_id, session, "ห้องนี้ยังไม่เปิดให้ยืนยันตัวตน")
            session.update({"state": "student_id", "selected_class_id": class_id})
            self._save(user_id, session)
            return _result(True, "พิมพ์รหัสนักเรียนเพื่อยืนยันตัวตน")

        if state == "teacher_name":
            from mtc_assistant.teacher_identity import find_teacher_by_display_name

            teacher = find_teacher_by_display_name(self.db, text)
            if not teacher:
                return self._fail_step(user_id, session, "ไม่พบรายการคุณครูนี้ กรุณาตรวจสอบชื่อหรือติดต่อแอดมิน")
            session.update({"state": "teacher_code", "teacher_id": teacher.teacher_id})
            self._save(user_id, session)
            return _result(True, "พิมพ์รหัสยืนยันส่วนตัวของคุณครู")

        if state == "teacher_code":
            from mtc_assistant.teacher_identity import verify_teacher_code_and_bind

            result = verify_teacher_code_and_bind(
                self.db,
                user_id,
                str(session.get("teacher_id") or ""),
                text,
                now_provider=self.now_provider,
            )
            if result.success:
                self._clear(user_id)
            return _result(result.success, result.message)

        if state == "student_id":
            try:
                student_key = build_student_key(text, self.pepper)
            except ValueError:
                return self._fail_step(user_id, session, "ข้อมูลนี้ยังใช้ยืนยันไม่ได้")
            session.update({"state": "first_name", "student_key": student_key})
            _drop_raw_student_fields(session)
            self._save(user_id, session)
            return _result(True, "พิมพ์ชื่อจริงตามรายชื่อห้อง")

        if state == "first_name":
            session.update({"state": "last_name", "normalized_first_name": normalize_identity_text(text)})
            self._save(user_id, session)
            return _result(True, "พิมพ์นามสกุลตามรายชื่อห้อง")

        if state == "last_name":
            session.update({"state": "class_number", "normalized_last_name": normalize_identity_text(text)})
            self._save(user_id, session)
            return _result(True, "พิมพ์เลขที่ในห้อง")

        if state == "class_number":
            try:
                class_number = int(text)
            except ValueError:
                return self._fail_step(user_id, session, "เลขที่ในห้องต้องเป็นตัวเลข")
            session.update({"state": "confirm", "class_number": class_number})
            self._save(user_id, session)
            return _result(True, "ตรวจข้อมูลแล้วพิมพ์ ยืนยัน เพื่อผูกบัญชี LINE กับรายชื่อห้อง")

        if state == "confirm":
            if text != "ยืนยัน":
                return _result(False, "พิมพ์ ยืนยัน เพื่อดำเนินการต่อ หรือ ยกเลิก เพื่อยกเลิก")
            return self._bind(user_id, session)

        self._clear(user_id)
        return _result(False, "ขั้นตอนยืนยันตัวตนไม่สมบูรณ์ กรุณาเริ่มใหม่")

    def _bind(self, user_id: str, session: dict) -> IdentityResult:
        try:
            if _supports_firestore_transaction(self.db):
                transaction = self.db.transaction()

                @firestore.transactional
                def bind_in_transaction(transaction):
                    return self._bind_once(user_id, session, transaction=transaction)

                return bind_in_transaction(transaction)
            return self._bind_once(user_id, session)
        except Exception as exc:
            logger.exception("Identity binding failed: %s", exc)
            return _result(False, "ยืนยันตัวตนไม่สำเร็จ กรุณาติดต่อแอดมิน")

    def _bind_once(self, user_id: str, session: dict, transaction=None) -> IdentityResult:
        class_id = str(session.get("selected_class_id") or "")
        student_key = str(session.get("student_key") or "")
        if not is_valid_class_id(class_id) or not student_key:
            return _result(False, "ข้อมูลยืนยันตัวตนไม่ครบ กรุณาเริ่มใหม่")

        registry = get_class_registry_entry(self.db, class_id)
        if not registry or registry.status != "active":
            return _result(False, "ห้องนี้ยังไม่เปิดให้ยืนยันตัวตน")

        roster_ref = _doc_ref(self.db, f"classes/{class_id}/roster/{student_key}")
        roster_doc = _txn_get(roster_ref, transaction)
        if not getattr(roster_doc, "exists", False):
            return self._failed_match(user_id, session)
        roster = roster_doc.to_dict() or {}
        if roster.get("status", "active") != "active":
            return self._failed_match(user_id, session)
        if str(roster.get("bound_user_id") or "") not in ("", user_id):
            return _result(False, "รายชื่อนี้ถูกผูกกับบัญชีอื่นแล้ว กรุณาติดต่อแอดมิน")
        if not self._matches_roster(session, roster):
            return self._failed_match(user_id, session)

        now = self._now_iso()
        user_ref = _doc_ref(self.db, f"users/{user_id}")
        class_user_ref = _doc_ref(self.db, f"classes/{class_id}/users/{user_id}")
        session_ref = _session_ref(self.db, user_id)
        existing_user = _txn_get(user_ref, transaction)
        user_data = existing_user.to_dict() if getattr(existing_user, "exists", False) else {}
        existing_verified_class = str(user_data.get("verified_class_id") or "")
        if existing_verified_class and existing_verified_class != class_id:
            return _result(False, "บัญชีนี้มีข้อมูลยืนยันตัวตนอีกห้องแล้ว กรุณาติดต่อแอดมิน")
        existing_classes = _as_string_list(user_data.get("class_ids"))
        merged_classes = sorted(set(existing_classes + [class_id]))
        full_name = str(roster.get("full_name") or f"{roster.get('first_name', '')} {roster.get('last_name', '')}").strip()

        _txn_set(roster_ref, {
            "bound_user_id": user_id,
            "bound_at": now,
            "updated_at": now,
        }, merge=True, transaction=transaction)
        _txn_set(user_ref, {
            "user_id": user_id,
            "class_ids": merged_classes,
            "active_class_id": class_id,
            "identity_status": "verified",
            "verified_class_id": class_id,
            "last_seen_at": now,
        }, merge=True, transaction=transaction)
        _txn_set(class_user_ref, {
            "user_id": user_id,
            "first_name": roster.get("first_name"),
            "last_name": roster.get("last_name"),
            "full_name": full_name,
            "class_number": roster.get("class_number"),
            "roster_key": student_key,
            "verification_status": "verified",
            "verified_at": now,
            "role": "student",
            "status": "active",
            "last_seen_at": now,
        }, merge=True, transaction=transaction)
        _txn_delete(session_ref, transaction)
        return _result(True, "ยืนยันตัวตนสำเร็จ บัญชี LINE ผูกกับรายชื่อห้องแล้ว")

    def _matches_roster(self, session: dict, roster: dict) -> bool:
        return (
            normalize_identity_text(roster.get("normalized_first_name") or roster.get("first_name"))
            == session.get("normalized_first_name")
            and normalize_identity_text(roster.get("normalized_last_name") or roster.get("last_name"))
            == session.get("normalized_last_name")
            and int(roster.get("class_number") or -1) == int(session.get("class_number") or -2)
        )

    def _failed_match(self, user_id: str, session: dict) -> IdentityResult:
        attempts = int(session.get("failed_attempts", 0) or 0) + 1
        session["failed_attempts"] = attempts
        if attempts >= MAX_FAILED_ATTEMPTS:
            self._clear(user_id)
            return _result(False, "ยืนยันตัวตนไม่สำเร็จหลายครั้ง กรุณาติดต่อแอดมิน")
        self._save(user_id, session)
        return _result(False, "ข้อมูลไม่ตรงกับรายชื่อห้อง กรุณาตรวจสอบแล้วลองใหม่")

    def _fail_step(self, user_id: str, session: dict, message: str) -> IdentityResult:
        session["failed_attempts"] = int(session.get("failed_attempts", 0) or 0) + 1
        if session["failed_attempts"] >= MAX_FAILED_ATTEMPTS:
            self._clear(user_id)
            return _result(False, "ลองไม่สำเร็จหลายครั้ง กรุณาเริ่มใหม่ภายหลัง")
        self._save(user_id, session)
        return _result(False, message)

    def _load(self, user_id: str) -> dict | None:
        if not self.db:
            return None
        snapshot = _session_ref(self.db, user_id).get()
        if not getattr(snapshot, "exists", False):
            return None
        return snapshot.to_dict() or {}

    def _save(self, user_id: str, session: dict) -> None:
        _drop_raw_student_fields(session)
        session["updated_at"] = self._now_iso()
        _session_ref(self.db, user_id).set(session)

    def _clear(self, user_id: str) -> None:
        _session_ref(self.db, user_id).delete()

    def _now_iso(self) -> str:
        return self.now_provider().isoformat()

    def _expires_at_iso(self) -> str:
        return (self.now_provider() + datetime.timedelta(minutes=SESSION_TTL_MINUTES)).isoformat()

    def _is_expired(self, session: dict) -> bool:
        try:
            expires_at = datetime.datetime.fromisoformat(str(session.get("expires_at") or ""))
        except ValueError:
            return True
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=LOCAL_TZ)
        return expires_at <= self.now_provider()


def _session_ref(db, user_id: str):
    return db.collection("users").document(user_id).collection("sessions").document(IDENTITY_SESSION_DOC_ID)


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


def _txn_delete(ref, transaction=None) -> None:
    if transaction is not None:
        transaction.delete(ref)
        return
    ref.delete()


def _require_pepper(pepper: str | None = None) -> str:
    value = str(pepper if pepper is not None else os.environ.get("STUDENT_ID_PEPPER", "")).strip()
    if len(value) < MIN_PEPPER_LENGTH:
        raise ValueError("STUDENT_ID_PEPPER is missing or too weak")
    return value


def _class_id_from_user_text(text: str) -> str | None:
    compact = normalize_identity_text(text).lower().replace(" ", "")
    if compact in ACTIVE_CLASS_MATRIX:
        return compact
    if compact.startswith("mtc") and compact[3:].isdigit():
        candidate = compact
    elif compact.isdigit():
        candidate = f"mtc{compact}"
    else:
        return None
    return candidate if candidate in ACTIVE_CLASS_MATRIX else None


def _is_teacher_identity_choice(text: str) -> bool:
    compact = normalize_identity_text(text).lower().replace(" ", "")
    return compact in {"คุณครูmtc", "ครูmtc", "mtcteacher", "teacher"}


def _is_student_identity_choice(text: str) -> bool:
    compact = normalize_identity_text(text).lower().replace(" ", "")
    return compact in {"นักเรียน", "student"}


def _drop_raw_student_fields(session: dict) -> None:
    for key in ("student_id", "raw_student_id", "submitted_student_id"):
        session.pop(key, None)


def _as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _result(success: bool, text: str) -> IdentityResult:
    return IdentityResult(success, TextMessage(text=text))


def _looks_like_inline_identity_command(user_message: str) -> bool:
    text = normalize_identity_text(user_message).lower()
    return text.startswith(("ยืนยันตัวตน ", "verify ", "identity "))

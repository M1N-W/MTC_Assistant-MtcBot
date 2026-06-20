# -*- coding: utf-8 -*-
"""Invite-code onboarding for class-aware LINE users."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from typing import Any

from firebase_admin import firestore

from mtc_assistant.config import LOCAL_TZ, logger


JOIN_PREFIXES = ("JOIN ", "เข้าห้อง ")
INVITE_CODE_PATTERN = re.compile(r"^[A-Z0-9_-]{3,32}$")
CLASS_ID_PATTERN = re.compile(r"^[a-z0-9_-]{3,40}$")


@dataclass(frozen=True)
class InviteJoinResult:
    success: bool
    message: str
    class_id: str | None = None
    label: str | None = None
    code: str | None = None


def normalize_invite_code(code: str) -> str:
    return (code or "").strip().upper()


def parse_join_code(user_message: str) -> str | None:
    text = (user_message or "").strip()
    upper_text = text.upper()
    if upper_text.startswith("JOIN "):
        code = normalize_invite_code(text[5:])
        return code or None
    if text.startswith("เข้าห้อง "):
        code = normalize_invite_code(text[len("เข้าห้อง "):])
        return code or None
    return None


def is_join_command(user_message: str) -> bool:
    text = (user_message or "").strip()
    return text.upper().startswith("JOIN ") or text.startswith("เข้าห้อง ")


def join_class_with_invite(db, user_id: str, user_message: str, display_name: str = "Unknown") -> InviteJoinResult:
    code = parse_join_code(user_message)
    if not code:
        return InviteJoinResult(False, "พิมพ์ JOIN <code> หรือ เข้าห้อง <code> เพื่อเข้าห้อง", code=None)
    if not is_valid_invite_code(code):
        return InviteJoinResult(False, "invite code ต้องใช้ A-Z, 0-9, _ หรือ - และยาว 3-32 ตัวอักษร", code=code)
    if not db:
        return InviteJoinResult(False, "ระบบฐานข้อมูลยังไม่พร้อม ลองใหม่อีกทีในภายหลัง", code=code)

    try:
        return _join_class_with_invite(db, user_id, code, display_name)
    except Exception as e:
        logger.exception("Invite-code join failed for %s with redacted code: %s", user_id, e)
        return InviteJoinResult(False, "เข้าห้องไม่สำเร็จ ลองใหม่อีกที หรือติดต่อแอดมินห้อง", code=code)


def _join_class_with_invite(db, user_id: str, code: str, display_name: str) -> InviteJoinResult:
    invite_ref = db.collection("class_invites").document(code)
    user_ref = db.collection("users").document(user_id)

    if hasattr(db, "transaction"):
        transaction = db.transaction()
        return _join_class_with_invite_transaction(
            transaction,
            db,
            invite_ref,
            user_ref,
            user_id,
            code,
            display_name,
        )

    return _join_class_with_invite_once(db, invite_ref, user_ref, user_id, code, display_name)


@firestore.transactional
def _join_class_with_invite_transaction(
    transaction,
    db,
    invite_ref,
    user_ref,
    user_id: str,
    code: str,
    display_name: str,
) -> InviteJoinResult:
    return _join_class_with_invite_once(
        db,
        invite_ref,
        user_ref,
        user_id,
        code,
        display_name,
        transaction=transaction,
    )


def _join_class_with_invite_once(
    db,
    invite_ref,
    user_ref,
    user_id: str,
    code: str,
    display_name: str,
    transaction=None,
) -> InviteJoinResult:
    if transaction is not None:
        invite_doc = invite_ref.get(transaction=transaction)
    else:
        invite_doc = invite_ref.get()
    if not getattr(invite_doc, "exists", False):
        return InviteJoinResult(False, "ไม่พบ invite code นี้ ตรวจโค้ดแล้วลองใหม่อีกที", code=code)

    invite = invite_doc.to_dict() or {}
    class_id = str(invite.get("class_id") or "").strip()
    label = str(invite.get("label") or class_id or "ห้องเรียน").strip()
    if not class_id:
        return InviteJoinResult(False, "invite code นี้ยังไม่ได้ผูกกับห้อง ติดต่อแอดมินห้อง", code=code)
    if not is_valid_class_id(class_id):
        return InviteJoinResult(False, "invite code นี้ผูกกับ class_id ที่ไม่ถูกต้อง ติดต่อแอดมินห้อง", code=code)

    if transaction is not None:
        existing_user = user_ref.get(transaction=transaction)
    else:
        existing_user = user_ref.get()
    existing_data = existing_user.to_dict() if getattr(existing_user, "exists", False) else {}
    existing_classes = _as_string_list((existing_data or {}).get("class_ids"))
    already_joined = class_id in existing_classes or (existing_data or {}).get("active_class_id") == class_id

    validation_error = _validate_invite(invite)
    if validation_error and not already_joined:
        return InviteJoinResult(False, validation_error, code=code)

    class_user_ref = (
        db.collection("classes")
        .document(class_id)
        .collection("users")
        .document(user_id)
    )

    now = datetime.datetime.now(tz=LOCAL_TZ)
    global_user_payload = {
        "user_id": user_id,
        "display_name": display_name,
        "active_class_id": class_id,
        "class_ids": sorted(set(existing_classes + [class_id])),
        "identity_status": (existing_data or {}).get("identity_status", "unverified"),
        "status": "active",
        "last_seen_at": firestore.SERVER_TIMESTAMP,
    }
    class_user_payload = {
        "user_id": user_id,
        "display_name": display_name,
        "role": (existing_data or {}).get("role", "student"),
        "status": "active",
        "verification_status": "unverified",
        "joined_at": (existing_data or {}).get("joined_at") or now.isoformat(),
        "last_seen_at": firestore.SERVER_TIMESTAMP,
    }

    if transaction is not None:
        transaction.set(user_ref, global_user_payload, merge=True)
        transaction.set(class_user_ref, class_user_payload, merge=True)
    else:
        user_ref.set(global_user_payload, merge=True)
        class_user_ref.set(class_user_payload, merge=True)

    if not already_joined:
        if transaction is not None:
            transaction.update(invite_ref, {"used_count": firestore.Increment(1)})
        else:
            invite_ref.update({"used_count": firestore.Increment(1)})

    return InviteJoinResult(True, f"เข้าห้อง {label} เรียบร้อยแล้ว", class_id=class_id, label=label, code=code)


def _validate_invite(invite: dict[str, Any]) -> str | None:
    if invite.get("status") != "active":
        return "invite code นี้ยังไม่เปิดใช้งาน ติดต่อแอดมินห้อง"

    expires_at = invite.get("expires_at")
    if _is_expired(expires_at):
        return "invite code นี้หมดอายุแล้ว ติดต่อแอดมินห้อง"

    used_count = _parse_nonnegative_int(invite.get("used_count"), default=0)
    max_uses = _parse_optional_nonnegative_int(invite.get("max_uses"))
    if used_count is None or max_uses == "invalid":
        return "invite code นี้ตั้งค่าไม่ถูกต้อง ติดต่อแอดมินห้อง"
    if max_uses is not None and used_count >= max_uses:
        return "invite code นี้ถูกใช้ครบจำนวนแล้ว ติดต่อแอดมินห้อง"

    return None


def is_valid_invite_code(code: str) -> bool:
    return bool(INVITE_CODE_PATTERN.fullmatch(code or ""))


def is_valid_class_id(class_id: str) -> bool:
    return bool(CLASS_ID_PATTERN.fullmatch(class_id or ""))


def _parse_nonnegative_int(value, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _parse_optional_nonnegative_int(value):
    if value is None:
        return None
    parsed = _parse_nonnegative_int(value)
    return parsed if parsed is not None else "invalid"


def _is_expired(expires_at) -> bool:
    if not expires_at:
        return False
    now = datetime.datetime.now(tz=LOCAL_TZ)
    if hasattr(expires_at, "timestamp"):
        expires_dt = expires_at
    elif isinstance(expires_at, str):
        try:
            expires_dt = datetime.datetime.fromisoformat(expires_at)
        except ValueError:
            return True
    else:
        return True
    if expires_dt.tzinfo is None:
        expires_dt = expires_dt.replace(tzinfo=LOCAL_TZ)
    return expires_dt <= now


def _as_string_list(value) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]

# -*- coding: utf-8 -*-
"""
MTC Assistant - Interactive homework session flow
"""

import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Union

from linebot.v3.messaging import TextMessage

from mtc_assistant.class_context import ClassContext
from mtc_assistant.config import logger
from mtc_assistant.features import add_homework_to_db
from mtc_assistant.quick_replies import build_subject_quick_reply, build_due_date_quick_reply


# In-memory fallback for local/test runs; production handlers pass Firestore.
_homework_sessions: Dict[str, Dict] = {}
_homework_sessions_lock = threading.Lock()
_SESSION_DOC_ID = "homework_create"
_SESSION_SCHEMA_VERSION = 1
_SESSION_TTL_HOURS = 24


class HomeworkSessionStoreReadError(Exception):
    """Raised when durable session state cannot be trusted."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_ref(db, user_id: str):
    if not db:
        return None
    return db.collection("users").document(user_id).collection("sessions").document(_SESSION_DOC_ID)


def _serialize_class_context(class_context) -> dict:
    if not class_context:
        return {}
    return {
        "class_id": getattr(class_context, "class_id", None),
        "role": getattr(class_context, "role", "student"),
        "is_legacy_fallback": bool(getattr(class_context, "is_legacy_fallback", False)),
    }


def _restore_class_context(user_id: str, session: dict, fallback_context=None):
    if fallback_context:
        return fallback_context
    class_id = session.get("class_id")
    if not class_id:
        return None
    return ClassContext(
        class_id=class_id,
        user_id=user_id,
        role=session.get("role") or "student",
        is_legacy_fallback=bool(session.get("is_legacy_fallback", False)),
    )


def _load_session(user_id: str, db=None):
    if db:
        ref = _session_ref(db, user_id)
        try:
            snapshot = ref.get()
        except Exception as e:
            logger.warning("Homework session read failed: %s", e)
            raise HomeworkSessionStoreReadError() from e
        if snapshot and getattr(snapshot, "exists", False):
            return snapshot.to_dict() or {}

    with _homework_sessions_lock:
        session = _homework_sessions.get(user_id)
        return dict(session) if session else None


def _save_session(user_id: str, session: dict, db=None) -> bool:
    if db:
        try:
            _session_ref(db, user_id).set(session)
            return True
        except Exception as e:
            logger.warning("Homework session write failed: %s", e)
            return False
    with _homework_sessions_lock:
        _homework_sessions[user_id] = dict(session)
    return True


def _clear_session(user_id: str, db=None) -> bool:
    cleared = True
    if db:
        try:
            _session_ref(db, user_id).delete()
        except Exception as e:
            logger.warning("Homework session delete failed: %s", e)
            cleared = False
    with _homework_sessions_lock:
        _homework_sessions.pop(user_id, None)
    return cleared


def _is_valid_session(session: dict) -> bool:
    if not isinstance(session, dict):
        return False
    step = session.get("step")
    if step == "subject":
        return True
    if step == "detail":
        return bool(session.get("subject"))
    if step == "due_date":
        return bool(session.get("subject")) and bool(session.get("detail"))
    return False


def _is_expired_session(session: dict) -> bool:
    expires_at = session.get("expires_at")
    if not expires_at:
        return False
    try:
        expires_at_dt = datetime.fromisoformat(str(expires_at))
        if expires_at_dt.tzinfo is None:
            expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)
        return expires_at_dt <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return True


def _safe_restart_message() -> TextMessage:
    return TextMessage(
        text="ขั้นตอนบันทึกการบ้านไม่สมบูรณ์\n\n"
             "พิมพ์ 📝 บันทึกการบ้าน เพื่อเริ่มบันทึกการบ้านใหม่"
    )


def session_read_failure_message() -> TextMessage:
    return TextMessage(
        text="ตอนนี้ระบบบันทึกการบ้านอ่านสถานะไม่สำเร็จ\n"
             "ลองพิมพ์อีกครั้ง หรือพิมพ์ “ยกเลิกการบ้าน” แล้วเริ่มใหม่ได้เลย"
    )


def _session_write_failure_message() -> TextMessage:
    return TextMessage(
        text="ตอนนี้ระบบบันทึกการบ้านบันทึกสถานะไม่สำเร็จ\n"
             "ลองใหม่อีกครั้งได้เลย"
    )


def has_homework_session(user_id: str, db=None) -> bool:
    """Check whether a user is currently creating homework."""
    return _load_session(user_id, db=db) is not None


def start_homework_session(user_id: str, class_context=None, db=None) -> tuple:
    """Start interactive homework creation session"""
    now = _now_iso()
    session = {
        "user_id": user_id,
        "step": "subject",
        "subject": None,
        "detail": None,
        "due_date": None,
        "created_at": now,
        "updated_at": now,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=_SESSION_TTL_HOURS)).isoformat(),
        "schema_version": _SESSION_SCHEMA_VERSION,
        **_serialize_class_context(class_context),
    }
    if not db:
        session["class_context"] = class_context
    if not _save_session(user_id, session, db=db):
        return _session_write_failure_message(), None

    quick_reply = build_subject_quick_reply()

    message = TextMessage(
        text="เลือกวิชาที่จะสั่งการบ้านได้เลย",
        quick_reply=quick_reply
    )

    return message, quick_reply


def handle_homework_session(
    user_id: str,
    user_message: str,
    db=None,
    class_context=None,
) -> Union[TextMessage, tuple]:
    """Handle homework creation step by step"""
    try:
        session = _load_session(user_id, db=db)
    except HomeworkSessionStoreReadError:
        return session_read_failure_message()
    if not session:
        return None

    if _is_expired_session(session) or not _is_valid_session(session):
        if not _clear_session(user_id, db=db):
            return TextMessage(text="ตอนนี้ระบบบันทึกการบ้านลบสถานะไม่สำเร็จ\nลองใหม่อีกครั้งได้เลย")
        return _safe_restart_message()

    step = session["step"]

    # Step 1: Subject selection
    if step == "subject":
        session["subject"] = user_message
        session["step"] = "detail"
        session["updated_at"] = _now_iso()
        if not _save_session(user_id, session, db=db):
            return _session_write_failure_message()

        return TextMessage(
            text=f"📝 เลือกวิชาแล้ว\n\n"
                 f"วิชา: {user_message}\n\n"
                 f"พิมพ์รายละเอียดการบ้านได้เลย\n"
                 f"เช่น แบบฝึกหัด 5.2"
        )

    # Step 2: Detail entry
    elif step == "detail":
        session["detail"] = user_message
        session["step"] = "due_date"
        session["updated_at"] = _now_iso()
        if not _save_session(user_id, session, db=db):
            return _session_write_failure_message()

        quick_reply = build_due_date_quick_reply()

        return TextMessage(
            text=f"📌 รายละเอียดการบ้าน\n\n"
                 f"วิชา: {session['subject']}\n"
                 f"รายละเอียด: {user_message}\n\n"
                 f"กำหนดส่งวันไหน?\n"
                 f"เลือกจากปุ่มด้านล่าง หรือพิมพ์เองก็ได้",
            quick_reply=quick_reply
        )

    # Step 3: Due date and save
    elif step == "due_date":
        session["due_date"] = user_message
        session["updated_at"] = _now_iso()
        if not _save_session(user_id, session, db=db):
            return _session_write_failure_message()

        # Save to database
        subject = session["subject"]
        detail = session["detail"]
        due_date = session["due_date"]
        context_for_save = _restore_class_context(
            user_id,
            session,
            fallback_context=class_context or session.get("class_context"),
        )

        result = add_homework_to_db(subject, detail, due_date, class_context=context_for_save)
        if "เรียบร้อยแล้ว" in result:
            completed_session = dict(session)
            completed_session["step"] = "completed"
            completed_session["updated_at"] = _now_iso()
            _save_session(user_id, completed_session, db=db)

        # Clear session
        cleared = _clear_session(user_id, db=db)

        # Success message with summary
        if "เรียบร้อยแล้ว" in result:
            if not cleared:
                return TextMessage(
                    text="✅ บันทึกการบ้านแล้ว\n\n"
                         "แต่ระบบลบสถานะขั้นตอนไม่สำเร็จ\n"
                         "พิมพ์ “ยกเลิกการบ้าน” แล้วเริ่มใหม่ได้เลยถ้ายังเห็นขั้นตอนเดิม"
                )
            return TextMessage(
                text=f"✅ บันทึกการบ้านแล้ว\n\n"
                     f"วิชา: {subject}\n"
                     f"รายละเอียด: {detail}\n"
                     f"กำหนดส่ง: {due_date}\n\n"
                     f"พิมพ์ “การบ้าน” เพื่อดูรายการทั้งหมด"
            )

        return TextMessage(text=result)

    return None


def cancel_homework_session(user_id: str, db=None) -> str:
    """Cancel homework creation session"""
    try:
        has_session = has_homework_session(user_id, db=db)
    except HomeworkSessionStoreReadError:
        return session_read_failure_message().text
    if has_session:
        if not _clear_session(user_id, db=db):
            return "ตอนนี้ระบบบันทึกการบ้านลบสถานะไม่สำเร็จ\nลองใหม่อีกครั้งได้เลย"
        return "ยกเลิกการเพิ่มการบ้านแล้ว"
    return None

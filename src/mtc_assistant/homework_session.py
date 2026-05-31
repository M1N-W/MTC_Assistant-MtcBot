# -*- coding: utf-8 -*-
"""
MTC Assistant - Interactive homework session flow
"""

import threading
from typing import Dict, Union

from linebot.v3.messaging import TextMessage

from mtc_assistant.features import add_homework_to_db
from mtc_assistant.quick_replies import build_subject_quick_reply, build_due_date_quick_reply


# Store homework creation state for each user
_homework_sessions: Dict[str, Dict] = {}
_homework_sessions_lock = threading.Lock()


def has_homework_session(user_id: str) -> bool:
    """Check whether a user is currently creating homework."""
    return user_id in _homework_sessions


def start_homework_session(user_id: str, class_context=None) -> tuple:
    """Start interactive homework creation session"""
    with _homework_sessions_lock:
        _homework_sessions[user_id] = {
            "step": "subject",
            "subject": None,
            "detail": None,
            "due_date": None,
            "class_context": class_context,
        }

    quick_reply = build_subject_quick_reply()

    message = TextMessage(
        text="เลือกวิชาที่จะสั่งการบ้านได้เลย",
        quick_reply=quick_reply
    )

    return message, quick_reply


def handle_homework_session(user_id: str, user_message: str) -> Union[TextMessage, tuple]:
    """Handle homework creation step by step"""
    if user_id not in _homework_sessions:
        return None

    session = _homework_sessions[user_id]
    step = session["step"]

    # Step 1: Subject selection
    if step == "subject":
        session["subject"] = user_message
        session["step"] = "detail"

        return TextMessage(
            text=f"วิชา: {user_message}\n\n"
                 f"พิมพ์รายละเอียดการบ้านได้เลย\n"
                 f"เช่น ทำแบบฝึกหัด 4.1 หรือ ท่องบทอาขยาน"
        )

    # Step 2: Detail entry
    elif step == "detail":
        session["detail"] = user_message
        session["step"] = "due_date"

        quick_reply = build_due_date_quick_reply()

        return TextMessage(
            text=f"รายละเอียด: {user_message}\n\n"
                 f"กำหนดส่งวันไหน?\n"
                 f"เลือกด้านล่าง หรือพิมพ์เองก็ได้",
            quick_reply=quick_reply
        )

    # Step 3: Due date and save
    elif step == "due_date":
        session["due_date"] = user_message

        # Save to database
        subject = session["subject"]
        detail = session["detail"]
        due_date = session["due_date"]

        result = add_homework_to_db(subject, detail, due_date, class_context=session.get("class_context"))

        # Clear session
        del _homework_sessions[user_id]

        # Success message with summary
        if "เรียบร้อยแล้ว" in result:
            return TextMessage(
                text=f"บันทึกแล้ว\n\n"
                     f"วิชา: {subject}\n"
                     f"รายละเอียด: {detail}\n"
                     f"กำหนดส่ง: {due_date}\n\n"
                     f"พิมพ์ 'การบ้าน' เพื่อดูทั้งหมด"
            )

        return TextMessage(text=result)

    return None


def cancel_homework_session(user_id: str) -> str:
    """Cancel homework creation session"""
    if user_id in _homework_sessions:
        del _homework_sessions[user_id]
        return "ยกเลิกการเพิ่มการบ้านแล้ว"
    return None

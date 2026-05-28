# -*- coding: utf-8 -*-

from typing import Optional

from linebot.v3.messaging import TextMessage

from mtc_assistant.config import logger
from mtc_assistant.classroom_knowledge import answer_classroom_question
from mtc_assistant.features import (
    get_worksheet_message,
    get_school_link_message,
    get_timetable_image_message,
    get_grade_link_message,
    get_absence_form_message,
    get_bio_link_message,
    get_physic_link_message,
    get_help_message,
    get_next_class_message,
    get_time_until_next_class_message,
    get_exam_countdown_message,
    get_music_link_message,
    get_homeworks_from_db,
)
from mtc_assistant.flex_messages import get_links_menu_message


COMMANDS = [
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เช็คเวลาเรียน", "เช็คเวลา"), get_time_until_next_class_message),
    (("ดูงาน",), lambda msg: TextMessage(text=get_homeworks_from_db())),
    (("ลิงก์ที่สำคัญ", "ลิงก์", "links"), get_links_menu_message),
    (("ปฏิทินกิจกรรม", "ปฏิทิน"), get_exam_countdown_message),
    (("ช่วยเหลือ", "คำสั่ง", "help"), get_help_message),
    (("งาน", "การบ้าน", "ใบงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("ลา",), get_absence_form_message),
    (("ชีวะ",), get_bio_link_message),
    (("ฟิสิกส์",), get_physic_link_message),
    (("คาบต่อไป",), get_next_class_message),
    (("อีกกี่นาที",), get_time_until_next_class_message),
    (("สอบ", "วันสอบ"), get_exam_countdown_message),
    (("เปิดเพลง", "หาเพลง"), get_music_link_message),
]

BROAD_EXACT_KEYWORDS = {"งาน", "การบ้าน", "ใบงาน"}


def format_error_message(error: str, suggestion: str = None) -> str:
    message = f"{error}\n"
    if suggestion:
        message += f"\n{suggestion}"
    return message


def handle_standard_command(user_message: str, user_message_lower: str) -> Optional[TextMessage]:
    if user_message_lower.startswith(("ถามเอกสาร", "ค้นเอกสาร", "rag")):
        return TextMessage(text=answer_classroom_question(user_message))

    for keywords, action in COMMANDS:
        matched = False
        for keyword in keywords:
            keyword_lower = keyword.lower()
            is_match = (
                user_message_lower == keyword_lower
                if keyword_lower in BROAD_EXACT_KEYWORDS
                else keyword_lower in user_message_lower
            )
            if is_match:
                try:
                    reply_message = action(user_message)
                    matched = True
                    break
                except Exception as e:
                    logger.exception(f"Error: {e}")
                    reply_message = TextMessage(
                        text=format_error_message(
                            "แงงง ระบบขัดข้องนิดหน่อยฮะ 🥺",
                            "ลองส่งคำสั่งมาใหม่อีกทีน้า"
                        )
                    )
                    break
        if matched:
            return reply_message

    return None

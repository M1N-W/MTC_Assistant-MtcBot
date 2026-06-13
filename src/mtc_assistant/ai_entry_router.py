# -*- coding: utf-8 -*-
"""Pure routing decisions for intentional AI entry."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum

from mtc_assistant.config import LOCAL_TZ


MAX_AI_PROMPT_LENGTH = 1000

_AI_PREFIX = re.compile(
    r"^(?:ai|เอไอ|ถาม\s*(?:ai|เอไอ))(?=$|\s|[:：])",
    re.IGNORECASE,
)
_TRAILING_PUNCTUATION = re.compile(r"[\s?？!！.]+$")
_NATURAL_AI_MARKERS = (
    "ทำไม",
    "คืออะไร",
    "อธิบาย",
    "ช่วยสรุป",
    "ช่วยอธิบาย",
)
_HOMEWORK_MARKERS = ("การบ้าน", "ส่งอะไร", "ส่งไร", "ส่งงาน")
_TIMETABLE_MARKERS = ("เรียนอะไร", "มีเรียน", "ตารางเรียน", "คาบอะไร")
_EXAM_MARKERS = ("สอบ", "กลางภาค", "ปลายภาค")
_QUESTION_MARKERS = ("อะไร", "ไร", "เมื่อไหร่", "วันไหน", "กี่วัน")

_THAI_WEEKDAYS = (
    "วันจันทร์",
    "วันอังคาร",
    "วันพุธ",
    "วันพฤหัสบดี",
    "วันศุกร์",
    "วันเสาร์",
    "วันอาทิตย์",
)
_THAI_MONTHS = (
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)

AI_USAGE_GUIDANCE = (
    "อยากถาม AI เรื่องอะไร พิมพ์แบบนี้ได้เลยนะครับ!\n\n"
    "ai อธิบายเรื่องลำดับเลขคณิต\n"
    "เอไอ ช่วยสรุปเรื่องเมทริกซ์\n"
    "ถามAI ช่วยวางแผนอ่านฟิสิกส์"
)
AI_PROMPT_TOO_LONG = (
    "คำถาม AI ต้องยาวไม่เกิน 1,000 ตัวอักษรนะครับ\n"
    "ลองย่อคำถามแล้วส่งใหม่อีกครั้ง"
)
UNKNOWN_MESSAGE_TEXT = (
    "ยังไม่เจอคำสั่งนี้ในระบบนะครับ\n\n"
    "เลือกทางต่อได้เลย"
)


class AIEntryKind(str, Enum):
    EXPLICIT_AI = "explicit_ai"
    EMPTY_AI = "empty_ai"
    DATE_UTILITY = "date_utility"
    CLASSROOM_BRIDGE = "classroom_bridge"
    NATURAL_AI = "natural_ai"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AIEntryDecision:
    kind: AIEntryKind
    prompt: str = ""
    response_text: str = ""


def classify_ai_entry(message: str, now: datetime | None = None) -> AIEntryDecision:
    """Classify a message without I/O or model calls."""
    text = str(message or "").strip()
    explicit = _explicit_ai_decision(text)
    if explicit:
        if explicit.kind == AIEntryKind.EXPLICIT_AI:
            protected = _protected_prompt_decision(explicit.prompt, now)
            if protected:
                return protected
        return explicit

    normalized = _normalize_question(text)
    if not normalized:
        return AIEntryDecision(AIEntryKind.UNKNOWN)

    date_response = _date_utility_response(normalized, now)
    if date_response:
        return AIEntryDecision(AIEntryKind.DATE_UTILITY, response_text=date_response)

    classroom_response = _classroom_bridge_response(normalized)
    if classroom_response:
        return AIEntryDecision(AIEntryKind.CLASSROOM_BRIDGE, response_text=classroom_response)

    if len(normalized) >= 8 and any(marker in normalized for marker in _NATURAL_AI_MARKERS):
        return AIEntryDecision(AIEntryKind.NATURAL_AI, prompt=text)

    return AIEntryDecision(AIEntryKind.UNKNOWN)


def _protected_prompt_decision(
    prompt: str,
    now: datetime | None,
) -> AIEntryDecision | None:
    normalized = _normalize_question(prompt)
    date_response = _date_utility_response(normalized, now)
    if date_response:
        return AIEntryDecision(AIEntryKind.DATE_UTILITY, response_text=date_response)
    classroom_response = _classroom_bridge_response(normalized)
    if classroom_response:
        return AIEntryDecision(
            AIEntryKind.CLASSROOM_BRIDGE,
            response_text=classroom_response,
        )
    return None


def _explicit_ai_decision(text: str) -> AIEntryDecision | None:
    match = _AI_PREFIX.match(text)
    if not match:
        return None

    prompt = text[match.end():].lstrip(" \t:：").strip()
    if not prompt:
        return AIEntryDecision(AIEntryKind.EMPTY_AI, response_text=AI_USAGE_GUIDANCE)
    if len(prompt) > MAX_AI_PROMPT_LENGTH:
        return AIEntryDecision(AIEntryKind.EMPTY_AI, response_text=AI_PROMPT_TOO_LONG)
    return AIEntryDecision(AIEntryKind.EXPLICIT_AI, prompt=prompt)


def _normalize_question(text: str) -> str:
    return _TRAILING_PUNCTUATION.sub("", text.strip()).strip()


def _date_utility_response(text: str, now: datetime | None) -> str | None:
    today_phrases = ("วันนี้เป็นวันอะไร", "วันนี้วันอะไร", "วันนี้วันที่เท่าไหร่")
    tomorrow_phrases = ("พรุ่งนี้เป็นวันอะไร", "พรุ่งนี้วันอะไร", "พรุ่งนี้วันที่เท่าไหร่")

    if text not in today_phrases and text not in tomorrow_phrases:
        return None

    local_now = now or datetime.now(tz=LOCAL_TZ)
    if local_now.tzinfo is None:
        local_now = local_now.replace(tzinfo=LOCAL_TZ)
    else:
        local_now = local_now.astimezone(LOCAL_TZ)

    target = local_now + timedelta(days=1) if text in tomorrow_phrases else local_now
    label = "พรุ่งนี้" if text in tomorrow_phrases else "วันนี้"
    weekday = _THAI_WEEKDAYS[target.weekday()]
    month = _THAI_MONTHS[target.month]
    return f"{label}คือ{weekday}ที่ {target.day} {month} {target.year}"


def _classroom_bridge_response(text: str) -> str | None:
    if any(marker in text for marker in _HOMEWORK_MARKERS) and any(
        marker in text for marker in _QUESTION_MARKERS
    ):
        return (
            "คำถามนี้ต้องใช้ข้อมูลการบ้านจริงจากระบบนะครับ\n"
            "ตอนนี้พิมพ์ “การบ้าน” เพื่อดูรายการที่บันทึกไว้ได้เลย"
        )

    if any(marker in text for marker in _TIMETABLE_MARKERS):
        return (
            "คำถามนี้ต้องใช้ตารางเรียนจริงของห้องนะครับ\n"
            "ตอนนี้พิมพ์ “ตารางเรียน” เพื่อดูข้อมูลล่าสุดได้เลย"
        )

    if any(marker in text for marker in _EXAM_MARKERS) and any(
        marker in text for marker in _QUESTION_MARKERS
    ):
        return (
            "คำถามนี้ต้องใช้ข้อมูลสอบจริงของห้องนะครับ\n"
            "ตอนนี้พิมพ์ “ปฏิทินกิจกรรม” เพื่อดูข้อมูลที่ระบบมีได้เลย"
        )

    return None

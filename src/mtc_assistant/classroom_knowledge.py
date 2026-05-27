# -*- coding: utf-8 -*-
"""
RAG-lite classroom knowledge assistant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

import mtc_assistant.features as features
from mtc_assistant.config import (
    ABSENCE_LINK,
    Bio_LINK,
    GRADE_LINK,
    Physic_LINK,
    SCHOOL_LINK,
    TIMETABLE_IMG,
    WORKSHEET_LINK,
    logger,
)


@dataclass(frozen=True)
class KnowledgeChunk:
    title: str
    source: str
    text: str


KNOWLEDGE_BASE: List[KnowledgeChunk] = [
    KnowledgeChunk(
        "แหล่งข้อมูลประจำห้อง",
        "MTC Assistant constants",
        (
            f"ลิงก์ตารางงานและใบงาน: {WORKSHEET_LINK}\n"
            f"เว็บไซต์โรงเรียน: {SCHOOL_LINK}\n"
            f"รูปตารางเรียน: {TIMETABLE_IMG}\n"
            f"ระบบตรวจสอบผลการเรียน: {GRADE_LINK}\n"
            f"แบบฟอร์มลาออนไลน์: {ABSENCE_LINK}"
        ),
    ),
    KnowledgeChunk(
        "แหล่งเฉลยและเอกสารวิทยาศาสตร์",
        "MTC Assistant constants",
        f"เฉลยชีววิทยา: {Bio_LINK}\nเฉลยฟิสิกส์: {Physic_LINK}",
    ),
    KnowledgeChunk(
        "ความสามารถหลักของ MTC Assistant",
        "Project feature map",
        (
            "ระบบรองรับตารางเรียน คาบถัดไป เวลาก่อนคาบเรียน การบ้าน วันสอบ "
            "คำนวณเกรด GPA เครื่องคิดเลขอัจฉริยะ ข้อสอบจำลองด้วย Gemini AI "
            "ระบบประกาศ Broadcast บัญชีดำผู้ใช้ และ dashboard ผู้ดูแล"
        ),
    ),
    KnowledgeChunk(
        "แนวคิด Sustainable Innovation",
        "NSC proposal concept",
        (
            "โครงการสนับสนุนห้องเรียนไร้กระดาษโดยแปลงประกาศ การบ้าน และเอกสารให้เป็นข้อมูลดิจิทัล "
            "สนับสนุน SDG 4 ด้วยการเข้าถึงข้อมูลที่เท่าเทียมผ่าน LINE และลดภาระงานซ้ำของผู้แทนห้องกับครู"
        ),
    ),
]


def answer_classroom_question(user_message: str) -> str:
    """Answer a question from curated classroom knowledge with source grounding."""
    question = _strip_trigger(user_message)
    if not question:
        return "พิมพ์คำถามหลังคำว่า ถามเอกสาร เช่น ถามเอกสาร ลิงก์ใบงานอยู่ที่ไหน"

    chunks = _retrieve_chunks(question, limit=3)
    if not chunks:
        return "ยังไม่พบข้อมูลที่เกี่ยวข้องในฐานความรู้ประจำห้อง"

    context = "\n\n".join(
        f"[{index + 1}] {chunk.title}\nแหล่งข้อมูล: {chunk.source}\n{chunk.text}"
        for index, chunk in enumerate(chunks)
    )
    client = features.gemini_client_primary or features.gemini_client_fallback
    model = features.gemini_model_primary or features.gemini_model_fallback
    if client and model:
        prompt = f"""ตอบคำถามจากบริบทเท่านั้น ถ้าไม่มีข้อมูลให้บอกว่าไม่พบข้อมูล
ใช้ภาษาไทย กระชับ และปิดท้ายด้วยแหล่งอ้างอิงเป็นชื่อหัวข้อ

บริบท:
{context}

คำถาม: {question}"""
        try:
            response = client.models.generate_content(model=model, contents=prompt)
            text = _extract_text(response)
            if text:
                return text[:1800]
        except Exception as e:
            logger.error("RAG-lite Gemini answer failed: %s", e)

    sources = ", ".join(chunk.title for chunk in chunks)
    return f"{chunks[0].text[:1200]}\n\nแหล่งอ้างอิง: {sources}"


def _strip_trigger(message: str) -> str:
    cleaned = message.strip()
    for trigger in ("ถามเอกสาร", "ค้นเอกสาร", "rag", "RAG"):
        if cleaned.lower().startswith(trigger.lower()):
            return cleaned[len(trigger):].strip(" :：")
    return cleaned


def _retrieve_chunks(question: str, limit: int) -> List[KnowledgeChunk]:
    terms = _terms(question)
    scored = []
    for chunk in KNOWLEDGE_BASE:
        haystack = f"{chunk.title} {chunk.text}".lower()
        score = sum(1 for term in terms if term in haystack)
        if score:
            scored.append((score, chunk))
    if not scored:
        return KNOWLEDGE_BASE[:1]
    scored.sort(key=lambda item: item[0], reverse=True)
    return [chunk for _, chunk in scored[:limit]]


def _terms(text: str) -> set[str]:
    raw_terms = re.findall(r"[A-Za-z0-9ก-๙]+", text.lower())
    return {term for term in raw_terms if len(term) >= 2}


def _extract_text(response) -> str:
    if hasattr(response, "text") and response.text:
        return str(response.text).strip()
    if hasattr(response, "candidates") and response.candidates:
        parts = getattr(getattr(response.candidates[0], "content", None), "parts", None)
        if parts:
            return "".join(str(part.text) for part in parts if getattr(part, "text", None)).strip()
    return ""

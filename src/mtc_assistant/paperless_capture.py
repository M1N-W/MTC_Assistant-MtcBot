# -*- coding: utf-8 -*-
"""
Paperless Capture AI for classroom note digitization.
"""

from __future__ import annotations

import json
import re
import threading
from typing import Any, Dict

from google.genai import types

import mtc_assistant.features as features
from mtc_assistant.config import LINE_SAFE_TRUNCATE, logger


ALLOWED_IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 6 * 1024 * 1024


class PaperlessCaptureError(Exception):
    """Raised when a paperless capture request cannot be processed."""


def analyze_classroom_image(image_bytes: bytes, mime_type: str, timeout_seconds: float = 25) -> Dict[str, Any]:
    """Summarize a classroom image using Gemini Vision."""
    if not image_bytes:
        raise PaperlessCaptureError("Image content is empty.")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise PaperlessCaptureError("Image is larger than 6 MB.")
    if mime_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise PaperlessCaptureError("Only JPEG, PNG, and WebP images are supported.")

    client = features.gemini_client_primary or features.gemini_client_fallback
    model = features.gemini_model_primary or features.gemini_model_fallback
    if not client or not model:
        raise PaperlessCaptureError("Gemini Vision is not configured.")

    prompt = """วิเคราะห์ภาพกระดาน เอกสาร หรือสไลด์การเรียนนี้สำหรับนักเรียน MTC
ตอบเป็น JSON ล้วนเท่านั้น โดยใช้ schema นี้:
{
  "title": "หัวข้อสั้น",
  "summary": ["สรุปประเด็นที่ 1", "สรุปประเด็นที่ 2"],
  "homework_candidates": ["งานหรือกำหนดส่งที่พบ ถ้าไม่มีให้เป็น []"],
  "keywords": ["คำสำคัญ"],
  "paperless_value": "อธิบายสั้นๆ ว่าภาพนี้ช่วยลดการใช้กระดาษหรือการจดซ้ำอย่างไร"
}
ห้ามใส่ markdown หรือคำอธิบายอื่นนอก JSON"""

    result = {"response": None, "error": None}

    def _call_gemini():
        try:
            result["response"] = client.models.generate_content(
                model=model,
                contents=[
                    prompt,
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ],
            )
        except Exception as e:
            result["error"] = e

    thread = threading.Thread(target=_call_gemini, daemon=True)
    thread.start()
    thread.join(timeout=timeout_seconds)
    if thread.is_alive():
        raise PaperlessCaptureError("Gemini Vision request timed out.")
    if result["error"]:
        if features.is_gemini_quota_error(result["error"]):
            raise PaperlessCaptureError("Gemini Vision quota is temporarily limited. Please try again later.")
        raise PaperlessCaptureError(str(result["error"]))

    raw_text = _extract_text(result["response"])
    parsed = _parse_json_response(raw_text)
    parsed["raw_text"] = raw_text[:LINE_SAFE_TRUNCATE]
    return parsed


def _extract_text(response: Any) -> str:
    if hasattr(response, "text") and response.text:
        return str(response.text).strip()
    if hasattr(response, "candidates") and response.candidates:
        parts = getattr(getattr(response.candidates[0], "content", None), "parts", None)
        if parts:
            return "".join(str(part.text) for part in parts if getattr(part, "text", None)).strip()
    return str(response or "").strip()


def _parse_json_response(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        data = {
            "title": "Paperless Capture",
            "summary": [cleaned[:1000] or "ไม่พบข้อความที่อ่านได้ชัดเจน"],
            "homework_candidates": [],
            "keywords": [],
            "paperless_value": "ระบบช่วยแปลงภาพการเรียนให้เป็นโน้ตดิจิทัลเพื่อลดการจดซ้ำและลดการใช้กระดาษ",
        }

    return {
        "title": str(data.get("title") or "Paperless Capture").strip()[:120],
        "summary": _clean_list(data.get("summary")),
        "homework_candidates": _clean_list(data.get("homework_candidates")),
        "keywords": _clean_list(data.get("keywords"))[:12],
        "paperless_value": str(data.get("paperless_value") or "").strip()[:700],
    }


def _clean_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip()[:700] for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()[:700]]
    return []

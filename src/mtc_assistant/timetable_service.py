# -*- coding: utf-8 -*-
"""Timetable loading, validation, and status formatting."""

from __future__ import annotations

import datetime
import math
from typing import Any

from mtc_assistant.class_context import get_class_registry_entry
from mtc_assistant.config import LOCAL_TZ, SCHEDULE, TIMETABLE_IMG, logger


def schedule_to_firestore_days(schedule: dict[int, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    days: dict[str, list[dict[str, Any]]] = {}
    for weekday, periods in schedule.items():
        normalized = []
        for index, period in enumerate(periods, start=1):
            normalized.append({
                "period": period.get("period", index),
                "start": str(period.get("start", "")).strip(),
                "end": str(period.get("end", "")).strip(),
                "subject": str(period.get("subject", "")).strip(),
                "room": str(period.get("room", "-")).strip() or "-",
            })
        days[str(weekday)] = normalized
    return days


def build_timetable_config(schedule: dict[int, list[dict[str, Any]]], image_url: str | None = None) -> dict[str, Any]:
    config = {
        "timezone": "Asia/Bangkok",
        "days": schedule_to_firestore_days(schedule),
    }
    if image_url:
        config["image_url"] = image_url
    return config


def get_timetable_image_url(db=None, class_context=None) -> str:
    config = _load_timetable_config(db, class_context, validate_days=False)
    image_url = str((config or {}).get("image_url") or "").strip()
    return image_url or TIMETABLE_IMG


def get_timetable_status_text(db=None, class_context=None, now: datetime.datetime | None = None) -> str:
    schedule = _load_schedule_for_context(db, class_context)
    return format_timetable_status(schedule, now or datetime.datetime.now(LOCAL_TZ))


def get_next_class_text(db=None, class_context=None, now: datetime.datetime | None = None) -> str:
    schedule = _load_schedule_for_context(db, class_context)
    return format_next_class(schedule, now or datetime.datetime.now(LOCAL_TZ))


def format_next_class(schedule: dict[int, list[dict[str, Any]]], now: datetime.datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=LOCAL_TZ)

    periods = _valid_periods_for_day(schedule, now.weekday(), now.date())
    if not periods:
        return "วันนี้หยุด ไม่มีเรียนนะ พักให้เต็มที่เลย"

    for period in periods:
        if now < period["start_dt"]:
            return "\n".join([
                "คาบต่อไป",
                "",
                period["subject"],
                _room_line(period),
                _time_range(period),
            ])

        if period["start_dt"] <= now < period["end_dt"]:
            return "\n".join([
                "กำลังเรียนอยู่",
                "",
                period["subject"],
                _room_line(period),
                f"จนถึง {period['end']}",
            ])

    return "หมดคาบแล้วสำหรับวันนี้ กลับบ้านได้เลย"


def format_timetable_status(schedule: dict[int, list[dict[str, Any]]], now: datetime.datetime) -> str:
    if now.tzinfo is None:
        now = now.replace(tzinfo=LOCAL_TZ)

    periods = _valid_periods_for_day(schedule, now.weekday(), now.date())
    if not periods:
        return "วันนี้ไม่มีคาบเรียนในตาราง"

    current = None
    next_period = None
    for index, period in enumerate(periods):
        if period["start_dt"] <= now < period["end_dt"]:
            current = period
            next_period = periods[index + 1] if index + 1 < len(periods) else None
            break
        if now < period["start_dt"]:
            next_period = period
            break

    if current:
        minutes_left = _ceil_minutes(current["end_dt"] - now)
        lines = [
            "ตอนนี้กำลังเรียน",
            "",
            current["subject"],
            _room_line(current),
            _time_range(current),
            "",
            f"เหลืออีก {minutes_left} นาที",
        ]
        if next_period:
            lines.extend([
                "",
                "คาบถัดไป",
                next_period["subject"],
                _room_line(next_period),
                _time_range(next_period),
            ])
        else:
            lines.extend(["", "คาบนี้เป็นคาบสุดท้ายของวันนี้"])
        return "\n".join(lines)

    if next_period:
        minutes_until = _ceil_minutes(next_period["start_dt"] - now)
        is_before_first = next_period == periods[0]
        if is_before_first:
            return "\n".join([
                "ยังไม่เริ่มคาบแรก",
                "",
                f"อีก {minutes_until} นาทีถึงคาบแรก",
                "",
                "คาบแรก",
                next_period["subject"],
                _room_line(next_period),
                _time_range(next_period),
            ])
        return "\n".join([
            "ตอนนี้ไม่มีคาบเรียนในตาราง",
            "",
            f"อีก {minutes_until} นาทีถึงคาบถัดไป",
            "",
            "คาบถัดไป",
            next_period["subject"],
            _room_line(next_period),
            _time_range(next_period),
        ])

    last_period = periods[-1]
    return "\n".join([
        "วันนี้หมดคาบเรียนแล้ว",
        "",
        "คาบสุดท้ายคือ",
        last_period["subject"],
        _room_line(last_period),
        _time_range(last_period),
    ])


def normalize_timetable_config(config: dict[str, Any] | None) -> dict[int, list[dict[str, str]]] | None:
    if not isinstance(config, dict):
        return None
    days = config.get("days")
    if not isinstance(days, dict):
        return None

    normalized: dict[int, list[dict[str, str]]] = {}
    for weekday_raw, raw_periods in days.items():
        try:
            weekday = int(weekday_raw)
        except (TypeError, ValueError):
            return None
        if weekday < 0 or weekday > 6 or not isinstance(raw_periods, list):
            return None

        normalized_periods = []
        for raw_period in raw_periods:
            period = _normalize_period(raw_period)
            if period is None:
                return None
            normalized_periods.append(period)
        normalized[weekday] = normalized_periods

    return normalized


def _load_schedule_for_context(db, class_context) -> dict[int, list[dict[str, Any]]]:
    config = _load_timetable_config(db, class_context)
    normalized = normalize_timetable_config(config)
    return normalized or SCHEDULE


def _load_timetable_config(db, class_context, validate_days: bool = True) -> dict[str, Any] | None:
    if not db or not class_context or getattr(class_context, "is_legacy_fallback", False):
        return None

    try:
        registry = get_class_registry_entry(db, class_context.class_id)
        term_id = registry.active_term_id if registry else None
        if not term_id:
            return None
        doc = (
            db.collection("classes")
            .document(class_context.class_id)
            .collection("terms")
            .document(term_id)
            .collection("config")
            .document("timetable")
            .get()
        )
        if not getattr(doc, "exists", False):
            return None
        data = doc.to_dict() or {}
        if validate_days and normalize_timetable_config(data) is None:
            logger.warning("Invalid timetable config for %s/%s; using fallback", class_context.class_id, term_id)
            return None
        return data
    except Exception as e:
        logger.warning("Could not load timetable config: %s", e)
        return None


def _normalize_period(raw_period) -> dict[str, str] | None:
    if not isinstance(raw_period, dict):
        return None
    start = str(raw_period.get("start") or "").strip()
    end = str(raw_period.get("end") or "").strip()
    subject = str(raw_period.get("subject") or "").strip()
    room = str(raw_period.get("room") or "-").strip() or "-"
    if not start or not end or not subject:
        return None
    try:
        datetime.datetime.strptime(start, "%H:%M")
        datetime.datetime.strptime(end, "%H:%M")
    except ValueError:
        return None
    return {"start": start, "end": end, "subject": subject, "room": room}


def _valid_periods_for_day(schedule: dict[int, list[dict[str, Any]]], weekday: int, date: datetime.date):
    periods = []
    for raw_period in schedule.get(weekday, []):
        period = _normalize_period(raw_period)
        if period is None:
            continue
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_time = datetime.datetime.strptime(period["end"], "%H:%M").time()
        periods.append({
            **period,
            "start_dt": datetime.datetime.combine(date, start_time).replace(tzinfo=LOCAL_TZ),
            "end_dt": datetime.datetime.combine(date, end_time).replace(tzinfo=LOCAL_TZ),
        })
    return sorted(periods, key=lambda item: item["start_dt"])


def _ceil_minutes(delta: datetime.timedelta) -> int:
    return max(0, math.ceil(delta.total_seconds() / 60))


def _room_line(period: dict[str, Any]) -> str:
    return f"ห้อง {period.get('room') or '-'}"


def _time_range(period: dict[str, Any]) -> str:
    return f"{period['start']} - {period['end']}"

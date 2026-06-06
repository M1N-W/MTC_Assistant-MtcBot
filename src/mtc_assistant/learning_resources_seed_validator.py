# -*- coding: utf-8 -*-
"""Offline dry-run validation and planning for learning resource seeds.

Accepted seed input is either a JSON list of resource objects or a JSON object
with a ``resources`` list. This module never imports runtime app services.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping
from urllib.parse import urlparse


TEXTBOOK_SOLUTIONS = "textbook_solutions"
ALLOWED_TEXTBOOK_SOLUTION_SUBJECT_IDS = {"biology", "physics"}
ALLOWED_GRADE_LEVELS = {"m4", "m5", "m6"}
ALLOWED_STATUSES = {"active", "hidden", "archived"}
GENERAL_LINK_FIELDS = {
    "worksheet_url",
    "grade_url",
    "absence_form_url",
    "timetable_image_url",
    "school_url",
    "mtc_game_url",
}
PRIVATE_STUDENT_FIELDS = {
    "student_id",
    "student_number",
    "national_id",
    "phone",
    "line_user_id",
    "line_user_ids",
    "user_id",
}
SECRET_MARKERS = (
    "API_KEY=",
    "TOKEN=",
    "SECRET=",
    "PRIVATE_KEY",
    "BEGIN PRIVATE KEY",
    "LINE_CHANNEL_ACCESS_TOKEN",
    "LINE_CHANNEL_SECRET",
    "MTC_DASHBOARD_API_TOKEN",
    "DASHBOARD_SESSION_SECRET",
    "FIREBASE_PRIVATE_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
ENV_ASSIGNMENT_RE = re.compile(r"\b[A-Z][A-Z0-9_]{2,}\s*=\s*\S+")
JWT_TOKEN_RE = re.compile(r"\b(?:Bearer\s+)?[A-Za-z0-9_-]{32,}\.[A-Za-z0-9_-]{16,}(?:\.[A-Za-z0-9_-]{16,})?\b")
LABELED_OPAQUE_TOKEN_RE = re.compile(
    r"\b(?:Bearer|TOKEN|API[_-]?KEY|SECRET|PRIVATE[_-]?KEY)\s*[=:]?\s*[A-Za-z0-9_.-]{40,}\b",
    re.IGNORECASE,
)
WINDOWS_PATH_RE = re.compile(r"^[A-Za-z]:\\")
UNC_PATH_RE = re.compile(r"^\\\\[^\\]+\\[^\\]+")
ABSOLUTE_LOCAL_PATH_RE = re.compile(r"^/(?:Users|home|private|tmp|var|etc|mnt/[A-Za-z])(?:/|$)")


def plan_learning_resources_seed(
    seed_resources: Iterable[Mapping[str, Any]],
    *,
    existing_resources: Iterable[Mapping[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Validate seed resources and build an offline dry-run plan."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    normalized_seed: list[dict[str, Any]] = []
    seen_ids: dict[tuple[str, str, str], int] = {}
    collisions: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}

    for index, raw in enumerate(seed_resources):
        if not isinstance(raw, Mapping):
            errors.append(_issue(index, None, "Resource must be a JSON object"))
            continue

        record = _normalize_record(raw)
        _validate_record(index, raw, record, errors, warnings)

        identity = _identity(record)
        if all(identity):
            if identity in seen_ids:
                errors.append(_issue(index, record.get("id"), "Duplicate resource id in the same class_id + term_id"))
            seen_ids[identity] = index

        if _is_active_textbook_solution(record):
            key = (
                record["class_id"],
                record["term_id"],
                record["section"],
                record["subject_id"],
                record["type"],
            )
            collisions.setdefault(key, []).append(record)

        normalized_seed.append(record)

    for records in collisions.values():
        if len(records) > 1 and not all(record.get("allow_multiple") is True for record in records):
            ids = ", ".join(record["id"] for record in records)
            errors.append(_issue(None, ids, "Duplicate active textbook_solutions subject/type collision"))

    result = _empty_result(errors, warnings)
    if errors:
        return result

    existing = [_normalize_record(raw) for raw in existing_resources or [] if isinstance(raw, Mapping)]
    existing_by_identity = {_identity(record): record for record in existing if all(_identity(record))}
    seed_by_identity = {_identity(record): record for record in normalized_seed if all(_identity(record))}
    seed_scopes = {(record["class_id"], record["term_id"]) for record in normalized_seed}

    for record in _sort_records(normalized_seed):
        existing_record = existing_by_identity.get(_identity(record))
        if existing_record is None:
            result["would_create"].append(record)
        elif _comparison_payload(record) == _comparison_payload(existing_record):
            result["would_skip"].append(record)
        else:
            result["would_update"].append(record)

    for record in _sort_records(existing):
        scope = (record.get("class_id"), record.get("term_id"))
        if scope not in seed_scopes:
            continue
        if _identity(record) in seed_by_identity:
            continue
        if record.get("status") == "active":
            result["would_disable"].append(record)

    return result


def load_resources_payload(payload: Any) -> list[Mapping[str, Any]]:
    """Extract resources from supported JSON seed or snapshot payloads."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, Mapping) and isinstance(payload.get("resources"), list):
        return payload["resources"]
    raise ValueError("Seed JSON must be a list or an object with a resources list")


def _empty_result(errors: list[dict[str, Any]], warnings: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "would_create": [],
        "would_update": [],
        "would_skip": [],
        "would_disable": [],
        "errors": errors,
        "warnings": warnings,
    }


def _normalize_record(raw: Mapping[str, Any]) -> dict[str, Any]:
    record = dict(raw)
    for key, value in list(record.items()):
        if isinstance(value, str):
            record[key] = value.strip()
    return record


def _validate_record(
    index: int,
    raw: Mapping[str, Any],
    record: Mapping[str, Any],
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    for field in ("class_id", "term_id", "id", "title", "section", "type", "url"):
        if not _non_empty_str(record.get(field)):
            errors.append(_issue(index, record.get("id"), f"{field} is required"))

    resource_id = record.get("id")
    if _non_empty_str(resource_id) and not _is_safe_firestore_id(resource_id):
        errors.append(_issue(index, resource_id, "id must be a safe Firestore document ID"))

    if "enabled" in raw:
        errors.append(_issue(index, resource_id, "enabled is obsolete; use status"))

    status = record.get("status")
    if status not in ALLOWED_STATUSES:
        errors.append(_issue(index, resource_id, "status must be active, hidden, or archived"))

    section = record.get("section")
    subject_id = record.get("subject_id")
    if section == TEXTBOOK_SOLUTIONS and not _non_empty_str(subject_id):
        errors.append(_issue(index, resource_id, "subject_id is required for textbook_solutions"))
    if (
        section == TEXTBOOK_SOLUTIONS
        and _non_empty_str(subject_id)
        and subject_id not in ALLOWED_TEXTBOOK_SOLUTION_SUBJECT_IDS
    ):
        errors.append(_issue(index, resource_id, "subject_id is not supported for textbook_solutions"))
    if _non_empty_str(subject_id) and not _is_safe_firestore_id(subject_id):
        errors.append(_issue(index, resource_id, "subject_id must be a safe non-empty string"))

    grade_level = record.get("grade_level")
    if section == TEXTBOOK_SOLUTIONS and grade_level not in ALLOWED_GRADE_LEVELS:
        errors.append(_issue(index, resource_id, "grade_level must be m4, m5, or m6 for textbook_solutions"))

    url = record.get("url")
    if _non_empty_str(url):
        _validate_url(index, resource_id, url, errors)

    for field in raw.keys():
        if field in GENERAL_LINK_FIELDS:
            warnings.append(_issue(index, resource_id, f"{field} belongs in config/links, not learning resources"))
        if field in PRIVATE_STUDENT_FIELDS:
            errors.append(_issue(index, resource_id, f"{field} looks like private student data"))

    if _contains_secret(raw):
        errors.append(_issue(index, resource_id, "Resource contains secret-looking value"))

    if _contains_local_path(raw):
        errors.append(_issue(index, resource_id, "Resource contains local file path"))


def _validate_url(index: int, resource_id: Any, url: str, errors: list[dict[str, Any]]) -> None:
    if _is_local_path(url):
        errors.append(_issue(index, resource_id, "url must not be a local file path"))
        return

    parsed = urlparse(url)
    if parsed.scheme == "http":
        errors.append(_issue(index, resource_id, "url must use https"))
        return
    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(_issue(index, resource_id, "url must be a valid https URL"))


def _identity(record: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("class_id") or ""),
        str(record.get("term_id") or ""),
        str(record.get("id") or ""),
    )


def _comparison_payload(record: Mapping[str, Any]) -> dict[str, Any]:
    ignored = {"created_at", "updated_at", "updated_by"}
    return {key: record[key] for key in sorted(record) if key not in ignored}


def _is_active_textbook_solution(record: Mapping[str, Any]) -> bool:
    return (
        record.get("status") == "active"
        and record.get("section") == TEXTBOOK_SOLUTIONS
        and _non_empty_str(record.get("subject_id"))
        and _non_empty_str(record.get("type"))
    )


def _sort_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(records, key=lambda record: _identity(record))


def _non_empty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_safe_firestore_id(value: str) -> bool:
    return value not in {".", ".."} and "/" not in value and bool(SAFE_ID_RE.match(value))


def _contains_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_secret(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_secret(child) for child in value)
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return (
        any(marker in upper for marker in SECRET_MARKERS)
        or bool(ENV_ASSIGNMENT_RE.search(value))
        or bool(JWT_TOKEN_RE.search(value))
        or bool(LABELED_OPAQUE_TOKEN_RE.search(value))
    )


def _contains_local_path(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(_contains_local_path(child) for child in value.values())
    if isinstance(value, list):
        return any(_contains_local_path(child) for child in value)
    return isinstance(value, str) and _is_local_path(value.strip())


def _is_local_path(value: str) -> bool:
    return (
        value.startswith("file://")
        or value.startswith("./")
        or value.startswith("../")
        or value.startswith("~/")
        or bool(WINDOWS_PATH_RE.match(value))
        or bool(UNC_PATH_RE.match(value))
        or bool(ABSOLUTE_LOCAL_PATH_RE.match(value))
    )


def _issue(index: int | None, resource_id: Any, message: str) -> dict[str, Any]:
    issue = {"message": message}
    if index is not None:
        issue["index"] = index
    if _non_empty_str(resource_id):
        issue["id"] = resource_id
    return issue

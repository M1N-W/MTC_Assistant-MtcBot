# -*- coding: utf-8 -*-
"""Read-only Firestore readiness check for a class term."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Callable, TextIO

from .learning_resources_service import ALLOWED_GRADE_LEVELS, TEXTBOOK_SOLUTIONS
from .timetable_service import normalize_timetable_config


REQUIRED_LINK_FIELDS = ("school_url", "grade_url", "absence_form_url")
OPTIONAL_TEXTBOOK_SUBJECTS = ("biology", "physics")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ReadinessCheckError(RuntimeError):
    """Raised when the check cannot reliably inspect Firestore."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise ValueError(message)


def check_term_readiness(db: Any, class_id: str, term_id: str) -> dict[str, Any]:
    """Inspect one class term without mutating Firestore."""
    result = _base_result(class_id, term_id)
    registry = _read_document(db, f"system/class_registry/{class_id}/main")
    registry_grade = None

    if registry is None:
        result["checks"]["registry"]["status"] = "missing"
        result["errors"].append("Class registry document is missing.")
    else:
        active_term_id = _nonempty_string(registry.get("active_term_id"))
        registry_grade = _nonempty_string(registry.get("grade_level"))
        registry_status = _nonempty_string(registry.get("status"))
        result["registry_active_term_id"] = active_term_id
        result["registry_grade_level"] = registry_grade
        result["registry_status"] = registry_status
        result["is_active_term"] = active_term_id == term_id

        if registry_grade not in ALLOWED_GRADE_LEVELS:
            result["checks"]["registry"]["status"] = "error"
            result["errors"].append(
                "Registry grade_level must be one of: m4, m5, m6."
            )
        else:
            result["checks"]["registry"]["status"] = "pass"

    term_path = f"classes/{class_id}/terms/{term_id}"
    term = _read_document(db, term_path)
    if term is None:
        result["checks"]["term_doc"]["status"] = "missing"
        result["errors"].append("Term document is missing.")
    else:
        result["checks"]["term_doc"]["status"] = "pass"

    _check_links(db, term_path, result)
    _check_timetable(db, term_path, result)
    _check_resources(db, term_path, registry_grade, result)

    result["ready_to_switch"] = not result["errors"]
    return result


def main(
    argv: list[str] | None = None,
    *,
    db_factory: Callable[[], Any] | None = None,
    stdout: TextIO = sys.stdout,
    stderr: TextIO = sys.stderr,
) -> int:
    del stderr  # The CLI contract is JSON-only.
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--class-id", required=True)
    parser.add_argument("--term-id", required=True)

    try:
        args = parser.parse_args(argv)
        _validate_id("class_id", args.class_id)
        _validate_id("term_id", args.term_id)
    except (ValueError, TypeError) as exc:
        _write_json(
            stdout,
            _fatal_result(None, None, f"Invalid arguments: {exc}"),
        )
        return 2

    try:
        db = (db_factory or _firestore_client)()
        result = check_term_readiness(db, args.class_id, args.term_id)
    except Exception as exc:
        _write_json(
            stdout,
            _fatal_result(
                args.class_id,
                args.term_id,
                f"Readiness check failed: {exc}",
            ),
        )
        return 1

    _write_json(stdout, result)
    return 0


def _check_links(db: Any, term_path: str, result: dict[str, Any]) -> None:
    check = result["checks"]["links_config"]
    links = _read_document(db, f"{term_path}/config/links")
    if links is None:
        check["status"] = "missing"
        result["errors"].append("Links config document is missing.")
        return

    missing_fields = []
    for field in REQUIRED_LINK_FIELDS:
        status = "present" if _nonempty_string(links.get(field)) else "missing"
        check["required_fields"][field] = status
        if status == "missing":
            missing_fields.append(field)

    check["worksheet_url"] = (
        "present"
        if _nonempty_string(links.get("worksheet_url"))
        else "optional_missing"
    )
    if missing_fields:
        check["status"] = "error"
        result["errors"].append(
            "Links config is missing required fields: "
            + ", ".join(missing_fields)
            + "."
        )
    else:
        check["status"] = "pass"


def _check_timetable(db: Any, term_path: str, result: dict[str, Any]) -> None:
    check = result["checks"]["timetable_config"]
    timetable = _read_document(db, f"{term_path}/config/timetable")
    if timetable is None:
        check["status"] = "missing"
        result["errors"].append("Timetable config document is missing.")
        return

    has_image = bool(_nonempty_string(timetable.get("image_url")))
    normalized_days = normalize_timetable_config(timetable)
    has_days = bool(normalized_days)
    check["image_url"] = "present" if has_image else "missing"
    check["days"] = "present" if has_days else "missing_or_invalid"

    if has_image and has_days:
        check["status"] = "pass"
    else:
        check["status"] = "error"
        result["errors"].append(
            "Timetable config requires image_url and valid nonempty days."
        )


def _check_resources(
    db: Any,
    term_path: str,
    registry_grade: str | None,
    result: dict[str, Any],
) -> None:
    check = result["checks"]["resources"]
    resources = _read_collection(db, f"{term_path}/resources")
    active_resources = [
        resource
        for resource in resources
        if _nonempty_string(resource.get("status")) == "active"
    ]
    check["active_count"] = len(active_resources)

    if not active_resources:
        check["status"] = "missing"
        result["errors"].append("Resources collection has no active resources.")
    else:
        check["status"] = "pass"

    for subject_id in OPTIONAL_TEXTBOOK_SUBJECTS:
        subject_resources = [
            resource
            for resource in active_resources
            if _nonempty_string(resource.get("subject_id")) == subject_id
            and _nonempty_string(resource.get("section")) == TEXTBOOK_SOLUTIONS
        ]
        if not subject_resources:
            check["textbook_solutions"][subject_id] = "missing"
            result["warnings"].append(
                f"Active {subject_id} textbook_solutions resource is missing."
            )
        elif registry_grade in ALLOWED_GRADE_LEVELS and any(
            _nonempty_string(resource.get("grade_level")) == registry_grade
            for resource in subject_resources
        ):
            check["textbook_solutions"][subject_id] = "pass"
        elif registry_grade in ALLOWED_GRADE_LEVELS:
            check["textbook_solutions"][subject_id] = "grade_mismatch"
            result["errors"].append(
                f"Active {subject_id} textbook_solutions resource does not "
                f"match registry grade_level {registry_grade}."
            )
        else:
            check["textbook_solutions"][subject_id] = "registry_grade_invalid"

    if any(
        status == "grade_mismatch"
        for status in check["textbook_solutions"].values()
    ):
        check["status"] = "error"


def _read_document(db: Any, path: str) -> dict[str, Any] | None:
    try:
        snapshot = _document(db, path).get()
    except Exception as exc:
        raise ReadinessCheckError(f"Could not read {path}: {exc}") from exc
    if not getattr(snapshot, "exists", False):
        return None
    data = snapshot.to_dict()
    if not isinstance(data, dict):
        raise ReadinessCheckError(f"Document {path} did not contain an object.")
    return data


def _read_collection(db: Any, path: str) -> list[dict[str, Any]]:
    try:
        snapshots = _collection(db, path).stream()
        resources = []
        for snapshot in snapshots:
            data = snapshot.to_dict()
            if not isinstance(data, dict):
                raise ReadinessCheckError(
                    f"Collection {path} contained a non-object document."
                )
            resources.append(data)
        return resources
    except ReadinessCheckError:
        raise
    except Exception as exc:
        raise ReadinessCheckError(f"Could not read {path}: {exc}") from exc


def _document(db: Any, path: str) -> Any:
    parts = path.split("/")
    reference = db.collection(parts[0]).document(parts[1])
    for index in range(2, len(parts), 2):
        reference = reference.collection(parts[index]).document(parts[index + 1])
    return reference


def _collection(db: Any, path: str) -> Any:
    parts = path.split("/")
    reference = db.collection(parts[0]).document(parts[1])
    for index in range(2, len(parts) - 1, 2):
        reference = reference.collection(parts[index]).document(parts[index + 1])
    return reference.collection(parts[-1])


def _validate_id(name: str, value: Any) -> None:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise ValueError(
            f"{name} must contain only letters, numbers, dot, underscore, or hyphen"
        )


def _nonempty_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _base_result(class_id: str | None, term_id: str | None) -> dict[str, Any]:
    return {
        "class_id": class_id,
        "term_id": term_id,
        "registry_active_term_id": None,
        "registry_grade_level": None,
        "registry_status": None,
        "is_active_term": False,
        "ready_to_switch": False,
        "checks": {
            "registry": {"status": "not_checked"},
            "term_doc": {"status": "not_checked"},
            "links_config": {
                "status": "not_checked",
                "required_fields": {
                    field: "not_checked" for field in REQUIRED_LINK_FIELDS
                },
                "worksheet_url": "not_checked",
            },
            "timetable_config": {
                "status": "not_checked",
                "image_url": "not_checked",
                "days": "not_checked",
            },
            "resources": {
                "status": "not_checked",
                "active_count": 0,
                "textbook_solutions": {
                    subject: "not_checked"
                    for subject in OPTIONAL_TEXTBOOK_SUBJECTS
                },
            },
        },
        "warnings": [],
        "errors": [],
    }


def _fatal_result(
    class_id: str | None,
    term_id: str | None,
    message: str,
) -> dict[str, Any]:
    result = _base_result(class_id, term_id)
    result["errors"].append(message)
    return result


def _write_json(output: TextIO, payload: dict[str, Any]) -> None:
    json.dump(payload, output, ensure_ascii=False, indent=2, sort_keys=True)
    output.write("\n")


def _firestore_client() -> Any:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise RuntimeError(
            "firebase-admin is required to use the readiness check"
        ) from exc

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.ApplicationDefault())
    return firestore.client()


if __name__ == "__main__":
    raise SystemExit(main())

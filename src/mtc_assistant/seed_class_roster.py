# -*- coding: utf-8 -*-
"""Dry-run-first roster seed workflow for class identity proofing."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any

from mtc_assistant.identity_verification import build_student_key, normalize_identity_text


ALLOWED_FIELDS = {"student_id", "title", "first_name", "last_name", "full_name", "class_number", "status"}
EXAMPLE_CLASS_ID = "mtc-example"
PRODUCTION_CLASS_EXPECTATIONS = {
    "mtc11": {"grade_level": "m6", "count": 31},
    "mtc12": {"grade_level": "m5", "count": 33},
    "mtc13": {"grade_level": "m4", "count": 36},
}
SECRET_RE = re.compile(r"(TOKEN|SECRET|API[_-]?KEY|PRIVATE[_-]?KEY|PASSWORD)\s*[=:]", re.I)
URL_OR_PATH_RE = re.compile(r"(https?://|www\.|[A-Za-z]:\\|/[^/\s]+/|\.\./)")


def execute_seed(payload: dict, *, db=None, apply: bool = False, pepper: str | None = None, production: bool = False) -> dict:
    errors: list[dict[str, Any]] = []
    class_id = normalize_identity_text(payload.get("class_id"))
    students = payload.get("students")
    if not class_id:
        errors.append(_error("class_id is required"))
    if not isinstance(students, list):
        errors.append(_error("students must be a list"))
        students = []

    if apply and _is_example_value(class_id):
        errors.append(_error("example class_id cannot be applied"))
    if production:
        _validate_production_class_header(payload, db, errors)

    seen_keys: set[str] = set()
    seen_numbers: set[int] = set()
    planned = []
    for index, raw in enumerate(students):
        if not isinstance(raw, dict):
            errors.append(_error("student row must be an object", index))
            continue
        unknown = set(raw) - ALLOWED_FIELDS
        if unknown:
            errors.append(_error(f"unsupported fields: {', '.join(sorted(unknown))}", index))
        if _contains_secret(raw):
            errors.append(_error("row contains secret-like value", index))
        if _contains_unsafe_identity_value(raw):
            errors.append(_error("row contains URL or file-path-like identity value", index))
        if apply and _contains_placeholder(raw):
            errors.append(_error("placeholder row data cannot be applied", index))
        student_id = normalize_identity_text(raw.get("student_id"))
        title = normalize_identity_text(raw.get("title"))
        first_name = normalize_identity_text(raw.get("first_name"))
        last_name = normalize_identity_text(raw.get("last_name"))
        if not student_id or not first_name or not last_name or (production and not title):
            errors.append(_error("student_id, title, first_name, and last_name are required", index))
            continue
        if apply and _is_example_value(student_id):
            errors.append(_error("example student_id cannot be applied", index))
        try:
            class_number = int(raw.get("class_number"))
        except (TypeError, ValueError):
            errors.append(_error("class_number must be an integer", index))
            continue
        if class_number in seen_numbers:
            errors.append(_error("duplicate class_number", index))
        seen_numbers.add(class_number)
        try:
            student_key = build_student_key(student_id, pepper)
        except ValueError as exc:
            errors.append(_error(str(exc), index))
            continue
        if student_key in seen_keys:
            errors.append(_error("duplicate student identifier", index))
        seen_keys.add(student_key)
        planned.append({
            "path": f"classes/{class_id}/roster/{student_key}",
            "index": index,
            "data": {
                "first_name": first_name,
                "last_name": last_name,
                "full_name": normalize_identity_text(raw.get("full_name")) or f"{first_name} {last_name}",
                "normalized_first_name": first_name,
                "normalized_last_name": last_name,
                "class_number": class_number,
                "status": normalize_identity_text(raw.get("status")) or "active",
            },
        })

    if production:
        _validate_production_sequence(class_id, seen_numbers, len(planned), errors)

    if apply and db and not errors:
        registry = _read_doc(db, f"system/class_registry/{class_id}/main")
        if not registry:
            errors.append(_error("class registry is required before apply"))
        else:
            for item in planned:
                _doc_ref(db, item["path"]).set(item["data"], merge=True)

    return {
        "mode": "apply" if apply else "dry-run",
        "class_id": class_id,
        "counts": {
            "would_upsert": len(planned),
            "errors": len(errors),
        },
        "planned_rows": [{"index": item["index"], "path": _redact_roster_path(item["path"])} for item in planned],
        "errors": errors,
    }


def validate_multiple_seeds(payloads: list[dict], *, db=None, pepper: str | None = None) -> dict:
    classes: dict[str, dict[str, Any]] = {}
    errors: list[dict[str, Any]] = []
    seen_student_keys: dict[str, str] = {}
    total_records = 0

    for file_index, payload in enumerate(payloads):
        class_id = normalize_identity_text(payload.get("class_id"))
        result = execute_seed(payload, db=db, apply=False, pepper=pepper, production=True)
        students = payload.get("students") if isinstance(payload.get("students"), list) else []
        total_records += len(students)
        classes[class_id or f"file-{file_index}"] = {
            "class_id": class_id,
            "record_count": len(students),
            "would_upsert": result["counts"]["would_upsert"],
            "errors": result["counts"]["errors"],
            "error_rows": sorted({error.get("index") for error in result["errors"] if "index" in error}),
        }
        errors.extend(_with_context(error, class_id, file_index) for error in result["errors"])
        for index, raw in enumerate(students):
            if not isinstance(raw, dict):
                continue
            student_id = normalize_identity_text(raw.get("student_id"))
            if not student_id:
                continue
            try:
                student_key = build_student_key(student_id, pepper)
            except ValueError as exc:
                errors.append(_error_code("student_id_hmac_failed", str(exc), class_id, index))
                continue
            previous_class = seen_student_keys.get(student_key)
            if previous_class and previous_class != class_id:
                errors.append(_error_code("cross_class_duplicate_student_id", "same student identifier appears in more than one class seed", class_id, index))
            else:
                seen_student_keys[student_key] = class_id

    return {
        "mode": "multi-file-validation",
        "counts": {
            "classes": len(classes),
            "records": total_records,
            "errors": len(errors),
            "cross_class_duplicates": sum(1 for error in errors if error.get("code") == "cross_class_duplicate_student_id"),
        },
        "classes": classes,
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and seed class roster data.")
    parser.add_argument("--seed", required=True, action="append", help="Path to roster seed JSON. May be repeated for validation.")
    parser.add_argument("--apply", action="store_true", help="Write to Firestore. Omit for dry-run.")
    parser.add_argument("--production", action="store_true", help="Enforce production roster counts and class registry grade mapping.")
    parser.add_argument("--validate-only", action="store_true", help="Validate one or more seed files without write planning details.")
    args = parser.parse_args(argv)

    payloads = [json.loads(Path(seed_path).read_text(encoding="utf-8")) for seed_path in args.seed]
    if args.validate_only or len(payloads) > 1:
        result = validate_multiple_seeds(
            payloads,
            db=_get_firestore_db() if args.apply else None,
            pepper=os.environ.get("STUDENT_ID_PEPPER"),
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if result["errors"] else 0

    payload = payloads[0]
    db = _get_firestore_db() if args.apply else None
    result = execute_seed(
        payload,
        db=db,
        apply=args.apply,
        pepper=os.environ.get("STUDENT_ID_PEPPER"),
        production=args.production,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result["errors"] and args.apply else 0


def _get_firestore_db():
    from mtc_assistant.main import db
    if not db:
        raise RuntimeError("Firestore is not initialized")
    return db


def _doc_ref(db, path: str):
    parts = path.split("/")
    ref = db.collection(parts[0]).document(parts[1])
    index = 2
    while index < len(parts):
        ref = ref.collection(parts[index]).document(parts[index + 1])
        index += 2
    return ref


def _read_doc(db, path: str) -> dict:
    snapshot = _doc_ref(db, path).get()
    return snapshot.to_dict() if getattr(snapshot, "exists", False) else {}


def _error(message: str, index: int | None = None) -> dict:
    result = {"message": message}
    if index is not None:
        result["index"] = index
    return result


def _error_code(code: str, message: str, class_id: str = "", index: int | None = None) -> dict:
    result = {"code": code, "message": message}
    if class_id:
        result["class_id"] = class_id
    if index is not None:
        result["index"] = index
    return result


def _with_context(error: dict, class_id: str, file_index: int) -> dict:
    result = dict(error)
    result.setdefault("class_id", class_id)
    result.setdefault("file_index", file_index)
    return result


def _validate_production_class_header(payload: dict, db, errors: list[dict[str, Any]]) -> None:
    class_id = normalize_identity_text(payload.get("class_id"))
    expectation = PRODUCTION_CLASS_EXPECTATIONS.get(class_id)
    if not expectation:
        errors.append(_error_code("unsupported_production_class", "class_id must be mtc11, mtc12, or mtc13 for production validation", class_id))
        return
    if payload.get("academic_year") != 2569:
        errors.append(_error_code("academic_year_mismatch", "academic_year must be 2569", class_id))
    if normalize_identity_text(payload.get("term_id")) != "2569-t1":
        errors.append(_error_code("term_id_mismatch", "term_id must be 2569-t1", class_id))
    students = payload.get("students") if isinstance(payload.get("students"), list) else []
    if len(students) != expectation["count"]:
        errors.append(_error_code("record_count_mismatch", "record count does not match production expectation", class_id))
    if db:
        registry = _read_doc(db, f"system/class_registry/{class_id}/main")
        if not registry or registry.get("status", "active") != "active":
            errors.append(_error_code("registry_inactive_or_missing", "class registry is required and must be active", class_id))
        elif registry.get("grade_level") != expectation["grade_level"]:
            errors.append(_error_code("registry_grade_mismatch", "registry grade_level mismatch", class_id))


def _validate_production_sequence(class_id: str, seen_numbers: set[int], planned_count: int, errors: list[dict[str, Any]]) -> None:
    expectation = PRODUCTION_CLASS_EXPECTATIONS.get(class_id)
    if not expectation:
        return
    expected_numbers = set(range(1, expectation["count"] + 1))
    if seen_numbers != expected_numbers or planned_count != expectation["count"]:
        errors.append(_error_code("class_number_sequence_gap", "class_number sequence must be contiguous for production roster", class_id))


def _contains_secret(row: dict) -> bool:
    return any(SECRET_RE.search(str(value or "")) for value in row.values())


def _contains_unsafe_identity_value(row: dict) -> bool:
    identity_keys = ("title", "first_name", "last_name", "full_name")
    return any(URL_OR_PATH_RE.search(str(row.get(key) or "")) for key in identity_keys)


def _contains_placeholder(row: dict) -> bool:
    return any(_is_example_value(str(value or "")) for value in row.values())


def _is_example_value(value: str) -> bool:
    text = str(value or "").lower()
    return (
        text == EXAMPLE_CLASS_ID
        or text.startswith("example-")
        or "example.com" in text
        or text in {"placeholder", "todo", "tbd", "dummy"}
    )


def _redact_roster_path(path: str) -> str:
    parts = path.split("/")
    if len(parts) >= 4:
        parts[-1] = "<student_key>"
    return "/".join(parts)


if __name__ == "__main__":
    raise SystemExit(main())

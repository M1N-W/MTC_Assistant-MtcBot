# -*- coding: utf-8 -*-
"""Dry-run-first teacher directory seed workflow."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from mtc_assistant.identity_verification import normalize_identity_text
from mtc_assistant.invite_codes import is_valid_class_id
from mtc_assistant.teacher_identity import TEACHER_ASSIGNMENT_ROLES


ALLOWED_TEACHER_FIELDS = {
    "teacher_id",
    "title",
    "first_name",
    "last_name",
    "display_name",
    "verification_code_hash",
    "assignments",
    "status",
}
ALLOWED_ASSIGNMENT_FIELDS = {"class_id", "assignment_roles"}
SECRET_RE = re.compile(r"(TOKEN|SECRET|API[_-]?KEY|PRIVATE[_-]?KEY|PASSWORD)\s*[=:]", re.I)


def execute_seed(payload: dict, *, db=None, apply: bool = False) -> dict:
    errors: list[dict[str, Any]] = []
    teachers = payload.get("teachers")
    if not isinstance(teachers, list):
        errors.append(_error("teachers must be a list"))
        teachers = []

    planned = []
    seen_teacher_ids: set[str] = set()
    assignment_counts = {"mtc13": 0, "mtc12": 0, "mtc11": 0}
    homeroom_count = 0
    single_assignment_count = 0

    for index, raw in enumerate(teachers):
        if not isinstance(raw, dict):
            errors.append(_error("teacher row must be an object", index))
            continue
        unknown = set(raw) - ALLOWED_TEACHER_FIELDS
        if unknown:
            errors.append(_error(f"unsupported fields: {', '.join(sorted(unknown))}", index))
        if "verification_code" in raw:
            errors.append(_error("plaintext verification_code is not allowed", index))
        if _contains_secret(raw):
            errors.append(_error("row contains secret-like value", index))

        teacher_id = normalize_identity_text(raw.get("teacher_id"))
        display_name = normalize_identity_text(raw.get("display_name"))
        code_hash = normalize_identity_text(raw.get("verification_code_hash"))
        if not teacher_id or not display_name or not code_hash:
            errors.append(_error("teacher_id, display_name, and verification_code_hash are required", index))
            continue
        if apply and _is_placeholder_hash(code_hash):
            errors.append(_error("placeholder verification_code_hash cannot be applied", index))
        if teacher_id in seen_teacher_ids:
            errors.append(_error("duplicate teacher_id", index))
        seen_teacher_ids.add(teacher_id)

        assignments = _normalize_assignments(raw.get("assignments"), errors, index)
        if len(assignments) == 1:
            single_assignment_count += 1
        if any("homeroom_teacher" in assignment["assignment_roles"] for assignment in assignments):
            homeroom_count += 1
        for assignment in assignments:
            assignment_counts[assignment["class_id"]] = assignment_counts.get(assignment["class_id"], 0) + 1

        directory_data = {
            "teacher_id": teacher_id,
            "display_name": display_name,
            "normalized_full_name": normalize_identity_text(display_name),
            "status": normalize_identity_text(raw.get("status")) or "active",
            "assigned_class_ids": [assignment["class_id"] for assignment in assignments],
            "assignments": assignments,
            "verification_status": "verified",
        }
        for key in ("title", "first_name", "last_name"):
            value = normalize_identity_text(raw.get(key))
            if value:
                directory_data[key] = value
        planned.append({
            "index": index,
            "teacher_id": teacher_id,
            "directory_path": f"system/teacher_directory/records/{teacher_id}",
            "verification_path": f"system/teacher_verification/records/{teacher_id}",
            "directory": directory_data,
            "verification": {
                "verification_code_hash": code_hash,
                "status": "active",
                "failed_attempts": 0,
            },
        })

    if apply and db and not errors:
        for item in planned:
            _doc_ref(db, item["directory_path"]).set(item["directory"], merge=True)
            _doc_ref(db, item["verification_path"]).set(item["verification"], merge=True)

    return {
        "mode": "apply" if apply else "dry-run",
        "counts": {
            "would_upsert": len(planned),
            "errors": len(errors),
            "single_assignment_teachers": single_assignment_count,
            "homeroom_teachers": homeroom_count,
        },
        "assignment_counts": assignment_counts,
        "planned_rows": [{"index": item["index"], "teacher_id": item["teacher_id"]} for item in planned],
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate and seed MTC teacher directory data.")
    parser.add_argument("--seed", required=True, help="Path to teacher directory seed JSON.")
    parser.add_argument("--apply", action="store_true", help="Write to Firestore. Omit for dry-run.")
    args = parser.parse_args(argv)

    payload = json.loads(Path(args.seed).read_text(encoding="utf-8"))
    db = _get_firestore_db() if args.apply else None
    result = execute_seed(payload, db=db, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if result["errors"] and args.apply else 0


def _normalize_assignments(value, errors: list[dict[str, Any]], index: int) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        errors.append(_error("assignments must be a list", index))
        return []
    assignments = []
    seen_classes: set[str] = set()
    for assignment in value:
        if not isinstance(assignment, dict):
            errors.append(_error("assignment must be an object", index))
            continue
        unknown = set(assignment) - ALLOWED_ASSIGNMENT_FIELDS
        if unknown:
            errors.append(_error(f"unsupported assignment fields: {', '.join(sorted(unknown))}", index))
        class_id = normalize_identity_text(assignment.get("class_id"))
        if not is_valid_class_id(class_id):
            errors.append(_error("assignment class_id is invalid", index))
            continue
        if class_id in seen_classes:
            errors.append(_error("duplicate class assignment", index))
        seen_classes.add(class_id)
        roles = [normalize_identity_text(role) for role in assignment.get("assignment_roles") or []]
        if not roles or any(role not in TEACHER_ASSIGNMENT_ROLES for role in roles):
            errors.append(_error("assignment_roles must contain only supported teacher assignment roles", index))
            continue
        assignments.append({"class_id": class_id, "assignment_roles": roles})
    return assignments


def _doc_ref(db, path: str):
    parts = path.split("/")
    ref = db.collection(parts[0]).document(parts[1])
    index = 2
    while index < len(parts):
        ref = ref.collection(parts[index]).document(parts[index + 1])
        index += 2
    return ref


def _contains_secret(row: dict) -> bool:
    return any(SECRET_RE.search(str(value or "")) for value in row.values())


def _is_placeholder_hash(value: str) -> bool:
    lowered = str(value or "").lower()
    return "replace_with" in lowered or "placeholder" in lowered or lowered in {"todo", "tbd"}


def _error(message: str, index: int | None = None) -> dict:
    result = {"message": message}
    if index is not None:
        result["index"] = index
    return result


def _get_firestore_db():
    from mtc_assistant.main import db
    if not db:
        raise RuntimeError("Firestore is not initialized")
    return db


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""Dry-run-first Firestore seed tool for class learning resources."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable, Mapping, TextIO
from urllib.parse import urlparse

from .learning_resources_seed_validator import (
    ALLOWED_GRADE_LEVELS,
    SAFE_ID_RE,
    TEXTBOOK_SOLUTIONS,
    plan_learning_resources_seed,
)


PLACEHOLDER_DOMAINS = {"example.com", "example.net", "example.org"}
PLACEHOLDER_SUFFIXES = (".example", ".invalid", ".test")
RESOURCE_FIELDS = {
    "id",
    "class_id",
    "term_id",
    "status",
    "section",
    "type",
    "subject_id",
    "subject_label",
    "grade_level",
    "term_label",
    "book_label",
    "title",
    "url",
    "sort_order",
    "notes",
    "description",
    "source_note",
    "ownership_note",
    "allow_multiple",
    "updated_by",
}
COMPARISON_IGNORED_FIELDS = {"created_at", "updated_at"}


def execute_seed(
    db: Any,
    payload: Any,
    *,
    apply: bool = False,
    timestamp: Any = None,
) -> dict[str, Any]:
    """Validate, plan, and optionally apply one class/term resource seed."""
    mode = "apply" if apply else "dry-run"
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    seed = _normalize_seed(payload, errors)
    result = _base_result(mode, seed)
    if errors:
        result["errors"] = errors
        return result

    class_id = seed["class_id"]
    term_id = seed["term_id"]
    registry_path = f"system/class_registry/{class_id}/main"
    registry_snapshot = _document(db, registry_path).get()
    if not registry_snapshot.exists:
        errors.append(_issue(f"Class registry does not exist at {registry_path}"))
        result["errors"] = errors
        return result

    registry = registry_snapshot.to_dict() or {}
    active_term_id = registry.get("active_term_id")
    registry_grade = registry.get("grade_level")
    result["registry_active_term_id"] = active_term_id
    result["registry_grade_level"] = registry_grade
    if not isinstance(active_term_id, str) or not active_term_id.strip():
        errors.append(_issue("Class registry active_term_id is missing"))
    elif term_id != active_term_id.strip():
        errors.append(_issue("Seed term_id must match class registry active_term_id"))
    if registry_grade not in ALLOWED_GRADE_LEVELS:
        errors.append(_issue("Class registry grade_level must be m4, m5, or m6"))

    resources = _flatten_resources(seed, errors)
    validation = plan_learning_resources_seed(resources)
    errors.extend(validation["errors"])
    warnings.extend(validation["warnings"])
    _validate_registry_grades(resources, registry_grade, errors)
    _validate_placeholder_urls(resources, apply, errors, warnings)
    result["errors"] = errors
    result["warnings"] = warnings
    if errors:
        return result

    term_path = f"classes/{class_id}/terms/{term_id}"
    term_snapshot = _document(db, term_path).get()
    create_term_doc = not term_snapshot.exists
    desired_resources = [_resource_write_payload(resource, seed["updated_by"]) for resource in resources]
    planned_create: list[tuple[str, dict[str, Any]]] = []
    planned_update: list[tuple[str, dict[str, Any]]] = []
    skipped: list[str] = []

    for desired in desired_resources:
        resource_id = desired["id"]
        resource_path = f"{term_path}/resources/{resource_id}"
        snapshot = _document(db, resource_path).get()
        if not snapshot.exists:
            planned_create.append((resource_path, desired))
        elif _is_unchanged(desired, snapshot.to_dict() or {}):
            skipped.append(resource_id)
        else:
            planned_update.append((resource_path, desired))

    if not apply:
        result.update(
            {
                "would_create_term_doc": create_term_doc,
                "would_create": [data["id"] for _, data in planned_create],
                "would_update": [data["id"] for _, data in planned_update],
                "would_skip": skipped,
                "no_writes_performed": True,
            }
        )
        return result

    write_timestamp = timestamp if timestamp is not None else _server_timestamp()
    if create_term_doc:
        _document(db, term_path).set(
            {
                "term_id": term_id,
                "status": "active",
                "display_name": seed.get("term_label") or term_id,
                "created_at": write_timestamp,
                "updated_at": write_timestamp,
                "updated_by": seed["updated_by"],
            },
            merge=True,
        )

    for resource_path, desired in planned_create:
        _document(db, resource_path).set(
            {
                **desired,
                "created_at": write_timestamp,
                "updated_at": write_timestamp,
            },
            merge=True,
        )
    for resource_path, desired in planned_update:
        _document(db, resource_path).set(
            {**desired, "updated_at": write_timestamp},
            merge=True,
        )

    result.update(
        {
            "created_term_doc": create_term_doc,
            "created": [data["id"] for _, data in planned_create],
            "updated": [data["id"] for _, data in planned_update],
            "skipped": skipped,
        }
    )
    return result


def main(
    argv: list[str] | None = None,
    *,
    db_factory: Callable[[], Any] | None = None,
    stdout: TextIO | None = None,
    timestamp: Any = None,
) -> int:
    """Run the learning resource seed CLI."""
    parser = argparse.ArgumentParser(description="Validate and seed class learning resources.")
    parser.add_argument("--seed", required=True, help="Path to the learning resources seed JSON.")
    parser.add_argument("--dry-run", action="store_true", help="Validate and preview without writes.")
    parser.add_argument("--apply", action="store_true", help="Apply reviewed creates and updates.")
    args = parser.parse_args(argv)
    output = stdout or sys.stdout

    if args.dry_run and args.apply:
        result = _error_result("Choose either --dry-run or --apply, not both")
        _write_result(output, result)
        return 2

    try:
        payload = json.loads(Path(args.seed).read_text(encoding="utf-8"))
        db = (db_factory or _firestore_client)()
        result = execute_seed(db, payload, apply=args.apply, timestamp=timestamp)
    except (OSError, ValueError, RuntimeError) as exc:
        result = _error_result(str(exc), mode="apply" if args.apply else "dry-run")

    _write_result(output, result)
    return 1 if result["errors"] else 0


def _normalize_seed(payload: Any, errors: list[dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        errors.append(_issue("Seed JSON must be an object"))
        return {}

    seed = dict(payload)
    for field in ("class_id", "term_id", "updated_by"):
        value = seed.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(_issue(f"{field} is required"))
        else:
            seed[field] = value.strip()
    for field in ("class_id", "term_id"):
        value = seed.get(field)
        if isinstance(value, str) and not _is_safe_firestore_id(value):
            errors.append(_issue(f"{field} must be a safe Firestore document ID"))
    resources = seed.get("resources")
    if not isinstance(resources, list) or not resources:
        errors.append(_issue("resources must be a non-empty list"))
    return seed


def _flatten_resources(seed: Mapping[str, Any], errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for index, raw in enumerate(seed["resources"]):
        if not isinstance(raw, Mapping):
            flattened.append(raw)
            continue

        resource = dict(raw)
        embedded_class = resource.get("class_id")
        embedded_term = resource.get("term_id")
        if embedded_class not in (None, "", seed["class_id"]):
            errors.append(_issue("resource class_id conflicts with seed class_id", index, resource.get("id")))
        if embedded_term not in (None, "", seed["term_id"]):
            errors.append(_issue("resource term_id conflicts with seed term_id", index, resource.get("id")))
        resource["class_id"] = seed["class_id"]
        resource["term_id"] = seed["term_id"]
        flattened.append(resource)
    return flattened


def _validate_registry_grades(
    resources: list[dict[str, Any]],
    registry_grade: Any,
    errors: list[dict[str, Any]],
) -> None:
    if registry_grade not in ALLOWED_GRADE_LEVELS:
        return
    for index, resource in enumerate(resources):
        if (
            isinstance(resource, Mapping)
            and resource.get("section") == TEXTBOOK_SOLUTIONS
            and resource.get("status") == "active"
            and resource.get("grade_level") in ALLOWED_GRADE_LEVELS
            and resource.get("grade_level") != registry_grade
        ):
            errors.append(
                _issue(
                    "Active textbook_solutions grade_level must match registry grade_level",
                    index,
                    resource.get("id"),
                )
            )


def _validate_placeholder_urls(
    resources: list[dict[str, Any]],
    apply: bool,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> None:
    for index, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            continue
        url = resource.get("url")
        if not isinstance(url, str) or not _is_placeholder_url(url):
            continue
        issue = _issue("url uses a placeholder domain and cannot be applied", index, resource.get("id"))
        if apply:
            errors.append(issue)
        else:
            warnings.append(issue)


def _is_placeholder_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return (
        any(hostname == domain or hostname.endswith(f".{domain}") for domain in PLACEHOLDER_DOMAINS)
        or hostname.endswith(PLACEHOLDER_SUFFIXES)
    )


def _is_safe_firestore_id(value: str) -> bool:
    return value not in {".", ".."} and "/" not in value and bool(SAFE_ID_RE.match(value))


def _resource_write_payload(resource: Mapping[str, Any], updated_by: str) -> dict[str, Any]:
    payload = {
        key: value
        for key, value in resource.items()
        if key in RESOURCE_FIELDS and value is not None
    }
    payload["updated_by"] = updated_by
    return payload


def _is_unchanged(desired: Mapping[str, Any], existing: Mapping[str, Any]) -> bool:
    return all(
        existing.get(key) == value
        for key, value in desired.items()
        if key not in COMPARISON_IGNORED_FIELDS
    )


def _document(db: Any, path: str) -> Any:
    parts = path.split("/")
    reference = db.collection(parts[0]).document(parts[1])
    for index in range(2, len(parts), 2):
        reference = reference.collection(parts[index]).document(parts[index + 1])
    return reference


def _firestore_client() -> Any:
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
    except ImportError as exc:
        raise RuntimeError("firebase-admin is required to use the seed tool") from exc

    if not firebase_admin._apps:
        firebase_admin.initialize_app(credentials.ApplicationDefault())
    return firestore.client()


def _server_timestamp() -> Any:
    from firebase_admin import firestore

    return firestore.SERVER_TIMESTAMP


def _base_result(mode: str, seed: Mapping[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "mode": mode,
        "class_id": seed.get("class_id"),
        "term_id": seed.get("term_id"),
        "registry_active_term_id": None,
        "registry_grade_level": None,
        "errors": [],
        "warnings": [],
    }
    if mode == "apply":
        result.update(
            {
                "created_term_doc": False,
                "created": [],
                "updated": [],
                "skipped": [],
            }
        )
    else:
        result.update(
            {
                "would_create_term_doc": False,
                "would_create": [],
                "would_update": [],
                "would_skip": [],
                "no_writes_performed": True,
            }
        )
    return result


def _error_result(message: str, *, mode: str = "dry-run") -> dict[str, Any]:
    result = _base_result(mode, {})
    result["errors"] = [_issue(message)]
    return result


def _issue(message: str, index: int | None = None, resource_id: Any = None) -> dict[str, Any]:
    issue: dict[str, Any] = {"message": message}
    if index is not None:
        issue["index"] = index
    if isinstance(resource_id, str) and resource_id.strip():
        issue["id"] = resource_id
    return issue


def _write_result(output: TextIO, result: Mapping[str, Any]) -> None:
    json.dump(result, output, ensure_ascii=False, indent=2, sort_keys=True)
    output.write("\n")


if __name__ == "__main__":
    raise SystemExit(main())

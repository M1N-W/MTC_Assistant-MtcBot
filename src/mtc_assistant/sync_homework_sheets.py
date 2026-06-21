# -*- coding: utf-8 -*-
"""Dry-run first Google Sheets homework sync foundation."""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable, Protocol

from mtc_assistant.firestore_paths import class_collection


EXPECTED_HEADERS = (
    "วันที่สั่ง",
    "วิชา",
    "รายละเอียดงาน",
    "กำหนดส่ง",
    "ปิดงานแล้ว",
    "หมายเหตุ",
    "_homework_id",
    "_revision",
    "_updated_at",
    "_updated_source",
    "_sync_status",
)


@dataclass(frozen=True)
class SheetConfig:
    class_id: str
    spreadsheet_id: str
    sheet_gid: int = 0


SHEET_CONFIGS = {
    "mtc11": SheetConfig("mtc11", "1dXvgPqmY0J1iDkF4muP9lC5VSa4R1sHRBj5bEK8_wec"),
    "mtc12": SheetConfig("mtc12", "1Vcp-ZbIO6fhoDOtIOIJN7h0fMYGuruSV6mIS-j6dz44"),
    "mtc13": SheetConfig("mtc13", "1SlnGJkzu3lko1rSHzRgy76P7uj3Be-DxHylDIdDMLYo"),
}


class SheetSchemaError(ValueError):
    """Raised when the homework Sheet header contract is unsafe."""


class ConflictCode(str, Enum):
    STALE_SHEET_REVISION = "stale_sheet_revision"
    FUTURE_SHEET_REVISION = "future_sheet_revision"
    DUPLICATE_HOMEWORK_ID = "duplicate_homework_id"
    MISSING_FIRESTORE_HOMEWORK = "missing_firestore_homework"


class SheetClient(Protocol):
    def read_rows(self, config: SheetConfig) -> list[list[str]]:
        ...

    def update_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        ...

    def append_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        ...


class FakeSheetClient:
    def __init__(self, rows_by_class: dict[str, list[list[str]]] | None = None):
        self.rows_by_class = rows_by_class or {}
        self.updated: list[tuple[str, list[dict]]] = []
        self.appended: list[tuple[str, list[dict]]] = []

    def read_rows(self, config: SheetConfig) -> list[list[str]]:
        return [list(row) for row in self.rows_by_class.get(config.class_id, [list(EXPECTED_HEADERS)])]

    def update_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        self.updated.append((config.class_id, rows))

    def append_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        self.appended.append((config.class_id, rows))


@dataclass
class SyncResult:
    class_id: str
    rows_scanned: int = 0
    valid_homework_rows: int = 0
    skipped_blank_rows: int = 0
    would_create: int = 0
    would_update: int = 0
    would_skip: int = 0
    would_append: int = 0
    conflicts: int = 0
    errors: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    sheet_writes: int = 0
    conflict_items: list[dict] = field(default_factory=list)
    planned_rows: list[dict] = field(default_factory=list)

    def add_conflict(self, *, row_number: int, code: ConflictCode, homework_id: str | None = None) -> None:
        self.conflicts += 1
        self.conflict_items.append(
            {
                "row_number": row_number,
                "homework_id_present": bool(homework_id),
                "conflict_code": code.value,
            }
        )

    def to_safe_dict(self) -> dict:
        return {
            "class_id": self.class_id,
            "rows_scanned": self.rows_scanned,
            "valid_homework_rows": self.valid_homework_rows,
            "skipped_blank_rows": self.skipped_blank_rows,
            "would_create": self.would_create,
            "would_update": self.would_update,
            "would_skip": self.would_skip,
            "would_append": self.would_append,
            "conflicts": self.conflicts,
            "errors": self.errors,
            "created": self.created,
            "updated": self.updated,
            "deleted": self.deleted,
            "sheet_writes": self.sheet_writes,
            "conflict_items": list(self.conflict_items),
        }


class HomeworkSheetsRepository:
    def __init__(self, db):
        self.db = db

    def get_homework(self, class_id: str, homework_id: str) -> dict | None:
        snapshot = class_collection(self.db, class_id, "homeworks").document(homework_id).get()
        if snapshot and getattr(snapshot, "exists", False):
            return snapshot.to_dict() or {}
        return None

    def set_homework(self, class_id: str, homework_id: str, data: dict) -> None:
        class_collection(self.db, class_id, "homeworks").document(homework_id).set(data, merge=True)

    def list_homeworks(self, class_id: str) -> list[dict]:
        items = []
        for snapshot in class_collection(self.db, class_id, "homeworks").stream():
            data = snapshot.to_dict() or {}
            if data.get("class_id") in (None, class_id):
                items.append(data)
        return items


def get_sheet_config(class_id: str) -> SheetConfig:
    if not class_id or "/" in class_id or "http://" in class_id or "https://" in class_id:
        raise ValueError("Unsupported class_id")
    try:
        return SHEET_CONFIGS[class_id]
    except KeyError as exc:
        raise ValueError("Unsupported class_id") from exc


def validate_header_row(header_row: Iterable[str]) -> None:
    headers = [str(value).strip() for value in header_row]
    if len(headers) < len(EXPECTED_HEADERS):
        raise SheetSchemaError("Missing required homework Sheet columns")
    for index, expected in enumerate(EXPECTED_HEADERS):
        if headers[index] != expected:
            raise SheetSchemaError(f"Unexpected homework Sheet column at position {index + 1}")


def _row_to_dict(row: list, headers: list[str]) -> dict:
    values = list(row) + [""] * max(0, len(headers) - len(row))
    return {header: values[index] if index < len(values) else "" for index, header in enumerate(headers)}


def _parse_sheet_rows(rows: list[list[str]]) -> tuple[list[str], list[tuple[int, dict]]]:
    if not rows:
        raise SheetSchemaError("Missing homework Sheet header")
    validate_header_row(rows[0])
    headers = [str(value).strip() for value in rows[0]]
    parsed = []
    for offset, row in enumerate(rows[1:], start=2):
        parsed.append((offset, _row_to_dict(row, headers)))
    return headers, parsed


def is_valid_homework_row(row: dict) -> bool:
    return bool(str(row.get("วิชา", "")).strip()) and bool(str(row.get("รายละเอียดงาน", "")).strip())


def _revision(value) -> int | None:
    if value in (None, ""):
        return None
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _is_closed(value) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y", "ปิด", "เสร็จ"}


def _doc_from_sheet_row(class_id: str, homework_id: str, row: dict, revision: int) -> dict:
    return {
        "homework_id": homework_id,
        "class_id": class_id,
        "subject": str(row.get("วิชา", "")).strip(),
        "details": str(row.get("รายละเอียดงาน", "")).strip(),
        "detail": str(row.get("รายละเอียดงาน", "")).strip(),
        "assigned_date": str(row.get("วันที่สั่ง", "")).strip(),
        "due_date": str(row.get("กำหนดส่ง", "")).strip() or "ไม่ระบุ",
        "is_closed": _is_closed(row.get("ปิดงานแล้ว")),
        "note": str(row.get("หมายเหตุ", "")).strip(),
        "source": "sheet",
        "revision": revision,
        "updated_source": "sheet",
        "sync_status": "pending",
        "sheet_gid": get_sheet_config(class_id).sheet_gid,
    }


def import_sheet_to_firestore(class_id: str, rows: list[list[str]], repo: HomeworkSheetsRepository, *, apply: bool = False) -> SyncResult:
    get_sheet_config(class_id)
    _headers, parsed_rows = _parse_sheet_rows(rows)
    result = SyncResult(class_id=class_id, rows_scanned=len(parsed_rows))

    for row_number, row in parsed_rows:
        if not is_valid_homework_row(row):
            result.skipped_blank_rows += 1
            continue
        result.valid_homework_rows += 1
        homework_id = str(row.get("_homework_id", "")).strip()
        sheet_revision = _revision(row.get("_revision")) or 1

        if not homework_id:
            result.would_create += 1
            if apply:
                new_id = f"hw-{uuid.uuid4().hex}"
                repo.set_homework(class_id, new_id, _doc_from_sheet_row(class_id, new_id, row, 1))
                result.created += 1
            continue

        existing = repo.get_homework(class_id, homework_id)
        if not existing:
            result.add_conflict(row_number=row_number, code=ConflictCode.MISSING_FIRESTORE_HOMEWORK, homework_id=homework_id)
            continue

        firestore_revision = _revision(existing.get("revision")) or 1
        if sheet_revision < firestore_revision:
            result.add_conflict(row_number=row_number, code=ConflictCode.STALE_SHEET_REVISION, homework_id=homework_id)
            continue
        if sheet_revision > firestore_revision:
            result.add_conflict(row_number=row_number, code=ConflictCode.FUTURE_SHEET_REVISION, homework_id=homework_id)
            continue

        result.would_update += 1
        if apply:
            repo.set_homework(class_id, homework_id, _doc_from_sheet_row(class_id, homework_id, row, firestore_revision + 1))
            result.updated += 1

    return result


def _row_from_doc(doc: dict) -> dict:
    return {
        "วันที่สั่ง": str(doc.get("assigned_date") or doc.get("created_at") or ""),
        "วิชา": str(doc.get("subject") or ""),
        "รายละเอียดงาน": str(doc.get("details") or doc.get("detail") or ""),
        "กำหนดส่ง": str(doc.get("due_date") or ""),
        "ปิดงานแล้ว": "TRUE" if bool(doc.get("is_closed")) else "FALSE",
        "หมายเหตุ": str(doc.get("note") or ""),
        "_homework_id": str(doc.get("homework_id") or ""),
        "_revision": str(_revision(doc.get("revision")) or 1),
        "_updated_at": str(doc.get("updated_at") or ""),
        "_updated_source": str(doc.get("updated_source") or doc.get("source") or "firestore"),
        "_sync_status": str(doc.get("sync_status") or "pending"),
    }


def export_firestore_to_sheet(class_id: str, rows: list[list[str]], repo: HomeworkSheetsRepository, *, apply: bool = False, sheet_client: SheetClient | None = None) -> SyncResult:
    config = get_sheet_config(class_id)
    _headers, parsed_rows = _parse_sheet_rows(rows)
    result = SyncResult(class_id=class_id, rows_scanned=len(parsed_rows))
    row_by_homework_id: dict[str, tuple[int, dict]] = {}

    for row_number, row in parsed_rows:
        homework_id = str(row.get("_homework_id", "")).strip()
        if not homework_id:
            if not is_valid_homework_row(row):
                result.skipped_blank_rows += 1
            continue
        if homework_id in row_by_homework_id:
            result.add_conflict(row_number=row_number, code=ConflictCode.DUPLICATE_HOMEWORK_ID, homework_id=homework_id)
            continue
        row_by_homework_id[homework_id] = (row_number, row)

    updates = []
    appends = []
    for doc in repo.list_homeworks(class_id):
        homework_id = str(doc.get("homework_id") or "").strip()
        if not homework_id:
            continue
        row = _row_from_doc(doc)
        result.planned_rows.append(row)
        if homework_id in row_by_homework_id:
            result.would_update += 1
            updates.append(row)
        else:
            result.would_append += 1
            appends.append(row)

    if apply and sheet_client:
        if updates:
            sheet_client.update_rows(config, updates)
            result.sheet_writes += len(updates)
        if appends:
            sheet_client.append_rows(config, appends)
            result.sheet_writes += len(appends)

    return result


def build_sheet_link_for_user(db, user_id: str, class_id: str) -> str | None:
    config = get_sheet_config(class_id)
    user_snapshot = db.collection("users").document(user_id).get()
    if not user_snapshot or not getattr(user_snapshot, "exists", False):
        return None
    user = user_snapshot.to_dict() or {}
    if class_id not in set(user.get("class_ids") or []):
        return None
    member_snapshot = db.collection("classes").document(class_id).collection("users").document(user_id).get()
    if not member_snapshot or not getattr(member_snapshot, "exists", False):
        return None
    member = member_snapshot.to_dict() or {}
    if member.get("status", "active") != "active":
        return None
    return f"https://docs.google.com/spreadsheets/d/{config.spreadsheet_id}/edit?gid={config.sheet_gid}#gid={config.sheet_gid}"


class GoogleSheetsClient:
    """Small REST client; credentials stay in env and are never logged."""

    def __init__(self):
        try:
            from google.oauth2 import service_account
            from google.auth.transport.requests import AuthorizedSession
        except ImportError as exc:
            raise RuntimeError("Google auth libraries are not installed") from exc

        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        raw_json = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON")
        cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        if raw_json:
            credentials = service_account.Credentials.from_service_account_info(json.loads(raw_json), scopes=scopes)
        elif cred_path:
            credentials = service_account.Credentials.from_service_account_file(cred_path, scopes=scopes)
        else:
            raise RuntimeError("Google Sheets credentials are not configured")
        self.session = AuthorizedSession(credentials)

    def read_rows(self, config: SheetConfig) -> list[list[str]]:
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{config.spreadsheet_id}/values/A:K"
        response = self.session.get(url, timeout=20)
        response.raise_for_status()
        return response.json().get("values", [])

    def update_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        raise NotImplementedError("Sheet row update is intentionally deferred behind dry-run review")

    def append_rows(self, config: SheetConfig, rows: list[dict]) -> None:
        raise NotImplementedError("Sheet row append is intentionally deferred behind dry-run review")


def create_default_sheet_client() -> SheetClient:
    return GoogleSheetsClient()


def _create_firestore_repo() -> HomeworkSheetsRepository:
    import firebase_admin
    from firebase_admin import firestore

    if not firebase_admin._apps:
        firebase_admin.initialize_app()
    return HomeworkSheetsRepository(firestore.client())


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run first homework Google Sheets sync")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("import", "export"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--class-id", required=True, choices=sorted(SHEET_CONFIGS))
        mode = sub.add_mutually_exclusive_group()
        mode.add_argument("--dry-run", action="store_true", default=True)
        mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    config = get_sheet_config(args.class_id)
    client = create_default_sheet_client()
    repo = _create_firestore_repo()
    rows = client.read_rows(config)
    apply = bool(args.apply)
    if args.command == "import":
        result = import_sheet_to_firestore(args.class_id, rows, repo, apply=apply)
    else:
        result = export_firestore_to_sheet(args.class_id, rows, repo, apply=apply, sheet_client=client)
    print(json.dumps(result.to_safe_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

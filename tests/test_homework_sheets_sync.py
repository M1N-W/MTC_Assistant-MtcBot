import json
import unittest
from io import StringIO
from unittest.mock import patch

from tests.fake_firestore import FakeDb

from mtc_assistant.sync_homework_sheets import (
    EXPECTED_HEADERS,
    ConflictCode,
    FakeSheetClient,
    HomeworkSheetsRepository,
    SheetSchemaError,
    build_sheet_link_for_user,
    export_firestore_to_sheet,
    get_sheet_config,
    import_sheet_to_firestore,
    is_valid_homework_row,
    main,
    validate_header_row,
)


HEADER = list(EXPECTED_HEADERS)


class HomeworkSheetsSyncTest(unittest.TestCase):
    def test_sheet_mapping_three_classes(self):
        self.assertEqual(
            "1dXvgPqmY0J1iDkF4muP9lC5VSa4R1sHRBj5bEK8_wec",
            get_sheet_config("mtc11").spreadsheet_id,
        )
        self.assertEqual("1Vcp-ZbIO6fhoDOtIOIJN7h0fMYGuruSV6mIS-j6dz44", get_sheet_config("mtc12").spreadsheet_id)
        self.assertEqual("1SlnGJkzu3lko1rSHzRgy76P7uj3Be-DxHylDIdDMLYo", get_sheet_config("mtc13").spreadsheet_id)
        self.assertEqual(0, get_sheet_config("mtc11").sheet_gid)

    def test_unknown_class_and_user_supplied_url_rejected(self):
        with self.assertRaises(ValueError):
            get_sheet_config("https://docs.google.com/spreadsheets/d/bad/edit")
        with self.assertRaises(ValueError):
            get_sheet_config("mtc10")

    def test_schema_validation(self):
        validate_header_row(HEADER)
        with self.assertRaises(SheetSchemaError):
            validate_header_row(HEADER[:6] + ["wrong"] + HEADER[7:])
        with self.assertRaises(SheetSchemaError):
            validate_header_row(HEADER[:6])
        validate_header_row(HEADER + ["ผู้ใช้เพิ่มเอง"])

    def test_row_validity_skips_blank_and_missing_visible_fields(self):
        self.assertFalse(is_valid_homework_row({"ปิดงานแล้ว": "FALSE"}))
        self.assertFalse(is_valid_homework_row({"วิชา": "", "รายละเอียดงาน": "งาน"}))
        self.assertFalse(is_valid_homework_row({"วิชา": "คณิต", "รายละเอียดงาน": ""}))
        self.assertTrue(is_valid_homework_row({"วิชา": "คณิต", "รายละเอียดงาน": "แบบฝึกหัด"}))

    def test_import_dry_run_aggregates_without_writes_or_details(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        rows = [
            HEADER,
            ["21/06/2569", "คณิต", "แบบฝึกหัด", "22/06/2569", "FALSE", "", "", "", "", "", ""],
            ["", "", "", "", "FALSE", "", "", "", "", "", ""],
        ]
        result = import_sheet_to_firestore("mtc12", rows, repo, apply=False)

        self.assertEqual(2, result.rows_scanned)
        self.assertEqual(1, result.valid_homework_rows)
        self.assertEqual(1, result.skipped_blank_rows)
        self.assertEqual(1, result.would_create)
        self.assertEqual({}, db.store)
        payload = result.to_safe_dict()
        self.assertNotIn("แบบฝึกหัด", json.dumps(payload, ensure_ascii=False))

    def test_import_matching_revision_would_update(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        repo.set_homework(
            "mtc12",
            "hw-1",
            {"homework_id": "hw-1", "class_id": "mtc12", "subject": "เดิม", "details": "เดิม", "revision": 2},
        )
        rows = [
            HEADER,
            ["21/06/2569", "คณิต", "ใหม่", "22/06/2569", "FALSE", "", "hw-1", "2", "", "sheet", ""],
        ]

        result = import_sheet_to_firestore("mtc12", rows, repo, apply=False)

        self.assertEqual(1, result.would_update)
        self.assertEqual(0, result.conflicts)
        self.assertEqual("เดิม", repo.get_homework("mtc12", "hw-1")["subject"])

    def test_import_revision_conflicts(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        repo.set_homework("mtc12", "hw-1", {"homework_id": "hw-1", "class_id": "mtc12", "revision": 3})
        rows = [
            HEADER,
            ["21/06/2569", "คณิต", "งาน", "", "FALSE", "", "hw-1", "2", "", "sheet", ""],
            ["21/06/2569", "ฟิสิกส์", "งาน", "", "FALSE", "", "hw-1", "4", "", "sheet", ""],
        ]

        result = import_sheet_to_firestore("mtc12", rows, repo, apply=False)

        self.assertEqual(2, result.conflicts)
        self.assertEqual(ConflictCode.STALE_SHEET_REVISION.value, result.conflict_items[0]["conflict_code"])
        self.assertEqual(ConflictCode.FUTURE_SHEET_REVISION.value, result.conflict_items[1]["conflict_code"])
        self.assertNotIn("คณิต", json.dumps(result.to_safe_dict(), ensure_ascii=False))

    def test_import_apply_creates_without_destructive_deletes(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        rows = [
            HEADER,
            ["21/06/2569", "คณิต", "งาน", "", "FALSE", "", "", "", "", "", ""],
        ]

        result = import_sheet_to_firestore("mtc13", rows, repo, apply=True)

        self.assertEqual(1, result.created)
        self.assertEqual(1, len([p for p in db.store if p.startswith("classes/mtc13/homeworks/")]))
        self.assertEqual(0, result.deleted)

    def test_export_dry_run_updates_appends_and_duplicate_conflict(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        repo.set_homework(
            "mtc11",
            "hw-1",
            {"homework_id": "hw-1", "class_id": "mtc11", "subject": "คณิต", "details": "งาน", "revision": 1},
        )
        repo.set_homework(
            "mtc11",
            "hw-2",
            {"homework_id": "hw-2", "class_id": "mtc11", "subject": "ฟิสิกส์", "details": "งาน", "revision": 1},
        )
        rows = [
            HEADER,
            ["", "คณิต", "งาน", "", "FALSE", "", "hw-1", "1", "", "firestore", ""],
            ["", "ซ้ำ", "งาน", "", "FALSE", "", "hw-1", "1", "", "firestore", ""],
        ]

        result = export_firestore_to_sheet("mtc11", rows, repo, apply=False)

        self.assertEqual(1, result.would_update)
        self.assertEqual(1, result.would_append)
        self.assertEqual(1, result.conflicts)
        self.assertEqual(0, result.sheet_writes)

    def test_export_closed_homework_maps_to_checkbox(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        repo.set_homework(
            "mtc11",
            "hw-1",
            {"homework_id": "hw-1", "class_id": "mtc11", "subject": "คณิต", "details": "งาน", "is_closed": True, "revision": 1},
        )

        row = export_firestore_to_sheet("mtc11", [HEADER], repo, apply=False).planned_rows[0]

        self.assertEqual("TRUE", row["ปิดงานแล้ว"])

    def test_no_class_crosses_to_another_spreadsheet(self):
        db = FakeDb()
        repo = HomeworkSheetsRepository(db)
        repo.set_homework("mtc12", "hw-1", {"homework_id": "hw-1", "class_id": "mtc12", "revision": 1})

        result = export_firestore_to_sheet("mtc11", [HEADER], repo, apply=False)

        self.assertEqual(0, result.would_append)

    def test_general_user_cannot_access_class_sheet_link(self):
        db = FakeDb()
        db.store["users/general"] = {"class_ids": []}
        db.store["users/member"] = {"class_ids": ["mtc12"]}
        db.store["classes/mtc12/users/member"] = {"status": "active"}

        self.assertIsNone(build_sheet_link_for_user(db, "general", "mtc12"))
        self.assertIn("1Vcp-ZbIO6fhoDOtIOIJN7h0fMYGuruSV6mIS-j6dz44", build_sheet_link_for_user(db, "member", "mtc12"))

    def test_cli_dry_run_outputs_safe_aggregate(self):
        rows = [
            HEADER,
            ["21/06/2569", "คณิต", "แบบฝึกหัด", "", "FALSE", "", "", "", "", "", ""],
        ]
        client = FakeSheetClient({"mtc12": rows})
        repo = HomeworkSheetsRepository(FakeDb())

        with patch("mtc_assistant.sync_homework_sheets.create_default_sheet_client", return_value=client), \
                patch("mtc_assistant.sync_homework_sheets._create_firestore_repo", return_value=repo), \
                patch("sys.stdout", new_callable=StringIO) as stdout:
            code = main(["import", "--class-id", "mtc12", "--dry-run"])

        output = stdout.getvalue()
        self.assertEqual(0, code)
        self.assertIn('"would_create": 1', output)
        self.assertNotIn("แบบฝึกหัด", output)


if __name__ == "__main__":
    unittest.main()

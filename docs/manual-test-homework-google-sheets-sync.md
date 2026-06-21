# Manual Test: Homework Google Sheets Sync Foundation

Scope: Master Plan 1 Phase 5A only. This verifies dry-run importer/exporter
behavior before any production Google Sheets write is approved.

## Preconditions

- Real Google credentials are configured outside Git using exactly one of:
  - `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`
  - `GOOGLE_APPLICATION_CREDENTIALS`
- Each target Sheet is shared with the service account.
- The Sheet header row exactly matches the Phase 5A schema.
- No Apps Script webhook, scheduler, deployment, or LINE Quick Reply change is
  part of this test.

## Dry-Run Import

```powershell
$env:PYTHONPATH='src'
python -m mtc_assistant.sync_homework_sheets import --class-id mtc12 --dry-run
```

Expected result:

- command exits successfully;
- output is aggregate-only;
- blank rows and checkbox-only rows are skipped;
- rows with missing `วิชา` or `รายละเอียดงาน` are skipped;
- stale or future revisions are reported as conflicts;
- no Firestore writes are made.

Repeat for `mtc11` and `mtc13`.

## Dry-Run Export

```powershell
$env:PYTHONPATH='src'
python -m mtc_assistant.sync_homework_sheets export --class-id mtc12 --dry-run
```

Expected result:

- command exits successfully;
- existing `_homework_id` rows are not duplicated;
- missing Firestore homework documents are counted as would-append;
- duplicate `_homework_id` rows are reported as conflicts;
- closed homework maps to the `ปิดงานแล้ว` checkbox value;
- no Google Sheets writes are made.

Repeat for `mtc11` and `mtc13`.

## Class Isolation

Run each class independently and confirm the reported `class_id` always matches
the requested class. Do not pass spreadsheet URLs to the command. Unknown class
IDs must be rejected.

## Conflict Test

1. Pick a non-production test row.
2. Set `_revision` lower than Firestore.
3. Run import dry-run.
4. Confirm `stale_sheet_revision` appears with row number only.
5. Set `_revision` higher than Firestore.
6. Run import dry-run.
7. Confirm `future_sheet_revision` appears with row number only.

The output must not include homework details, credentials, LINE IDs, student
data, or Firestore paths.

## First Apply Readiness

Do not run `--apply` until a human approves:

- exact class;
- exact Sheet;
- expected create/update counts;
- rollback plan;
- Firestore backup/export point;
- conflict count is zero or explicitly accepted.

## Rollback

Importer apply never hard-deletes homework based on missing Sheet rows. Rollback
for accidental creates or updates must use Firestore document history/backups and
the aggregate run output to locate the affected class and run window.

## Out of Scope

- realtime two-way sync;
- Apps Script webhook;
- scheduler jobs;
- LINE Quick Reply activation;
- production deployment;
- Dashboard authentication changes;
- MTC67 changes;
- AI routing changes.

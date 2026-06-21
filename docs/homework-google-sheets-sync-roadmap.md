# Homework Google Sheets Sync Roadmap

## Placement

This belongs to Master Plan 1, Phase 5: Homework System Maturity.

Subphase: Google Sheets Bidirectional Homework Sync.

Current implementation status: Phase 5A foundation only. It provides a
dry-run-first importer/exporter, class Sheet mapping, schema validation, stable
`homework_id`/`revision` handling, and conflict detection. It does not enable
Apps Script, realtime sync, scheduler jobs, production Sheet writes, or LINE
Quick Reply changes.

It is not part of the LINE account identity proofing implementation.

## Confirmed Sheet IDs

| Class | Google Sheet ID |
| --- | --- |
| MTC11 | `1dXvgPqmY0J1iDkF4muP9lC5VSa4R1sHRBj5bEK8_wec` |
| MTC12 | `1Vcp-ZbIO6fhoDOtIOIJN7h0fMYGuruSV6mIS-j6dz44` |
| MTC13 | `1SlnGJkzu3lko1rSHzRgy76P7uj3Be-DxHylDIdDMLYo` |

## Recommended Architecture

Firestore remains the source of truth. Google Sheets is an editable mirror.

LINE Quick Reply writes to the Homework Service first. The sync layer exports
validated Firestore homework records to the class-specific Sheet.

Sheet edits must return through a signed Apps Script webhook or reviewed
scheduled importer before updating Firestore.

## Required Record Identity

Each homework item needs a stable identifier shared by Firestore and Sheets:

- `homework_id`
- `class_id`
- `term_id`
- `subject`
- `title`
- `details`
- `assigned_date`
- `due_date`
- `status`
- `source`
- `revision`
- `updated_at`
- `updated_by`
- `sheet_row_id`
- `sync_status`

Do not match rows by subject and title alone.

## Conflict Policy

- Higher revision wins when one side clearly supersedes the other.
- Equal revision with different content becomes `conflict`.
- Do not silently use last-write-wins.
- Deletion uses `status: hidden` or `status: cancelled`, not hard delete.
- Every conflict resolution requires audit metadata.

## Security Rules

- Sheet IDs are mapped server-side by `class_id`.
- Never accept an arbitrary Sheet ID from a LINE user.
- Google credentials and Apps Script secrets stay in environment/config only.
- Webhook requests require a secret or signature.
- Validate every Sheet row before writing Firestore.
- Sync only the Sheet assigned to the active class.

## Deferred UX

Future Quick Reply after the sync foundation exists:

1. บันทึกผ่าน MTC Assistant
2. เปิดตารางงาน Google Sheets

Do not add this Quick Reply before the schema, importer, exporter, conflict
handling, and authorization tests exist.

## Phase 5A Command Surface

Dry-run is the default operating posture:

```powershell
$env:PYTHONPATH='src'
python -m mtc_assistant.sync_homework_sheets import --class-id mtc12 --dry-run
python -m mtc_assistant.sync_homework_sheets export --class-id mtc12 --dry-run
```

`--apply` is reserved for reviewed operator runs after credentials and Sheet
sharing are configured. It must not be used as part of deployment.

Safe output is aggregate-only by default:

- class ID;
- rows scanned;
- valid homework rows;
- skipped blank rows;
- create/update/append counts;
- conflict counts and row numbers;
- error counts.

It must not print homework details, student identifiers, LINE IDs, Google
credentials, tokens, or Firestore paths.

## Phase 5A Sheet Schema

Visible columns:

| Column | Header |
| --- | --- |
| A | วันที่สั่ง |
| B | วิชา |
| C | รายละเอียดงาน |
| D | กำหนดส่ง |
| E | ปิดงานแล้ว |
| F | หมายเหตุ |

Hidden system columns:

| Column | Header |
| --- | --- |
| G | _homework_id |
| H | _revision |
| I | _updated_at |
| J | _updated_source |
| K | _sync_status |

A row is homework only when both `วิชา` and `รายละเอียดงาน` are present.
Checkbox-only blank rows are ignored.

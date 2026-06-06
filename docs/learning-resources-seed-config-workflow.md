# Learning Resources Seed/Config Workflow

## Purpose

This plan defines the safest workflow for seeding and managing class/term-scoped learning resources before the 2026-06-09 MTC12/MTC13 code-family reveal event.

The workflow exists to reduce production URL mistakes, configure MTC13+ resources safely, keep MTC12 legacy behavior stable, and move ordinary class data toward Firestore without large refactors. It should make future implementation small, reviewable, and testable while keeping the sprint focused on demo value and production stability.

## Current State

- General Links Firestore-first is done.
- Learning Resources read-only service exists.
- `ชีวะ` and `ฟิสิกส์` commands for MTC13+ use learning resources with `section=textbook_solutions` and subject IDs `biology` / `physics`.
- MTC12 legacy biology and physics solution links still work.
- MTC13+ must not silently fall back to MTC12 subject-specific resources.
- If a class should reuse an old resource, it must be explicitly configured for that class and term.
- MTC67 is unrelated to learning resources and must stay hidden.

## Risk Sheet

Deliverable:
Docs-only seed/config workflow plan for future learning resources implementation.

Tightest constraint:
Presentation readiness by 2026-06-09 with low blast radius and no production URL mistakes.

Blast radius:
Learning resource Firestore documents, `ชีวะ` / `ฟิสิกส์` command responses, MTC12 legacy solution behavior, MTC13+ class isolation, cross-class resource leakage risk, user-facing command regressions, and manual LINE verification.

Dependency graph:
Seed input -> validation -> dry-run summary -> optional apply -> Firestore resource docs -> `learning_resources_service.py` -> `features.py` solution command responses.

Load order:
Class registry resolves active term first, then resources load from `/classes/{classId}/terms/{termId}/resources/{resourceId}`.

Smallest delta:
Start with a validator and dry-run summary only. Add explicit apply later after the dry-run output is trustworthy.

Architecture smells:
General links and learning resources can be confused unless resource types and paths stay explicit. Firestore writes without a dry-run preview create avoidable production URL risk. Overengineering before June 9 would reduce demo stability.

Exit criteria:
Dry-run shows intended creates, updates, skips, disables, errors, and warnings before any write. Future apply mode writes only reviewed class/term-scoped resources. Existing MTC12 legacy behavior and MTC13+ no-fallback behavior remain covered by tests and manual LINE checks.

Rollback plan:
Prefer disabling resources over deleting them. Re-run a previous seed or disable newly created resources if a mistake is detected.

## Data Scope and Resource Types

General links are operational links such as worksheet, school, grade, absence form, timetable image, or game links. Preferred path:

- `/classes/{classId}/terms/{termId}/config/links`

Learning resources are study resources owned by a class and term. Preferred path:

- `/classes/{classId}/terms/{termId}/resources/{resourceId}`

Textbook solutions are subject-specific solution manuals used by commands such as `ชีวะ` and `ฟิสิกส์`.

Assignment resources are class-shared files or assignment-related resources. They should not be mixed into general links unless a future product decision explicitly changes that boundary.

High-level resource document shape for future implementation:

- `id`
- `class_id`
- `term_id`
- `subject`
- `subject_id`
- `subject_label`
- `grade_level`
- `title`
- `section`
- `type`
- `url`
- `description`
- `status`
- `sort_order`
- `created_at`
- `updated_at`
- `updated_by`
- `source_note` or `ownership_note`

Real production URLs must be verified before write. Use fake/sample data in docs unless real URLs are explicitly provided by Mawin.

## Seed Input Format

Use a local JSON file with one explicit class and term:

```json
{
  "class_id": "mtc-example",
  "term_id": "2569-t1",
  "updated_by": "local-operator",
  "resources": [
    {
      "id": "biology-m4-t1-solutions",
      "status": "active",
      "section": "textbook_solutions",
      "type": "solution_manual",
      "subject_id": "biology",
      "grade_level": "m4",
      "title": "Sample biology solutions",
      "url": "https://example.com/sample"
    }
  ]
}
```

The example domain is intentionally rejected by apply mode. Replace it only in a
local ignored seed after Mawin verifies the real URL. Store real seed files under
`local-seeds/`, which is ignored by Git. Do not include student data, rosters,
secrets, or credentials.

## Dry-Run-First Workflow

Use Application Default Credentials through the standard Google environment:

```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS='C:\path\outside-the-repo\service-account.json'
$env:PYTHONPATH='src'
python -m mtc_assistant.seed_learning_resources --seed local-seeds\resources.json
```

Dry-run is the default. `--dry-run` is accepted when an explicit command is
preferred. It reads the class registry and current resource documents but never
writes:

```powershell
python -m mtc_assistant.seed_learning_resources --seed local-seeds\resources.json --dry-run
```

After reviewing the JSON summary, apply the same file explicitly:

```powershell
python -m mtc_assistant.seed_learning_resources --seed local-seeds\resources.json --apply
```

`--dry-run` and `--apply` cannot be combined. Apply mode creates a missing parent
term document and creates or updates the listed resource documents. It skips
unchanged documents. It does not delete, disable, archive, or modify resources
that are absent from the seed, and it never modifies the class registry.

Dry-run reports `would_create`, `would_update`, `would_skip`, `errors`, and
`warnings`. Apply reports `created`, `updated`, `skipped`, `errors`, and
`warnings`.

## Validation Rules

- `class_id` must be explicit.
- `term_id` must be explicit.
- `subject_id` must be from allowed known subjects or normalized before write.
- `url` must be `https` unless there is a justified exception.
- `status` must be `active`, `hidden`, or `archived`.
- `textbook_solutions` must declare `grade_level` as `m4`, `m5`, or `m6`.
- Runtime only returns textbook solutions when the resource grade exactly matches the class registry grade.
- MTC13+ must never fall back to MTC12 subject-specific resources.
- `title` must not be empty.
- Accidental duplicate subject/type collisions should fail unless explicitly allowed.
- Secret-looking values must fail validation.
- Local file paths must not be accepted for production resources.
- Preview image/video fields are not needed for normal learning resources unless a future UI requires them.

## Idempotency and Rollback

- Re-running the same seed should not duplicate documents.
- Stable resource IDs are required.
- Updates should be deterministic.
- Old resources should use `hidden` or `archived`, not be deleted, in the first implementation.
- Rollback can re-run a previous seed or disable newly created resources.
- Firestore writes should include `updated_by` and `updated_at`.

## User-Facing Behavior Expectations

- `ชีวะ` returns the correct class/term-scoped biology resource for the active class.
- `ฟิสิกส์` returns the correct class/term-scoped physics resource for the active class.
- MTC12 legacy biology and physics behavior remains stable.
- MTC13+ does not see MTC12 legacy resources unless explicitly configured.
- Missing resources return a friendly unavailable/config-needed message.
- Responses should be short, clear, and usable by students.

## Testing and Verification Plan

Future implementation verification commands:

- `python -m compileall -q src`
- `$env:PYTHONPATH='src'; python -m unittest tests.test_learning_resources_service tests.test_links_service tests.test_links_commands`
- `$env:PYTHONPATH='src'; python -m unittest discover -s tests`
- `git diff --check -- <touched files>`

Manual LINE test checklist after user-facing behavior changes:

- MTC12 `ชีวะ`
- MTC12 `ฟิสิกส์`
- MTC13 `ชีวะ`
- MTC13 `ฟิสิกส์`
- Missing resource fallback
- `ลิงก์`
- `งาน`
- `ตารางเรียน` if supported by the changed path
- MTC67 exact-match regression only if command routing was touched

## Presentation Readiness for 2026-06-09

This workflow supports the June 9 event by making resource configuration stable, reducing last-minute URL mistakes, increasing confidence in MTC13 onboarding, and letting Mawin shift focus to UX/demo polish after backend resource config is safe.

Before June 9, only high-ROI, low-blast-radius work should be done. Avoid broad dashboard, auth, or multi-tenant refactors during this sprint.

## Phased Plan

Phase A: Docs-only workflow plan.

Phase B: Offline seed validator.

Phase C: Dry-run-first CLI with explicit create/update apply mode and fake-Firestore tests.

Phase D: Add real class resources only after URLs and ownership are verified.

Phase E: Run manual LINE tests after resource data is intentionally applied.

Phase F: Add a dashboard editor later, after dashboard auth and class-admin boundaries are ready.

The dashboard editor is later, not now.

## Non-Goals

- No dashboard auth implementation.
- No dashboard resource editor now.
- No full multi-tenant migration.
- No roster import.
- No real production URLs unless Mawin explicitly provides verified ones.
- No destructive deletes in the first seed workflow.
- No Render deploy.
- No MTC67 UI promotion.
- No command routing rewrite unless necessary.

## Security and Privacy Checklist

- No secrets in repo.
- No environment values in docs.
- No real rosters.
- No raw student IDs.
- No cross-class leakage.
- Explicit `class_id` and `term_id`.
- Dry-run by default.
- Review before apply.
- Audit trail fields for writes.
- No browser exposure of dashboard API token.
- Keep class admin write features for later after auth is ready.

## Open Questions

- Where should seed input files live later?
- Should resource IDs be human-readable or generated?
- How should subjects be normalized in Thai and English?
- Should `term_id` format be `2026-t1`, `term1-2026`, or another convention?
- Who verifies ownership and accuracy of URLs?
- How should multiple resources for one subject be represented?
- How should expired resources be handled?
- How much of this should move to the dashboard later?

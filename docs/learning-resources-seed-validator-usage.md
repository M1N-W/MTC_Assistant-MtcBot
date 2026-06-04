# Learning Resources Seed Validator Usage

## Purpose

The Learning Resources seed validator is a Phase B safety tool for checking local JSON seed files before any future production write workflow exists.

It validates class/term-scoped learning resource records and prints a dry-run plan only. It does not write Firestore, does not have an apply mode, does not change LINE behavior, and does not require a Render deploy.

## Resource Boundaries

General operational links belong under:

```text
classes/{classId}/terms/{termId}/config/links
```

Examples include worksheet, grade, absence form, timetable image, school, and game links.

Learning resources belong under:

```text
classes/{classId}/terms/{termId}/resources/{resourceId}
```

Examples include textbook solution links, assignment resources, and class-shared study materials.

MTC13 and future classes must not silently fall back to MTC12 subject-specific resources. If a class should reuse a resource, it must have an explicit record for its own `class_id` and `term_id`.

## Run The Fake Seed

Use the fake example seed to check the dry-run output shape:

```powershell
python scripts/validate_learning_resources_seed.py --seed docs/examples/learning-resources-seed.example.json
```

Expected output categories:

- `would_create`
- `would_update`
- `would_skip`
- `would_disable`
- `errors`
- `warnings`

The fake seed should produce no errors or warnings and should list three `would_create` records when no existing snapshot is provided.

## Validation Rules

- `class_id` and `term_id` are required.
- Resource URLs must use `https://`.
- `http://` URLs are hard validation errors.
- Local/private file paths are rejected.
- Secret-looking values are rejected.
- Duplicate resource IDs are rejected within the same `class_id` and `term_id`.
- `textbook_solutions` requires `subject_id`.
- `textbook_solutions` currently accepts only `biology` and `physics`.
- `subject_id` is optional outside subject-specific sections, but must be safe if present.
- General link fields such as `worksheet_url`, `grade_url`, `absence_form_url`, `timetable_image_url`, `school_url`, and `mtc_game_url` do not belong in learning resource seeds.
- There is no destructive delete category.

## Phase C Is Deferred

Phase C apply mode is intentionally not implemented yet. Real production resource URLs and ownership must be verified before any future tool writes to Firestore.

Until then, this workflow stays dry-run only:

- No `--apply`.
- No Firestore writes.
- No Firebase credentials required.
- No production URLs in example files.
- No student data, roster data, LINE user IDs, secrets, tokens, or environment values.

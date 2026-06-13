# Learning Resources Seed Validator Usage

> **Historical Phase B usage:** The repository now has an implemented
> dry-run-first Firestore seed/apply workflow. Use
> [Learning Resources Seed/Config Workflow](learning-resources-seed-config-workflow.md)
> for the current authoritative workflow. This file is retained for the
> offline validator interface and must not be read as current dry-run-only
> system status.

## Purpose

The Learning Resources seed validator is a Phase B safety tool for checking
local JSON seed files. It remains useful for offline validation before using
the current Firestore-aware workflow.

This specific validator prints a dry-run plan and does not write Firestore.
The separate current CLI supports reviewed dry-run and explicit apply modes as
documented in the authoritative workflow.

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
- `status` is required and must be `active`, `hidden`, or `archived`.
- The obsolete `enabled` field is rejected.
- Resource URLs must use `https://`.
- `http://` URLs are hard validation errors.
- Local/private file paths are rejected.
- Secret-looking values are rejected.
- Duplicate resource IDs are rejected within the same `class_id` and `term_id`.
- `textbook_solutions` requires `subject_id`.
- `textbook_solutions` currently accepts only `biology` and `physics`.
- `textbook_solutions` requires `grade_level` and accepts only `m4`, `m5`, or `m6`.
- Runtime only serves textbook solutions whose grade matches the class registry grade exactly.
- `subject_id` is optional outside subject-specific sections, but must be safe if present.
- General link fields such as `worksheet_url`, `grade_url`, `absence_form_url`, `timetable_image_url`, `school_url`, and `mtc_game_url` do not belong in learning resource seeds.
- There is no destructive delete category.
- Collision detection and disable planning consider only `status=active` resources.

## Phase C Status

Phase C is implemented through the Firestore-aware
`mtc_assistant.seed_learning_resources` workflow. Dry-run remains the default,
and apply requires an explicit `--apply` after review. Real production URLs and
ownership must be verified before writes.

This offline validator still:

- performs no Firestore writes;
- requires no Firebase credentials;
- keeps production URLs out of example files; and
- accepts no student data, roster data, LINE user IDs, secrets, tokens, or
  environment values.

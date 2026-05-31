# MTC13 Multi-Class Manual Test Record

## Summary

- Test date: 2026-05-31
- Result: passed
- Scope: deployed MTC13 multi-class onboarding, class-aware timetable commands, MTC12 fallback behavior, and TEST_MTC13 invite lifecycle.
- Final test invite state: `TEST_MTC13` was disabled after testing with `used_count` remaining at `1`.

## Deployment/Commit Context

The manual test was performed after deploying the MTC13 multi-class rollout and follow-up fixes through `main`.

Relevant local commits:

- `686c818 feat: add multi-class onboarding and timetable foundation`
- `d1ade9c fix: run bot from package entrypoint on Render`
- `a4d001e fix: track first message in rate limiter`
- `217528a fix: recover Firebase connection after health probe timeout`
- `74b1ec3 feat: add food randomizer command`
- `3fd1f03 chore: refine grade calculator feedback and user-scope tests`
- `6d38cb5 chore: seed timetable image urls for mtc12 and mtc13`

## Firebase Documents Verified

- `/healthz` reported Firebase as healthy.
- `system/class_registry/mtc13/main` exists and has `active_term_id`.
- `classes/mtc13/terms/2569-t1/config/timetable` exists and has `image_url` plus `days`.
- `class_invites/TEST_MTC13` was active during the test.
- The test user record was reset before onboarding validation.
- `users/{userId}.active_class_id` became `mtc13` after joining.
- `classes/mtc13/users/{userId}` was created after joining.
- Rejoining with `TEST_MTC13` did not increment `used_count`.
- `class_invites/TEST_MTC13` was disabled after the test.
- `class_invites/TEST_MTC13.used_count` ended at `1`.

## LINE Commands Tested

- Unknown user before JOIN: class-specific timetable command was blocked.
- Unknown user before JOIN: `help` worked.
- `JOIN TEST_MTC13` succeeded.
- `ตารางเรียน` sent the MTC13 timetable image.
- `คาบต่อไป` used MTC13 timetable data.
- `เช็คเวลาเรียน` used MTC13 timetable data.
- MTC12 user behavior was verified after the MTC13 flow.

## Passed Checklist

- [x] Deployment responded through `/healthz`.
- [x] Firebase health status was true.
- [x] MTC13 class registry resolved the active term.
- [x] MTC13 timetable config included `image_url` and `days`.
- [x] Unknown users could not use class-specific timetable commands before JOIN.
- [x] Unknown users could still use `help` before JOIN.
- [x] `JOIN TEST_MTC13` created the correct root user class state.
- [x] `JOIN TEST_MTC13` created the class-scoped user document.
- [x] Rejoining was idempotent and did not increment invite usage.
- [x] MTC13 timetable image response did not fall back to MTC12.
- [x] MTC13 next-class and timetable-status commands used class-aware data.
- [x] MTC12 user behavior remained valid.
- [x] `TEST_MTC13` was disabled after manual testing.

## Known Limitations

- Exam countdown is still hardcoded and not class-aware.
- Dashboard editor and class selector are not implemented yet.
- A future real MTC13 invite code should replace `TEST_MTC13`.
- Timetable image URLs currently depend on external image hosting.

## Follow-Up Tasks

- Replace `TEST_MTC13` with a real MTC13 invite code before public launch.
- Keep `TEST_MTC13` disabled unless explicitly needed for controlled testing.
- Make exam countdown class-aware after official exam dates are available.
- Add dashboard support for class selection and class-owned timetable editing.
- Consider moving timetable images to a controlled hosting/storage path.

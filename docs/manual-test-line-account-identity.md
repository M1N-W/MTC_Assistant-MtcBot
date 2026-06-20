# LINE Account Identity Manual Test Checklist

## Scope

Manual test the Phase H LINE account, roster proofing, and class selection flow
for MTC11, MTC12, and MTC13 after fake/local roster dry-runs and reviewed
environment configuration.

## Preconditions

- `STUDENT_ID_PEPPER` is configured in the target environment.
- Real roster seed files are outside the repository or under ignored
  `local-seeds/`.
- Real teacher directory seeds are outside the repository or under ignored
  `local-seeds/`, with reviewed code hashes only.
- `mtc11`, `mtc12`, and `mtc13` registry documents exist with the reviewed
  grade levels.
- MTC11 has reviewed registry, room, active term, and timetable-day data.
- MTC11 timetable image URL is still pending until a reviewed HTTPS URL is
  supplied and manually tested.

## Checklist

- `บัญชี` shows LINE profile data and no raw LINE user ID.
- Invite-joined users can use and select authorized classes while remaining
  visibly unverified.
- `ยืนยันตัวตน` binds only the selected class roster record.
- `ยืนยันตัวตน` for a teacher requires the private verification code after the
  teacher display name.
- Teacher verification creates class-scoped role `teacher` only for assigned
  classes.
- Homeroom teacher display does not grant `class_admin` or `super_admin`.
- A roster record bound to another LINE user fails safely.
- `เลือกห้อง` lists or switches only active memberships.
- MTC11 uses its own timetable-day data and does not fall back to MTC12
  timetable, links, resources, image, or roster.
- MTC11 `ตารางเรียน` returns a class-specific unavailable message while the
  image URL is pending.
- Account Flex contains no raw student ID, `student_key`, roster key, Firestore
  path, teacher ID, verification-code hash, secret, or diagnostic text.

## Not Performed By This Checklist

- No deployment.
- No commit or push.
- No real roster data committed to Git.
- No Dashboard individual authentication.

---

## Operator Checklist: Issue Teacher Verification Code

Run through these steps **offline** (before deployment) to issue a teacher verification code securely.

### Prerequisites

- Firebase service-account credentials available via `FIREBASE_CREDENTIALS_JSON`,
  `FIREBASE_CREDENTIALS_BASE64`, or a key file at the path in `config.FIREBASE_KEY_PATH`.
- Teacher directory record already seeded: `system/teacher_directory/records/{teacher_id}`
  with `"status": "active"`.

### Step 1 — Seed teacher directory (if not already done)

```bash
# Example using seed_teacher_directory
python -m mtc_assistant.seed_teacher_directory --apply
```

- `[ ]` Confirm the record exists and is `"status": "active"` in Firestore.

### Step 2 — Dry-run (no writes, no code generated)

```bash
python -m mtc_assistant.issue_teacher_verification_code \
  --teacher-id <teacher_id>
```

- `[ ]` Output is JSON with `"dry_run": true` and correct `teacher_id`.
- `[ ]` No verification document created in Firestore.
- `[ ]` No plaintext code printed.

### Step 3 — Apply (generate and issue code)

```bash
python -m mtc_assistant.issue_teacher_verification_code \
  --teacher-id <teacher_id> \
  --expires-in-hours 24 \
  --max-attempts 5 \
  --apply
```

- `[ ]` Output includes `SUCCESS` and `Code: <code>`.
- `[ ]` Code is displayed exactly once; the terminal session should be closed after delivery.
- `[ ]` Deliver the code privately to the teacher (e.g., secure message, in-person).
- `[ ]` Firestore document `system/teacher_verification/records/{teacher_id}` exists with
        `"status": "active"`, `"failed_attempts": 0`, and a non-empty `verification_code_hash`.
- `[ ]` The hash does not contain the plaintext code.

### Step 4 — Verify on LINE (teacher)

- `[ ]` Teacher opens LINE, sends `ยืนยันตัวตน`.
- `[ ]` Bot prompts for teacher display name.
- `[ ]` Teacher sends their display name as registered in the directory.
- `[ ]` Bot prompts for verification code.
- `[ ]` Teacher enters the code received in Step 3.
- `[ ]` Bot confirms success; Firestore `users/{uid}` has `"identity_type": "mtc_teacher"`,
        `"verification_status": "verified"`.
- `[ ]` `system/teacher_verification/records/{teacher_id}` is `"status": "used"`.
- `[ ]` A second teacher attempting to reuse the same code is rejected.

### Step 5 — Post-issuance security hygiene

- `[ ]` Terminal history cleared or session closed.
- `[ ]` No code or hash written to any file, note, or chat log.
- `[ ]` To rotate the code, re-run Step 3; old credential is overwritten atomically.


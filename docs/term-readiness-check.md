# Term Readiness Check

Use the read-only CLI before changing a class registry `active_term_id`:

```powershell
$env:PYTHONPATH='src'
python -m mtc_assistant.check_term_readiness --class-id mtc13 --term-id 2569-t2
```

The command reads Firestore and emits one JSON object to stdout. It never
creates, updates, or deletes documents. A completed check exits with code `0`
even when `ready_to_switch` is `false`. Invalid arguments, client
initialization failures, unreadable data, and unexpected exceptions return a
nonzero exit code with the failure in the JSON `errors` array.

`ready_to_switch` is true only when:

- the class registry exists and has grade `m4`, `m5`, or `m6`;
- the target term document exists;
- links config has `school_url`, `grade_url`, and `absence_form_url`;
- timetable config has `image_url` and valid nonempty `days`;
- the target term has at least one active learning resource; and
- the result has no errors.

`worksheet_url` remains optional. Missing active biology or physics
`textbook_solutions` resources produce warnings but do not block readiness.
When an active biology or physics textbook solution exists only for a grade
that differs from the registry grade, the check reports an error because the
runtime grade filter would not serve that resource.

The JSON also reports the registry term, registry grade and status, whether the
target is already active, active resource count, per-config status, warnings,
and errors. A future term can therefore be `ready_to_switch: true` while
`is_active_term` remains false.

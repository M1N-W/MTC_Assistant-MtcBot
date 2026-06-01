# MTC67 Easter Egg Manual Test Record

## Summary

- Test date: 2026-06-02
- Result: passed
- Scope: hidden MTC67 command, Firebase Hosting video asset delivery, Render env vars, LINE VideoMessage response, negative exact-match checks, and regression checks for existing commands.

## Deployment/Commit Context

- `bc4cc16 feat: add mtc67 easter egg command`
- `365fb71 chore: add firebase hosting assets for mtc67`
- Firebase Hosting URL: `https://mtc-assistant-database.web.app`
- Render deployment mode: Manual Deploy
- Render env vars required:
  - `MTC67_VIDEO_URL`
  - `MTC67_PREVIEW_IMAGE_URL`

## Asset Verification

- `/assets/easter-eggs/mtc67.mp4` opened successfully from Firebase Hosting.
- `/assets/easter-eggs/mtc67-preview.jpg` opened successfully from Firebase Hosting.

## Behavior Verified

### Positive Cases

- `67` returns the MTC67 video message.
- `mtc67` returns the MTC67 video message.
- `MTC67` returns the MTC67 video message.

### Negative Cases

- `abc67` does not trigger the video.
- `mtc678` does not trigger the video.
- `67 test` does not trigger the video.
- `วันนี้ 67 มาก` does not trigger the video.

## Regression Checks

- `ชีวะ` passed.
- `ฟิสิกส์` passed.
- `ลิงก์` passed.
- `งาน` passed.
- `เว็บโรงเรียน` passed.
- `เกรด` passed.
- `ลา` passed.

## Expected Design / Product Notes

- MTC67 is an easter egg and should stay hidden.
- It should not be listed in help text.
- It should not be added to Flex menu or Rich Menu.
- It should not affect learning resources, general links, or MTC12 legacy solution behavior.
- It intentionally uses exact-match command routing to avoid accidental triggers.

## Known Limitations

- The feature depends on Firebase Hosting asset availability.
- The feature depends on Render env vars being configured correctly.
- If env vars are missing, the bot should return a friendly unavailable text instead of crashing.
- The video file is currently committed as a static Firebase Hosting asset.
- If asset size grows significantly in future, reconsider whether repo-hosted Firebase Hosting assets are still appropriate.

## Next Project Roadmap Snapshot

### Learning Resources Completion

- Add an explicit dry-run-first way to seed or manage learning resources.
- Avoid production URL mistakes.
- Keep resources class/term-scoped under `classes/{classId}/terms/{termId}/resources/{resourceId}`.
- Do not allow silent fallback from MTC13+ to MTC12 subject resources.

### MTC13 Production Data

- Add real MTC13 learning resources only when URLs and ownership are verified.
- Test `ชีวะ` and `ฟิสิกส์` happy paths after resources exist.
- Keep MTC12 legacy behavior stable.

### UX Cleanup Later

- Do not redesign Flex/Rich Menu before data layer and resource behavior are stable.
- Eventually separate general links from learning resources.
- Keep MTC Assistant mascot/personality as part of the product identity.

### Dashboard/Admin Self-Service

- Future goal is to let trusted class admins update class data without Mawin deploying code.
- Dashboard work must respect auth, class scope, and proxy boundaries.
- Do not let browser-side code receive dashboard API tokens.

### Reliability and Operations

- Keep Render Manual Deploy as the current release control.
- Continue using manual test docs after user-facing changes.
- Keep secrets in environment variables, not repo.
- Use tests and small commits before production release.

## Follow-up Tasks

- No immediate follow-up required for MTC67 if manual test remains passed.
- Next likely engineering phase: learning resources seed/config workflow.
- Later phase: dashboard editor for class/term resources.
- Later phase: Flex/Rich Menu information architecture cleanup after resource data exists.
- If the video asset changes later, update Firebase Hosting assets and redeploy hosting.
- If Render env vars change, redeploy the bot manually.

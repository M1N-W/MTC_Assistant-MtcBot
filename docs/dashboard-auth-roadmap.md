# Dashboard Auth and Admin Roadmap

## Purpose

This roadmap locks the dashboard and admin authentication direction before implementation. The goal is to let future class admins maintain ordinary class data without requiring Mawin to deploy code for every timetable, link, resource, or class configuration change.

The dashboard must stay aligned with the current MTC Assistant architecture: LINE remains the main student interface, the dashboard remains a separate Next.js service, and Flask remains the bot/admin API service. Auth work must protect the existing server-side proxy boundary and preserve class-aware behavior for MTC13, MTC14, and later generations.

## Naming Model

- Admin Dashboard: the super-admin workspace for Mawin and any future explicitly trusted super admins.
- MTC13 Dashboard: the class-scoped workspace for MTC13 class admins.
- MTC14 Dashboard: the class-scoped workspace for MTC14 class admins.
- MTC[x] Dashboard: the generic name for any future class dashboard, where `x` is the MTC generation.
- Dashboard portal: the first signed-in screen where a user chooses the Admin Dashboard or one of the MTC[x] Dashboards they are allowed to access.

This is one web app, one codebase, and one deploy. The app splits access by route, role, and permission. Do not create multiple dashboard websites or separate dashboard codebases unless a future architecture decision explicitly changes this.

The existing MTC Dashboard becomes the Admin Dashboard. Class dashboards should use names like MTC13 Dashboard or MTC14 Dashboard so future maintainers understand which class workspace they are editing.

## Role Model

- `super_admin`: can manage all classes, global system settings, class admin accounts, and high-risk operations. Mawin is the current super admin.
- `class_admin`: can manage only assigned class data, such as links, learning resources, timetable, exams, and class-scoped operational content.
- `student` or `user`: can use LINE features and may have a bound class identity, but does not receive dashboard edit access by default.
- `tester` or `reporter`: optional future role for read-only checks or issue reporting if manual test and support flows need it.

Multiple class admins per class are allowed. Role and class scope must be enforced server-side for every class-scoped request. Frontend visibility is only UX; hidden buttons are not security.

## Route Model

Preferred routes:

- `/dashboard` or `/dashboard/portal`: signed-in dashboard portal.
- `/admin` or `/admin/super`: Admin Dashboard for super admins.
- `/dashboard/classes/{classId}`: MTC[x] Dashboard for class admins and super admins with access to that class.

Prefer `/dashboard/classes/{classId}` over bare `/classes/{classId}` because it keeps dashboard routes separate from future public or student-facing pages.

Route protection should happen before rendering protected dashboard content. The Next.js layer should check the signed-in session and allowed dashboard targets. Flask admin APIs must still validate role and class scope on every request because frontend route protection is not sufficient.

## Authentication Model

Super admin login should use stronger controls than normal class admin login. At minimum, it needs a unique account, strong password, rate limiting, session expiry, audit logging, and a recovery path that class admins cannot control.

Class admin login should support trusted maintainers for each class. Custom password auth is the likely first implementation because it can fit the current Next.js dashboard and Flask admin API boundary without forcing a new provider decision. OAuth or Google sign-in remains an open future option.

Session requirements:

- Store sessions server-side or sign/encrypt them with a strong `DASHBOARD_SESSION_SECRET`.
- Use secure, httpOnly, sameSite cookies where applicable.
- Expire sessions after a bounded duration.
- Invalidate old sessions after password reset, role removal, or class access removal.
- Do not store plaintext passwords.
- Store only password hashes using a modern password hashing algorithm.
- Track failed login attempts and rate limit by account and source.
- Return safe error messages that do not reveal whether a username, class admin account, or super admin account exists.

Password rules should require a minimum length, block known weak passwords where practical, and allow rotation without exposing old hashes or reset codes.

## Student / LINE Onboarding Identity Proofing

Student identity proofing is for binding a LINE user to a class roster record. It is not the same as dashboard authentication.

Suggested flow:

- User chooses a class such as MTC13 or MTC14.
- User submits roster proofing fields such as name, surname, class number, or student ID.
- Backend compares the submitted fields with class-scoped roster data.
- On a match, backend binds the LINE user ID to the roster record and class user document.
- On a mismatch, the user receives a safe path to contact a class admin or super admin.

Student ID is not a password. It is only proofing material. Do not force every student to set a password unless a later product need requires student web login.

Store only the minimum necessary identity data. Keep LINE user IDs internal and avoid exposing them unnecessarily in dashboard tables, exports, or logs.

## Forgot Password / Recovery Model

Student user recovery:

- Prefer LINE-based re-verification or class admin assistance if a student loses access to a bound identity.
- Use roster proofing again where appropriate.
- Do not use security questions.
- Rate limit reset attempts and record audit events.

Class admin recovery:

- Class admin submits a reset request.
- Super admin, or a properly authorized recovery policy, approves the reset.
- The system issues a one-time reset code or link with a short expiry.
- After reset, old sessions are invalidated.
- Reset events are recorded in audit logs.

Super admin recovery:

- Do not allow class admins to approve or control super admin recovery.
- Use a separate high-trust recovery path, such as a preconfigured emergency admin, environment-controlled reset process, or external identity provider if adopted later.
- Issue only one-time reset codes or links with expiry.
- Invalidate old sessions after reset.
- Rate limit attempts and audit every recovery action.

No recovery flow should use security questions or plaintext temporary passwords.

## Data Model High-Level

Recommended Firestore shape:

- `/classes/{classId}/roster/{studentKey}`
- `/classes/{classId}/users/{userId}`
- `/classes/{classId}/admin_accounts/{accountId}`
- `/system/super_admins/{adminId}`
- `/system/audit_logs/{logId}`
- `/system/password_reset_requests/{requestId}`

Roster documents should store only the data needed for identity proofing and class operations. Use `student_id_hash` or HMAC instead of raw student ID where practical. Store `SERVER_SECRET_PEPPER` in environment variables, not in the repo.

Do not commit real roster CSVs, real student data, real accounts, secrets, tokens, or production credentials. Use fake examples only. Keep LINE user IDs internal and avoid exposing them unnecessarily to class admins unless the workflow requires it.

General links remain class/term-scoped under:

- `/classes/{classId}/terms/{termId}/config/links`

Learning resources remain class/term-scoped under:

- `/classes/{classId}/terms/{termId}/resources/{resourceId}`

MTC13+ must never silently fall back to MTC12 subject-specific resources. If a class should reuse an older resource, it must be explicitly configured for that class and term.

## API and Permission Boundaries

Current boundary:

- Browser
- Next.js dashboard
- Next.js server-side `/api/admin/*` proxy
- Flask `/api/admin/*` Blueprint
- Firestore, Gemini, bot metrics, and LINE push APIs

The browser must never receive `MTC_DASHBOARD_API_TOKEN`. The browser authenticates to Next.js. The Next.js server-side proxy calls the Flask admin API with server-only credentials.

Backend permission rules:

- Validate `class_id` and role on every request.
- Do not trust client-provided `class_id` without checking permissions.
- Normal class admins cannot read or write another class.
- Super admins can manage all classes.
- Do not rely on frontend-only security.
- Return structured errors consistently.
- Paginate collection reads.
- Avoid unbounded Firestore streams for dashboard cards.
- Use bounded queries or counter documents for count-like dashboard metrics.

The LINE webhook must stay independent from dashboard failures.

## UX Design Direction

Use the existing dashboard design, layout, components, and stack as much as possible. Do not start with a full dashboard redesign.

Admin Dashboard can be more operations-focused. It should prioritize monitoring, admin management, release checks, class setup, and risk-sensitive actions.

MTC[x] Dashboard should be simpler, task-focused, and handoff-friendly. It should show only what the signed-in user can edit. It should avoid overwhelming class admins with global settings or unrelated operational tools.

The recommended visual direction is Classroom OS from `CONTEXT.md`: clean, modular, long-lived, and suitable for class admin handoff, timetable editing, config management, and multi-generation support. Keep MTC Assistant identity and mascot where appropriate, but do not let branding obscure maintenance tasks.

## Phased Implementation Plan

Phase A: docs-only roadmap.

- Create this document.
- Do not implement dashboard auth yet.
- Do not modify backend, dashboard, deployment, or environment config.

Phase B: read-only dashboard portal.

- Add a protected portal shell.
- Show only allowed dashboard destinations.
- Keep backend writes out of scope.

Phase C: class admin auth foundation.

- Add account model, password hashing, sessions, rate limiting, role checks, and class-scope checks.
- Add backend permission tests before release.
- Keep the browser-side dashboard token boundary intact.

Phase D: links editor.

- Edit class/term general links under `/classes/{classId}/terms/{termId}/config/links`.
- Keep subject-specific resources out of general links.

Phase E: learning resources editor.

- Manage class/term-scoped resources under `/classes/{classId}/terms/{termId}/resources/{resourceId}`.
- Support `textbook_solutions` and `assignment_resources` without MTC13+ falling back to MTC12 subject resources.

Phase F: timetable/exams editor.

- Let authorized class admins update timetable and exam config for their own class.
- Keep changes dry-run-friendly and reversible.

Phase G: LINE onboarding upgrade.

- Add roster-based identity proofing.
- Bind LINE user IDs to class-scoped user records.
- Keep student ID as proofing material, not a password.

After Phase A, do not immediately implement dashboard auth unless Mawin explicitly requests it. The next likely engineering sequence remains the learning resources seed/config workflow:

- Dry-run-first resource seed/config.
- Avoid production URL mistakes.
- Class/term-scoped resource docs.
- Test `ชีวะ` and `ฟิสิกส์` happy paths after real resources exist.

## Non-Goals for the First Implementation

- No full dashboard rewrite.
- No separate dashboard codebase.
- No production roster upload through ChatGPT.
- No plaintext passwords.
- No cross-class admin access.
- No browser-side dashboard token exposure.
- No deployment changes.
- No Render deploy.
- No backend implementation.
- No dashboard UI implementation.
- No changes to MTC67 help text, Flex menu, Rich Menu, dashboard UI, or normal user-facing docs.

## Security Checklist

- Password hashing.
- Rate limiting.
- Failed login tracking.
- Session expiry.
- Secure cookies where applicable.
- httpOnly cookies where applicable.
- sameSite cookies where applicable.
- Server-side role checks.
- Server-side class scope checks.
- Audit logs for admin changes.
- Safe reset flow.
- Secrets stored in environment variables.
- No real roster data in the repo.
- No raw student ID when hash or HMAC is practical.
- Manual test docs after user-facing or admin-facing changes.
- Backend permission tests before release.

## Open Questions

- Exact auth provider: custom password first, or future OAuth/Google?
- How are class admins appointed and removed?
- Should student LINE onboarding require only roster verification, or should any student web password exist later?
- How should the system handle students who transfer rooms?
- How should admin roles rotate each generation?
- Are parent or teacher roles needed later?
- Where should audit logs live for the right balance of cost, privacy, and retention?

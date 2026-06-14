# Dashboard Auth and Admin Roadmap

## Purpose

This roadmap supports the June 20, 2026 MTC OS v1 Foundation Release. The
foundation requires individual `super_admin`, `class_admin`, and `teacher`
accounts with Flask-owned authentication, sessions, and authorization.
The backend role model also includes `student` for the required later Student
Portal. This phase does not implement that portal UI.

The dashboard must stay aligned with the current MTC Assistant architecture: LINE remains the main student interface, the dashboard remains a separate Next.js service, and Flask remains the bot/admin API service. Auth work must protect the existing server-side proxy boundary and preserve class-aware behavior for MTC12, MTC13, and later generations.

## Naming Model

- Admin Dashboard: the super-admin workspace for Mawin and any future explicitly trusted super admins.
- MTC12 Dashboard: the class-scoped workspace for MTC12 class admins.
- MTC13 Dashboard: the class-scoped workspace for MTC13 class admins.
- MTC[x] Dashboard: the generic name for any future class dashboard, where `x` is the MTC generation.
- Dashboard portal: the first signed-in screen where a user chooses the Admin Dashboard or one of the MTC[x] Dashboards they are allowed to access.

This is one web app, one codebase, and one deploy. The app splits access by route, role, and permission. Do not create multiple dashboard websites or separate dashboard codebases unless a future architecture decision explicitly changes this.

The existing MTC Dashboard becomes the Admin Dashboard. Current class
workspaces should use names such as MTC12 Dashboard and MTC13 Dashboard.
Future classes use the generic MTC[x] pattern.

## Role Model

- `super_admin`: can manage all classes, global system settings, class admin accounts, and high-risk operations. Mawin is the current super admin.
- `class_admin`: belongs to exactly one class in MTC OS v1. One class may have
  multiple class admins. Long-term MTC OS v1 capabilities include ordinary
  management of links, learning resources, timetable, homework, exams,
  announcements, and other content for that assigned class.
- `teacher`: belongs to one or more explicitly assigned classes. One class may
  have multiple teachers.
- `student` or `user`: can use LINE features and may have a bound class identity, but does not receive dashboard edit access by default.
- `tester` or `reporter`: optional future role for read-only checks or issue reporting if manual test and support flows need it.

Only `super_admin` may appoint, remove, disable, recover, or change assignments
for class admins and teachers. Role, capability, and class scope must be
enforced by Flask for every protected request. Frontend visibility is only UX;
hidden buttons are not security.

Each class-admin write capability becomes active only when its module, backend
authorization, and permission tests exist. Account administration, term
lifecycle, global settings, and class BYOK remain `super_admin`-only unless a
later explicit decision changes them.

## Route Model

Preferred routes:

- `/dashboard` or `/dashboard/portal`: signed-in dashboard portal.
- `/admin` or `/admin/super`: Admin Dashboard for super admins.
- `/dashboard/classes/{classId}`: MTC[x] Dashboard for class admins and super admins with access to that class.

Prefer `/dashboard/classes/{classId}` over bare `/classes/{classId}` because it keeps dashboard routes separate from future public or student-facing pages.

Route protection should happen before rendering protected dashboard content. The Next.js layer should check the signed-in session and allowed dashboard targets. Flask admin APIs must still validate role and class scope on every request because frontend route protection is not sufficient.

## Authentication and Authority Model

Flask is the authority for account records, password verification, account
status, identity bindings, roles, assignments, sessions, recovery,
authorization, and audit logs. Next.js remains the browser-facing UI and BFF.
It may store and forward an opaque Flask-issued session in a secure HttpOnly
cookie but must not derive identity or permissions from it.

`MTC_DASHBOARD_API_TOKEN` authenticates the Next.js service to Flask only. It
is not a user login token or principal. The browser must never receive it.

Individual username/password login is required by June 20. Google login is a
later authentication method mapped by Flask to a pre-approved local account;
it must not auto-register arbitrary accounts.

Session requirements:

- Use opaque random Flask-issued session tokens.
- Store only secure hashes of session tokens in the backend session store.
- Use secure, httpOnly, sameSite cookies where applicable.
- Expire sessions after a bounded duration. A 12-hour absolute lifetime is the
  foundation recommendation.
- Invalidate old sessions after password reset, role removal, or class access removal.
- Do not store plaintext passwords.
- Store only password hashes using a modern password hashing algorithm.
- Track failed login attempts and rate limit by account and source.
- Return safe error messages that do not reveal whether a username, class admin account, or super admin account exists.

Password rules should require a minimum length, block known weak passwords where practical, and allow rotation without exposing old hashes or reset codes.

## Student / LINE Onboarding Identity Proofing

Student identity proofing is for binding a LINE user to a class roster record. It is not the same as dashboard authentication.

Suggested flow:

- User chooses a class such as MTC12 or MTC13.
- User submits roster proofing fields such as name, surname, class number, or student ID.
- Backend compares the submitted fields with class-scoped roster data.
- On a match, backend binds the LINE user ID to the roster record and class user document.
- On a mismatch, the user receives a safe path to contact a class admin or super admin.

Student ID is not a password. It is only proofing material. Do not force every student to set a password unless a later product need requires student web login.

Store only the minimum necessary identity data. Student and public interfaces
must never expose LINE user IDs. Super admins may view full IDs across all
classes; class admins may view full IDs only for their one assigned class; and
teachers may view full IDs only for explicitly assigned classes. List views
may mask IDs by default with an authorized details/reveal interaction. Bulk
export is not automatically allowed.

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
- `/system/dashboard_accounts/{accountId}`
- `/system/dashboard_sessions/{sessionId}`
- `/system/audit_logs/{logId}`
- `/system/password_reset_requests/{requestId}`

Roster documents should store only the data needed for identity proofing and class operations. Use `student_id_hash` or HMAC instead of raw student ID where practical. Store `SERVER_SECRET_PEPPER` in environment variables, not in the repo.

Do not commit real roster CSVs, real student data, real accounts, secrets,
tokens, or production credentials. Use fake examples only. Every full LINE
user ID read must be authorized server-side against the current role and class
scope.

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

The browser authenticates through Next.js, which forwards credentials to
Flask. Flask verifies the account and issues the opaque session. The Next.js
server-side proxy sends both the server-only service credential and the user
session to Flask.

Backend permission rules:

- Validate `class_id` and role on every request.
- Validate an operation-specific capability on every protected request.
- Do not trust client-provided `class_id` without checking permissions.
- Class admins cannot access outside their one assigned class.
- Teachers cannot access outside their explicit class assignments.
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

Thai is the primary language for normal Dashboard navigation, headings, forms,
buttons, confirmations, empty states, and errors. The teacher-first policy
means task-first language understandable to non-technical teachers, class
admins, and future student maintainers. English remains for product names and
familiar technical names such as MTC Assistant, MTC Dashboard, Classroom OS,
LINE, AI, URL, Google, and Gemini. Hide `class_id`, `term_id`, BYOK,
credentials, API tokens, and audit schemas from normal UX; show them only in
advanced or system contexts when necessary.

Section navigation should use stable URL hashes without another routing
framework: `#overview`, `#members`, `#homework`, `#announcements`,
`#resources`, `#system`, and `#ai-settings`. Read the hash only after the
client mounts, synchronize on `hashchange`, preserve Back/Forward behavior,
avoid duplicate same-section entries, and replace invalid or unauthorized
hashes with the first allowed section. Hashes are UX state, not authorization.
Use `aria-current="page"` and do not leave hidden sections focusable.

## Phased Implementation Plan

Phase A: docs-only roadmap.

- Create this document.
- Do not implement dashboard auth yet.
- Do not modify backend, dashboard, deployment, or environment config.

Phase B: Flask auth and authorization foundation.

- Add account, password hashing, role, assignment, session, recovery, audit,
  and current-principal models/endpoints.
- Add authorization middleware and positive/negative permission tests.
- Preserve the current production login only during migration.
- Foundation implementation adds `/api/admin/auth/login`, `/auth/me`, and
  `/auth/logout` behind separate service and human-session trust layers.
- Only self-session capabilities and tested super-admin account-management
  service capabilities are active at this stage. Existing class operations
  remain on the transitional principal path until a later migration.
- Additive Firestore records use hashed username reservations and hashed
  opaque-session lookup keys. No production account is created automatically.

Phase C: Next.js session migration.

- Proxy credentials to Flask and store only the Flask-issued opaque session.
- Add role-aware navigation and a safe Flask-owned `/api/admin/auth/me`.
- Migrate Mawin to the first `super_admin` account.
- Add CSRF protection at the Next.js mutation boundary; Flask does not set a
  browser-facing cookie in Phase B.

Phase D: role and class-scope production verification.

- Create controlled class-admin and teacher accounts.
- Verify single-class class-admin and explicit multi-class teacher assignments.
- Add super-admin appointment, removal, reassignment, and recovery workflows.
- Remove the shared password as the normal production login authority after
  verification.

The full Web Platform Definition of Done includes the later Student Portal as
a required milestone alongside teacher, class-admin, and super-admin
workspaces. It is not represented as complete by the backend foundation.

Phase E: links editor.

- Edit class/term general links under `/classes/{classId}/terms/{termId}/config/links`.
- Keep subject-specific resources out of general links.

Phase F: learning resources editor.

- Manage class/term-scoped resources under `/classes/{classId}/terms/{termId}/resources/{resourceId}`.
- Support `textbook_solutions` and `assignment_resources` without MTC13+ falling back to MTC12 subject resources.

Phase G: timetable/exams editor.

- Let authorized class admins update timetable and exam config for their own class.
- Keep changes dry-run-friendly and reversible.

Phase H: LINE onboarding upgrade.

- Add roster-based identity proofing.
- Bind LINE user IDs to class-scoped user records.
- Keep student ID as proofing material, not a password.

Dashboard auth is part of the June 20 foundation. Later editor modules remain
separate work and must not be represented as implemented before their APIs and
permission tests exist.

## Non-Goals for the First Implementation

- No full dashboard rewrite.
- No separate dashboard codebase.
- No production roster upload through ChatGPT.
- No plaintext passwords.
- No cross-class admin access.
- No browser-side dashboard token exposure.
- No deployment changes.
- No Render deploy.
- No Google login requirement for June 20.
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

- Which class-admin write modules are required for the June 20 Foundation
  Release versus later MTC OS v1 work?
- Should student LINE onboarding require only roster verification, or should any student web password exist later?
- How should the system handle students who transfer rooms?
- How should admin roles rotate each generation?
- Where should audit logs live for the right balance of cost, privacy, and retention?
- What retention periods should apply to sessions and audit logs?
- What emergency recovery path should be used for the super admin?

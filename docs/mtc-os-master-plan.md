# MTC OS Master Plan

## Authority

This is the canonical roadmap for the evolution of MTC Assistant into MTC OS.
It does not govern MTC the Game or Math Talent. The AI Architecture Rework is a
subsystem plan within MTC Assistant/MTC OS, not a separate system-level roadmap.

## Current Production State

The AI/BYOK production release was deployed and verified at `main` commit
`410552c`. Its recorded checks are in
[manual-test-ai-byok-production.md](manual-test-ai-byok-production.md).

Current architecture:

- LINE is the main student interface.
- Flask is the runtime and policy boundary.
- Firestore is the classroom data store.
- Next.js Dashboard is the admin command center and browser-facing BFF.
- The browser never receives `MTC_DASHBOARD_API_TOKEN`.
- AI is invoked intentionally and must not become an uncontrolled fallback.

Do not infer that roadmap items below already exist.

## June 20, 2026 Production Foundation

June 20, 2026 is a production deployment deadline. The required release is the
**MTC OS v1 Foundation Release**, not a demo or release candidate.

### Required Scope

1. MTC12 and MTC13 class/term foundation.
2. Term Operations:
   - Copy Term Config.
   - Term Readiness validation.
   - Active Term Switch.
   - Previous-term history and rollback procedure.
3. Dashboard authentication and authorization:
   - individual username/password accounts;
   - backend role support for `student`, `teacher`, `class_admin`, and
     `super_admin`;
   - secure Flask-owned sessions;
   - server-side role and capability checks;
   - server-side class-scope enforcement.
4. Super-admin workflows to appoint, remove, disable, recover, and reassign
   `class_admin` and `teacher` accounts.
5. Migration of existing Dashboard/admin APIs to the authenticated principal
   and permission model.
6. Stability of existing production functionality.
7. Production deployment, health checks, smoke tests, rollback notes, and
   point-in-time manual-test evidence.

### Role and Assignment Rules

- `super_admin` has global access and does not depend on class assignments.
  Mawin is currently the super admin.
- `class_admin` belongs to exactly one class in MTC OS v1. A class may have
  multiple class admins.
- `teacher` belongs to one or more explicitly assigned classes. A class may
  have multiple teachers.
- Only `super_admin` may appoint, remove, disable, recover, or change the
  assignment of class admins and teachers.
- Flask validates every requested class against the current principal.
- Users never choose a role manually.

An account with one accessible class opens that workspace directly. A
multi-class teacher receives a simple human-facing class switcher. Raw
`class_id` values and technical permission claims are not normal UI language.

### Authentication Authority

Flask owns dashboard accounts, password hashes, account status, identity
bindings, roles, assignments, sessions, recovery, authorization, and audit
records. Next.js owns the login/dashboard UX, stores a Flask-issued opaque
session in a secure HttpOnly cookie, and forwards requests as the
browser-facing BFF.

Two trust layers remain separate:

1. `MTC_DASHBOARD_API_TOKEN` authenticates the Next.js service to Flask. It is
   server-only and does not identify or authorize a person.
2. A separate opaque Flask-issued session identifies the signed-in person.

Protected requests require valid service authentication, a valid non-revoked
session, an active account, sufficient capability, valid class scope, and
CSRF/origin protection for mutations.

Session tokens are random and opaque. Store only secure hashes in the backend
session store. Role or assignment changes, password reset, account disable,
sign-out, forced sign-out, and security recovery revoke affected sessions.

Recommendation: use a bounded 12-hour absolute session lifetime for the
foundation release and require login again after expiry. Refresh tokens and a
configurable idle timeout remain later decisions.

The current shared `DASHBOARD_PASSWORD`, Next.js-signed cookie, and static
dashboard-principal environment values are transitional. Do not retain two
independent authentication authorities long-term. Keep
`MTC_DASHBOARD_API_TOKEN` only for service authentication.

Google login is a later authentication method mapped to a pre-approved local
Flask account. It is not required by June 20 and must never auto-register an
arbitrary Google account.

The backend-first auth foundation establishes additive account, username
reservation, opaque session, login throttle, and security-audit storage under
`/system`. It does not migrate the Next.js login, create production accounts,
or authorize existing global admin endpoints for teachers or class admins.
Those operations remain on the shared-password compatibility path until the
Next.js session and Admin API principal migrations are verified.

The foundation session lifetime is 12 hours. Session documents carry
`purge_after` metadata for 30 days after expiry, and security audit records
carry `retain_until` metadata for 365 days. Automated TTL cleanup is not part
of the foundation milestone.

The complete Web Platform still requires the Student Portal and the teacher,
class-admin, and super-admin workspaces. The Student Portal is a required later
milestone, not an optional idea, and is not implemented by this backend-only
foundation.

### Teacher Baseline

By June 20 a teacher may:

- sign in with an individual account;
- access only explicitly assigned classes;
- view existing assigned-class operational data;
- view full LINE user IDs for members of explicitly assigned classes;
- read assigned-class homework;
- use existing safe class-scoped homework writes when the endpoint and
  permission tests exist;
- create class-wide broadcasts for an assigned class;
- view assigned-class broadcast history and delivery results; and
- view safe summaries from existing timetable, links, resources, and health
  endpoints.

Teacher broadcasts require a visible class label, recipient count, message
preview, explicit confirmation, class-scoped recipient resolution, audit
record, and delivery result. Flask rechecks the assignment on every request.

Teachers cannot manage accounts, roles, assignments, term lifecycle, global
settings, system-wide broadcasts, class BYOK, AI credentials, raw AI
conversations, deployment settings, or system-wide audit logs.

LINE identity access remains server-side and class-scoped:

- `super_admin` may view full LINE user IDs across all classes.
- `class_admin` may view full LINE user IDs only for the one assigned class.
- `teacher` may view full LINE user IDs only for explicitly assigned classes.
- Student and public interfaces never expose LINE user IDs.
- List views may mask IDs by default and provide an authorized details/reveal
  interaction.
- Bulk export is not automatically allowed and requires a separate capability.

Raw AI prompt and response access remains `super_admin`-only. It is a separate
AI audit permission and does not restrict authorized class-scoped LINE
identity access.

### Capability Model

Roles provide default capabilities, while Flask authorizes each implemented
operation. Initial examples include:

- `members.read_for_assigned_class`
- `homework.read`
- `homework.create`
- `homework.update`
- `broadcast.create_for_assigned_class`
- `broadcast.read_for_assigned_class`

Future capabilities such as `exams.manage`, `resources.manage`,
`timetable.manage`, and `reminders.manage` must not authorize anything until
their modules and permission tests exist.

### Term Operations Ownership

Copying term configuration, readiness override, active-term switching,
rollback, and global class configuration are `super_admin`-only for the
foundation release.

The switch procedure must:

1. identify the source, target class, and target term;
2. copy only approved configuration with a preview;
3. run readiness validation;
4. record the previous active term;
5. require explicit confirmation;
6. change the active term atomically or with a recoverable sequence;
7. record the actor, timestamp, before/after values, and result; and
8. provide a documented rollback to the previous term.

MTC12 and MTC13 student counts are operational context, not business rules.
Do not hardcode `33` or `36` as authorization, readiness, or recipient limits.

## Later MTC OS v1 Work

The following remain MTC OS v1 work after the foundation:

- Learning Resources management and safe class-admin/teacher workflows.
- Timetable and Links self-service.
- Homework maturity, including duplicate protection, undo, edit history, and
  soft-hide.
- Exam Calendar editing.
- Configurable event reminders and saved named groups.
- Mature teacher workflows for exams, resources, timetable, announcements, and
  reminders.
- Reliability and operations improvements beyond the release gate.
- AI Classroom Context reading timetable, homework, exams, and announcements.
- MTC Enviroment link-first integration.

Student todo/doing/done homework completion state is not required for the
foundation.

## Post-v1

- AI memory.
- Personal BYOK.
- Advanced cross-product identity or progress integration.
- MTC Cipher progress synchronization.
- Separate staging infrastructure.

## Locked Product Decisions

- Bound students, teachers, and class admins may add homework directly in v1.
- Homework and exam events do not require an approval step in v1.
- There is no user-facing homework submission quota in v1.
- Duplicate protection, undo, edit history, and soft-hide are preferred
  homework safeguards.
- Teachers may send assigned-class broadcasts; the default audience is the
  whole class.
- Saved named groups are the preferred secondary audience later.
- Reminder timing is configurable per event when the reminder module exists.
- Gemini is the default AI provider; provider and model may vary by class.
- The system fallback budget is global.
- Raw AI prompts and responses may be stored for audit.
- Raw AI conversation access is `super_admin`-only.
- No final AI-retention period is locked.

## UX-First Principles

Students, teachers, and class admins should not need to understand
`class_id`, `term_id`, Firestore paths, credentials, BYOK, idempotency, cron
expressions, dry-run mechanics, audit schemas, or API tokens.

- Thai is the primary language for normal Dashboard navigation, headings,
  forms, buttons, confirmations, empty states, and errors.
- The teacher-first policy means task-first language that non-technical
  teachers, class admins, and future student maintainers can understand.
- English remains for product names and familiar technical names such as
  MTC Assistant, MTC Dashboard, Classroom OS, LINE, AI, URL, Google, and
  Gemini.
- Technical terms such as `class_id`, `term_id`, BYOK, credentials, API
  tokens, and audit schemas appear only in advanced or system contexts when
  necessary.
- Use human-facing class and term labels.
- Use safe defaults and explicit previews for risky actions.
- Open a single allowed workspace directly.
- Never use frontend hiding as authorization.
- Do not display unsupported features as though they work.

Dashboard section navigation uses lightweight URL hashes:

- `#overview`: ภาพรวม
- `#members`: สมาชิก
- `#homework`: การบ้าน
- `#announcements`: ประกาศ
- `#resources`: ลิงก์และสื่อ
- `#system`: ระบบ
- `#ai-settings`: การตั้งค่า AI

Hashes preserve refresh and browser history but remain UX state only.
Unsupported, invalid, or unauthorized hashes fall back to the first allowed
section. Invalid hashes should be replaced with `#overview` without adding a
history entry. Same-section clicks must not create duplicate entries. The UI
listens for `hashchange`, uses `aria-current="page"` for the active item, and
does not render hidden sections as focusable content. No additional routing
framework is required.

## Domain Boundaries and Invariants

- Worksheet links, persisted homework, and learning resources remain separate
  domains.
- MTC13+ never silently falls back to MTC12 subject resources.
- MTC67 remains hidden and exact-match only.
- MTC67 must not appear in help, Flex, Rich Menu, Dashboard, or public feature
  lists.
- Flask remains the final policy boundary.
- Frontend visibility is not authorization.
- AI remains intentionally invoked.

## Dependency Order

1. Preserve the verified AI/BYOK production baseline and document rollback.
2. Finalize class/term records for MTC12 and MTC13.
3. Implement Flask account, role, assignment, session, audit, and
   authorization foundations while preserving current login during migration.
4. Protect every existing admin API with service identity and user principal.
5. Change Next.js login to transport Flask credentials/session and add the
   safe current-principal endpoint.
6. Migrate Mawin to the first `super_admin`; create controlled class-admin and
   teacher accounts.
7. Implement Term Operations with preview, readiness gate, history, and
   rollback.
8. Verify role/capability/class-scope behavior and existing production
   regressions.
9. Deploy manually, run health and smoke checks, record evidence, and retire
   the shared-password authority.
10. Continue later MTC OS v1 modules in the order listed above.

## Exit Criteria

The June 20 foundation is complete only when:

- MTC12 and MTC13 resolve the correct class and active term.
- Copy, readiness, switch, history, and rollback procedures are verified.
- Three individual roles can sign in with secure username/password accounts.
- Flask rejects unauthenticated, disabled, insufficient-role, and wrong-class
  requests for every protected API.
- `class_admin` is limited to exactly one assigned class.
- Multi-class teachers can switch only among explicit assignments.
- Only `super_admin` can manage accounts or term lifecycle.
- Full LINE user ID access is enforced by role and class scope, with no student
  or public exposure and no implicit bulk-export permission.
- Broadcast resolution and history are class-scoped.
- Existing production behavior and MTC67 invariants pass regression checks.
- Bot and Dashboard health checks pass after Manual Deploy.
- Rollback notes and point-in-time manual-test evidence are committed without
  secrets or real roster data.

Performance budget: keep LINE webhook behavior independent of Dashboard
failures, avoid unbounded Dashboard reads, and add no new dependency to the
student request path for authentication.

Test threshold: every protected operation requires positive and negative
permission coverage, including wrong-role and wrong-class cases. Release
verification must also cover existing production smoke and regression paths.

Rollback: preserve the previous deployment, previous active-term value, and
transitional login until the replacement path is verified; revert the release
or restore the recorded term/account state without deleting audit history.

## Recommendations

- Keep the session design simple for v1: opaque tokens, bounded lifetime, and
  explicit re-login.
- Use a stable capability registry tied only to implemented endpoints.
- Replace global member and broadcast APIs with class-scoped equivalents before
  granting them to teachers or class admins.
- Keep term lifecycle operations super-admin-only until a later explicit
  decision changes that boundary.
- Long-term MTC OS v1 class-admin capabilities include ordinary management of
  links, learning resources, timetable, homework, exams, announcements, and
  other assigned-class content. Activate each capability only after its
  module, backend authorization, and permission tests exist.
- Account administration, term lifecycle, global settings, and class BYOK
  remain `super_admin`-only unless a later explicit decision changes them.

## Open Questions

- Exact audit-log and session retention periods.
- The emergency super-admin recovery procedure.
- Which class-admin write modules are required for the June 20 Foundation
  Release versus later MTC OS v1 work.
- The final scheduler mechanism for reminders.

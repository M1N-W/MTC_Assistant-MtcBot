# MTC Assistant Context

## Purpose

MTC Assistant is a LINE bot and web dashboard for MTC students at Benjamarachutit Ratchaburi. The project started as a class assistant for MTC12, but the long-term goal is to keep it useful for MTC13 and future generations after Mawin graduates.

This file is written for Codex and other AI coding tools. Treat it as the project context, architecture map, and decision guide before changing code.

## Mission

Build a maintainable, class-aware assistant that helps MTC students manage school life without requiring Mawin to manually deploy every timetable, homework, or class data update.

The system should support:

- MTC12 today.
- MTC13 onboarding next.
- MTC14 and later with minimal code changes.
- Class admins who can maintain their own class data from the dashboard.
- Safe AI features that are useful, age-appropriate, and easy to disable.
- Operational reliability on Render or a future VPS.

## Current System

### Runtime Architecture

```text
LINE user
  -> LINE Messaging API
  -> Flask webhook: /callback
  -> src/mtc_assistant handlers and feature modules
  -> Firestore / Gemini / LINE reply or push APIs

Admin browser
  -> Next.js dashboard under dashboard/
  -> Next.js /api/admin/* server proxy
  -> Flask Blueprint: /api/admin/*
  -> Firestore / Gemini Vision / bot metrics / LINE push APIs
```

The LINE webhook and dashboard are intentionally separated. Dashboard failures must not block `/callback`.

### Backend

- Python 3.11.
- Flask application under `src/mtc_assistant`.
- Gunicorn with `gthread`; do not switch to `gevent` because Firebase gRPC has historically been unsafe with monkey-patched threading.
- LINE Messaging API v3 for webhook replies and push messages.
- Firebase Firestore for persistent data.
- Google Gemini for AI chat, exam simulation, Paperless Capture, and classroom knowledge features.
- In-process caches/sessions still exist for some runtime behavior, so scaling workers needs care.

Key backend modules:

- `main.py`: Flask app, Firebase initialization, LINE/Gemini setup, health and metrics endpoints.
- `handlers.py`: LINE message routing and event handling.
- `command_router.py`: standard user command routing.
- `admin_router.py`: LINE admin command routing.
- `admin_api.py`: token-protected dashboard API mounted at `/api/admin/*`.
- `features.py`: schedule, homework, links, Gemini, and core feature helpers.
- `homework_session.py`: interactive homework session flow.
- `broadcast.py`: user tracking, broadcast, homework reminders, broadcast history.
- `user_blacklist.py`: Firestore-backed blacklist with in-memory cache.
- `paperless_capture.py`: Gemini Vision-based classroom image analysis.
- `classroom_knowledge.py`: lightweight RAG-style classroom document Q&A.

### Dashboard

- Next.js app under `dashboard/`.
- App Router, TypeScript, Tailwind, React Query, TanStack Table, and Recharts.
- The current shared-password login is transitional.
- Target authority: Flask owns dashboard identity, authentication, sessions,
  roles, class assignments, authorization, recovery, and audit records.
- Next.js remains the browser-facing UI and server-side BFF. It stores and
  forwards an opaque Flask-issued session but does not authorize operations.
- Next.js proxies admin requests server-side using `MTC_BOT_API_BASE_URL` and `MTC_DASHBOARD_API_TOKEN`.
- `MTC_DASHBOARD_API_TOKEN` authenticates the proxy service only. It is not a
  user principal.
- The browser must never receive `MTC_DASHBOARD_API_TOKEN`.

### Deployment

Current Render topology from `render.yaml`:

- `mtc-bot`: Python web service for Flask and LINE webhook.
- `mtc-dashboard`: Node web service for the Next.js dashboard.
- `mtc-cleanup`: Python worker placeholder.

Keep this topology as the baseline unless a separate VPS migration is explicitly requested.

## Current Data Model

Current Firestore data is mostly root-level and MTC12-specific:

```text
/users/{userId}
/homeworks/{homeworkId}
/broadcast_history/{broadcastId}
/blacklist/{userId}
/paperless_captures/{captureId}
/meta/stats
```

Current hardcoded class data also exists in `config.py`, including:

- `SCHEDULE`
- `EXAM_DATES`
- class-specific links
- timetable image URL
- expected class size default

This is the main architecture limit. MTC13 and future classes should not require code edits or redeploys for ordinary class data.

## Target Architecture

### Multi-Tenant Class Context

Every user and admin operation should resolve a `class_id` before reading or writing class-owned data.

Canonical class IDs:

```text
mtc12
mtc13
mtc14
```

Rules:

- `class_id` is required for class-owned data.
- A LINE user belongs to one active class by default.
- Super admins can access all classes.
- Class admins belong to exactly one assigned class in MTC OS v1.
- Teachers belong to one or more explicitly assigned classes.
- Only super admins appoint, remove, or change class-admin and teacher
  assignments.
- Shared system configuration lives under `/system`.
- Class-specific configuration lives under `/classes/{classId}`.
- New classes should be onboarded through Firestore/dashboard configuration, not code edits.

### Target Firestore Schema

```text
/system/class_registry
  classes: [
    {
      id: "mtc12",
      display_name: "MTC12",
      school_year_label: "ม.5/2",
      status: "active" | "archived",
      created_at: timestamp
    }
  ]

/system/feature_flags
  feedback_enabled: true
  game_link_enabled: true
  lookmaxxing_enabled: false
  confession_enabled: false
  study_buddy_enabled: false

/classes/{classId}/metadata
  display_name: string
  generation: number
  status: "active" | "archived"
  default_timezone: "Asia/Bangkok"
  owner_admin_ids: string[]
  class_admin_ids: string[]
  created_at: timestamp
  updated_at: timestamp

/classes/{classId}/config/timetable
  days: map
  updated_by: string
  updated_at: timestamp

/classes/{classId}/config/links
  worksheet_url: string
  school_url: string
  timetable_image_url: string
  grade_url: string
  absence_form_url: string
  mtc_game_url: string
  updated_by: string
  updated_at: timestamp

/classes/{classId}/config/teachers
  teachers: map
  updated_by: string
  updated_at: timestamp

/classes/{classId}/config/exams
  exam_windows: map
  updated_by: string
  updated_at: timestamp

/classes/{classId}/users/{userId}
  user_id: string
  display_name: string | null
  role: "student" | "teacher" | "class_admin" | "super_admin"
  status: "active" | "inactive" | "banned"
  joined_at: timestamp
  last_seen_at: timestamp

/classes/{classId}/homeworks/{homeworkId}
  subject: string
  detail: string
  due_date: string
  created_by: string
  created_at: timestamp
  updated_at: timestamp

/classes/{classId}/feedback/{feedbackId}
  user_id: string | null
  message: string
  is_anonymous: boolean
  status: "new" | "reviewed" | "closed"
  created_at: timestamp

/classes/{classId}/confessions/{confessionId}
  user_id: string | null
  message: string
  status: "pending" | "approved" | "rejected" | "broadcasted"
  moderator_id: string | null
  created_at: timestamp
  moderated_at: timestamp | null

/classes/{classId}/study_buddy_requests/{requestId}
  user_id: string
  subject: string
  goal: string
  availability: string
  status: "open" | "matched" | "cancelled"
  matched_user_id: string | null
  created_at: timestamp

/classes/{classId}/broadcast_history/{broadcastId}
  title: string
  message: string
  sent_by: string
  recipient_count: number
  success_count: number
  failure_count: number
  created_at: timestamp
```

### Migration Strategy

P0 migration should be additive and reversible:

1. Add class context helpers without deleting root collections.
2. Create `/classes/mtc12` and copy current root data into it.
3. Dual-read only where necessary during transition.
4. Switch new writes to class-scoped collections.
5. Keep root collections as rollback source until verified.
6. Remove or archive root collection reads only after dashboard and LINE flows are class-aware.

Rollback plan:

- Disable class-scoped reads with a feature flag.
- Repoint handlers/admin API back to root collections.
- Keep migration scripts idempotent so reruns do not duplicate documents.

## API Design

### Existing API Boundary

Keep this boundary:

```text
Browser
  -> Next.js dashboard
  -> Next.js server-side /api/admin/* proxy
  -> Flask /api/admin/* Blueprint
```

Do not let browser-side code call Flask directly with the dashboard token.

### Target Admin API

Class-scoped admin endpoints should require one of:

- A `class_id` path segment.
- A validated `class_id` query parameter.
- A class inferred from the authenticated admin's allowed classes.

Preferred shape:

```text
GET    /api/admin/classes
POST   /api/admin/classes
GET    /api/admin/classes/{class_id}/overview
GET    /api/admin/classes/{class_id}/users
GET    /api/admin/classes/{class_id}/homeworks
POST   /api/admin/classes/{class_id}/homeworks
GET    /api/admin/classes/{class_id}/feedback
PATCH  /api/admin/classes/{class_id}/feedback/{feedback_id}
GET    /api/admin/classes/{class_id}/confessions
PATCH  /api/admin/classes/{class_id}/confessions/{confession_id}
GET    /api/admin/classes/{class_id}/config/timetable
PUT    /api/admin/classes/{class_id}/config/timetable
GET    /api/admin/classes/{class_id}/config/links
PUT    /api/admin/classes/{class_id}/config/links
POST   /api/admin/classes/{class_id}/broadcasts
```

Rules:

- Validate admin authorization before every class-scoped read/write.
- Validate the current Flask-managed principal, role, capability, account
  status, and class assignment for every protected request.
- Return structured errors using the current `{"error": {"code", "message", "request_id"}}` shape.
- Keep `/callback` independent from dashboard errors.
- Limit dashboard payload sizes.
- Paginate collection reads.
- Do not stream all users for count-only dashboard cards; keep O(1) counter docs where possible.

### LINE Bot Class Resolution

Target flow:

```text
FollowEvent or first message
  -> check global user registry or class user docs
  -> if no class_id, ask user to choose MTC generation
  -> save class_id
  -> route command with ClassContext
```

Suggested `ClassContext` fields:

```text
class_id
user_id
role
feature_flags
class_config
```

Handlers should receive context instead of directly reading hardcoded MTC12 config.

## Feature Roadmap

### P0 - Multi-Tenant Foundation

Goal: make the bot safe for MTC13 without duplicating the codebase.

Build:

- Class registry.
- User onboarding flow for selecting MTC generation.
- Class-aware Firestore helper.
- Class admin permission model.
- Migration script for MTC12 root data into `/classes/mtc12`.
- Dashboard class selector.
- Class-scoped admin API reads.

Exit criteria:

- MTC12 behavior remains unchanged.
- New MTC13 class can be created without code edits.
- A class admin cannot access another class.
- `python -m compileall -q src` passes.
- Dashboard lint/typecheck/build passes when dashboard files change.
- Rollback to root collections is documented and tested in a dry run.

### P1 - Low-Risk Student Value

Goal: add useful features with small blast radius.

Build:

- Feedback system.
- MTC The Game link in links menu or `/game`.
- Class config editor for timetable, links, teachers, and exams.

Notes:

- Feedback writes to `/classes/{classId}/feedback`.
- Game link should be a config value, not hardcoded.
- If MTC The Game exposes a leaderboard API, integrate it behind a timeout and graceful fallback.

### P2 - High-Engagement Features With Guardrails

Goal: add viral features safely.

Build:

- Lookmaxxing Assistant.
- Anonymous confession with moderation.
- Study buddy matching.

Lookmaxxing rules:

- Text-only category advice.
- No selfie analysis.
- No attractiveness scoring.
- No face rating.
- No invasive procedure recommendations.
- No prescription drug advice.
- No diagnosis.
- Include "consult a doctor/dermatologist" guidance for medical concerns.
- Keep advice budget-friendly and evidence-informed.

Confession rules:

- Default status is `pending`.
- Broadcast only after admin approval.
- Store moderation action.
- Add abuse controls and rate limits before launch.

Study buddy rules:

- Match inside the same `class_id`.
- Show only the minimum needed contact details.
- Allow users to cancel open requests.

### P3 - Automation And Analytics

Goal: make the assistant useful without manual prompting.

Build:

- Exam countdown push notifications.
- Daily quiz/trivia.
- Richer dashboard analytics.
- Weekly class health report.
- Error and uptime alert routing to super admins.

Constraints:

- LINE OA push limits must be respected.
- Scheduled jobs must be idempotent.
- Broadcast-style features need dry-run mode.

## Safety And Security

### Data Boundaries

- Class admins must not read or mutate other classes.
- Teachers must not read or mutate classes outside explicit assignments.
- Raw LINE user IDs are super-admin-only and require an audited support,
  abuse-response, or delivery-diagnosis purpose.
- A user's `class_id` must be resolved server-side.
- Do not trust client-provided `class_id` without checking permissions.
- Keep super admin powers explicit.
- Do not expose raw LINE user IDs unnecessarily in student-facing features.

### Secret Handling

- Do not commit `.env`.
- Do not commit Firebase key files.
- Do not paste secrets into docs.
- Use Render env vars or a secure VPS `.env`.
- Keep `MTC_DASHBOARD_API_TOKEN`, `DASHBOARD_SESSION_SECRET`, LINE tokens, Gemini keys, and Firebase credentials separate.

### AI Safety

- AI features must fail closed when API keys, quotas, or timeouts fail.
- Prompts must include feature-specific safety boundaries.
- Do not let AI generate medical, legal, or disciplinary authority decisions.
- Store only what is needed for the feature.
- Add feature flags for risky or experimental AI features.

### Abuse Controls

- Keep per-user rate limiting.
- Add per-feature rate limits for confession, feedback, and AI tools.
- Keep blacklist behavior class-aware where appropriate.
- Log admin moderation actions.

## Performance And Reliability

### Tightest Constraints

- LINE webhook responses should be fast enough to avoid user-visible delays.
- Dashboard reads should avoid unbounded collection scans.
- Firestore count-like dashboard cards should use counters or bounded queries.
- AI and external API calls must have timeouts and graceful fallback text.
- Broadcasts should run in background workers/threads and record results.

### Current Scale Risks

- Some state is still in process memory.
- Multiple Gunicorn workers can split in-memory sessions and caches.
- Root-level collections make class isolation impossible.
- Hardcoded `config.py` class data requires deploys for ordinary timetable/link changes.
- Unbounded Firestore streams will become expensive with many users/classes.

### Reliability Defaults

- Keep `/healthz` lightweight.
- Keep `/callback` independent from dashboard and analytics features.
- Prefer idempotent scheduled jobs.
- Prefer additive migrations.
- Prefer feature flags over emergency code reverts.

## Development Protocol

Every code, architecture, or creative task should be evaluated through these roles.

### Lead Coder

- Identify the tightest production constraint before editing.
- Keep diffs minimal and reviewable.
- Preserve separation of concerns.
- Do not mix rendering/UI with state mutation.
- Do not rewrite full files unless explicitly requested.
- Validate module load order before monkey patches or overrides.
- Prefer small helpers over direct access to another module's private globals.

### Systems Analyst

- Produce a risk sheet before implementation.
- List blast radius.
- List dependency graph.
- List load order.
- State the smallest delta.
- Surface architecture smells in one concise sentence each.
- Define exit criteria and rollback plan.

### Creative Designer

Use this role when the task touches UI, character concepts, animations, VFX, or student-facing product identity.

- Provide exactly three distinct creative directions.
- Recommend one direction with one sentence of justification.
- Specify implementable visual details: colors, timing, easing, dimensions, and asset coordinates when relevant.
- Stay grounded in the current technical stack.

## Pre-Implementation Risk Sheet Template

Use this before non-trivial changes:

```markdown
## Risk Sheet

Deliverable:

Tightest constraint:

Blast radius:

Dependency graph:

Load order:

Smallest delta:

Architecture smells:

Exit criteria:

Rollback plan:
```

Example for multi-tenant migration:

```markdown
## Risk Sheet

Deliverable:
Class-aware Firestore access for homework reads and writes.

Tightest constraint:
LINE webhook latency and Firestore read volume.

Blast radius:
Homework commands, dashboard homework preview, broadcast homework reminders, migration script.

Dependency graph:
handlers.py -> homework_session.py -> features.py -> Firestore
admin_api.py -> _get_recent_homeworks -> Firestore
broadcast.py -> broadcast_homework_reminder -> Firestore

Load order:
main.py initializes Firebase, then features/broadcast/admin_api receive database access.

Smallest delta:
Add class-aware collection helper and route only homework through it first.

Architecture smells:
Current `features.py` owns both response formatting and Firestore paths.

Exit criteria:
MTC12 homework behavior is unchanged, MTC13 homework uses a separate path, compile checks pass.

Rollback plan:
Feature flag homework collection helper back to root `/homeworks`.
```

## Public Interface Changes To Prefer

Use explicit context objects rather than hidden globals for new class-aware work.

Preferred:

```python
@dataclass(frozen=True)
class ClassContext:
    class_id: str
    user_id: str
    role: str
```

Preferred helper shape:

```python
def class_collection(db, class_id: str, collection_name: str):
    return db.collection("classes").document(class_id).collection(collection_name)
```

Avoid:

```python
db.collection("homeworks")
```

for new class-owned features.

Avoid:

```python
CURRENT_CLASS_ID = "mtc12"
```

except as a temporary migration fallback behind a named feature flag.

## Dashboard Product Directions

These are future-facing options for dashboard and student-facing UI. If UI work is requested, choose one direction before designing screens.

### Direction 1 - MTC Command Center

- Mood: operational, sharp, admin-first.
- Primary color: `#0F172A`.
- Accent color: `#38BDF8`.
- Warning color: `#F97316`.
- Background: layered navy gradient from `#020617` to `#111827`.
- Motion: 0.18s ease-out for hover, 0.35s cubic-bezier(0.22, 1, 0.36, 1) for panel reveal.
- Best for: admin monitoring, uptime, broadcast operations, risk dashboards.

### Direction 2 - Classroom OS

- Mood: clean, modular, long-lived, handoff-friendly.
- Primary color: `#12372A`.
- Accent color: `#F4B942`.
- Surface color: `#FFF8E7`.
- Background: paper-like warm surface with subtle grid at 24px spacing using `rgba(18, 55, 42, 0.08)`.
- Motion: 0.22s ease-out for controls, 0.45s cubic-bezier(0.16, 1, 0.3, 1) for page transitions.
- Best for: class admin handoff, timetable editing, config management, multi-generation support.

### Direction 3 - Student Companion

- Mood: friendly, social, student-first.
- Primary color: `#1D4ED8`.
- Accent color: `#FB7185`.
- Support color: `#22C55E`.
- Background: soft radial gradients using `rgba(251, 113, 133, 0.18)` and `rgba(34, 197, 94, 0.12)`.
- Motion: 0.28s ease-in-out for quick replies, 0.5s cubic-bezier(0.34, 1.56, 0.64, 1) for celebratory cards.
- Best for: feedback, study buddy, quiz, student profile, student-facing landing pages.

Recommended direction: Classroom OS. It best matches the long-term requirement that future class admins can maintain MTC Assistant without Mawin deploying code for every change.

## Implementation Priorities For Future Agents

1. Do not begin new feature work by adding more hardcoded MTC12 data.
2. Move class-changing data into Firestore config documents.
3. Keep class-aware access behind small helper functions.
4. Extend dashboard APIs before adding dashboard UI that needs new backend data.
5. Add tests around routing and data path selection before migrations.
6. Use feature flags for risky features.
7. Keep Render deployment behavior stable unless deployment is the explicit task.

## Verification Commands

For backend-only changes:

```powershell
python -m compileall -q src
git diff --check -- <touched-files>
```

For dashboard changes:

```powershell
cd dashboard
npm run lint
npm run typecheck
npm run build
```

For documentation-only changes:

```powershell
git diff -- CONTEXT.md
git diff --check -- CONTEXT.md
```

For local dashboard and admin API verification:

```powershell
$env:PYTHONPATH="src"
$env:MTC_DASHBOARD_API_TOKEN="local-dashboard-token"
python -m mtc_assistant.main
```

```powershell
cd dashboard
$env:MTC_BOT_API_BASE_URL="http://127.0.0.1:5001"
$env:MTC_DASHBOARD_API_TOKEN="local-dashboard-token"
$env:DASHBOARD_PASSWORD="local-password"
$env:DASHBOARD_SESSION_SECRET="replace-with-long-local-secret"
npm run dev
```

Then verify through the Next.js proxy, not by exposing Flask tokens to the browser.

## Non-Goals Unless Explicitly Requested

- Do not replace LINE as the primary student interface.
- Do not move all data to SQL unless a separate architecture decision is made.
- Do not merge dashboard and webhook into one frontend/backend process.
- Do not build selfie-based attractiveness scoring.
- Do not broadcast anonymous content without moderation.
- Do not clean unrelated dirty worktree files while implementing a scoped task.

## Current Assumptions

- `AGENTS.md` remains the active development protocol.
- `CONTEXT.md` is an engineering context file for AI coding tools.
- Multi-tenant migration is planned but not yet implemented.
- MTC12 remains the production baseline until migration is verified.
- MTC13 support should be added through class-aware architecture, not a fork.
- Render remains the active deployment baseline until a VPS migration is explicitly selected.

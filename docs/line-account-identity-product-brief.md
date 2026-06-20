# LINE Account Identity Product Brief

## Placement

This is a supporting brief for Master Plan 1, Phase 4, under the Dashboard Auth
supporting roadmap Phase H: LINE onboarding upgrade.

It does not replace `CONTEXT.md`, `docs/mtc-os-master-plan.md`, or
`docs/dashboard-auth-roadmap.md`.

## Student Experience

The LINE account card gives students one safe place to check their MTC account
state, active class, and roster verification status. It supports MTC11, MTC12,
and MTC13 through one generic class-aware flow.

The same LINE account surface also supports MTC teacher identity as a separate
product identity type. Teacher verification uses the operator-managed teacher
directory plus a private one-time verification code hash; a teacher name is only
an allowlist/display value and is never treated as a secret.

## Privacy Rules

Student ID is proofing material only. The runtime converts it to a server-side
HMAC roster key immediately and never stores or displays the raw value.

Class membership and roster verification are separate. Invite-joined students
may use their authorized class while remaining visibly unverified.

Teacher LINE verification does not create a Dashboard account, does not grant
class_admin or super_admin, and does not grant access outside explicit teacher
assignments. Homeroom teacher is an assignment descriptor, not an elevated
authorization role.

MTC11 now has verified registry, term, room, and timetable-day seed data for
2569 term 1. Timetable image delivery remains pending until a reviewed HTTPS
image URL is supplied through the operator seed workflow.

## Visual Direction

Use a Classroom OS account card, not a marketplace account page. The card uses
deep navy and teal surfaces, warm ivory content areas, mint primary actions,
muted gold verified state, and soft amber unverified state.

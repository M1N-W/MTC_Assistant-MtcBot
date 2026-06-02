# MTC Ecosystem Starter Plan

## Purpose

This plan aligns MTC Assistant, MTC Dashboard, Math Talent, MTC Cipher, MTC The Game, and MTC Hub without creating scope creep before the 2026-06-09 MTC12/MTC13 code-family reveal event.

The near-term goal is to make the ecosystem feel connected through link-first integration while keeping MTC Assistant production stability and demo readiness as the sprint priority. This document separates the long-term ecosystem vision from the tasks that are safe to attempt before June 9.

## Ecosystem Map

MTC Ecosystem:

- MTC Assistant
  - LINE Bot
  - MTC Dashboard
- Math Talent
  - MTC Cipher
- MTC The Game
- MTC Hub

MTC Assistant is the practical classroom utility. It owns the LINE Bot entry point, core student commands, class-aware links, learning resources, timetable behavior, and admin operations through the dashboard.

Math Talent is the math learning website and applied math space. It should contain learning content and interactive labs, with MTC Cipher as the first flagship project.

MTC The Game is a separate game/community project. It should be linked from the ecosystem, but it should not become part of MTC Assistant's production-critical flow.

MTC Hub is the lightweight portal that makes the ecosystem visible. It can connect students to the right product without shared auth, shared databases, or deep backend integration.

## Product Positioning

- MTC Assistant: classroom utility, LINE Bot, and student entry point.
- MTC Dashboard: admin/control surface for MTC Assistant.
- Math Talent: math learning website and applied math hub.
- MTC Cipher: flagship math project, matrix cipher lab, and cipher game.
- MTC The Game: separate web game and community/entertainment project.
- MTC Hub: lightweight portal connecting the ecosystem.

MTC The Game should be mentioned and linked because it is a valuable existing project, but it should not become the main math project. MTC Cipher should carry the math-project weight because it has a clearer applied math core. MTC Hub should make the ecosystem visible without deep backend integration.

## Role of MTC Assistant

MTC Assistant remains the primary LINE Bot and practical classroom assistant. It should prioritize useful commands, class-aware links, learning resources, timetable behavior, and demo stability before June 9.

MTC Assistant can link users to ecosystem products, but it should not absorb every ecosystem feature into the bot. The safest near-term role is launcher and guide first, with deeper integration only after each product boundary is clearer.

## Role of MTC Dashboard

MTC Dashboard is admin-facing, not student-facing. It supports MTC Assistant operations such as class data, links, resources, admin workflows, metrics, and future class-admin self-service.

The existing dashboard auth roadmap remains the source of truth for future auth/admin work. Dashboard work should not start immediately unless Mawin explicitly requests it. No dashboard resource editor or ecosystem admin panel should be implemented now.

## Role of Math Talent

Math Talent should be the math website and learning hub. It can include high-school math content, problem sources, learning links, and future interactive labs.

To avoid becoming just a computer project, Math Talent must include interactive applied-math features. MTC Cipher is the first flagship lab. Later labs can explore graph theory, probability, functions, transformations, optimization, modular arithmetic, or other math topics with visible interaction.

## Role of MTC Cipher

MTC Cipher is the math project and cipher game/lab. It should use matrix-based encryption and decryption as an educational model, not as real secure encryption.

The product should avoid anonymous messaging or harmful use. It can be linked from Math Talent and MTC Assistant, but initial scope should stay simple, visual, and clearly educational.

## Role of MTC The Game

MTC The Game is an existing web game project and should not be wasted. It should be linked from MTC Assistant and/or MTC Hub as a community game.

It should stay separate from MTC Assistant production-critical flows. Do not over-integrate before June 9. Avoid leaderboard, account, and cloud-save integration for now. Do not expose admin or debug tools through MTC Assistant. Keep it as link-first integration until there is a clear reason for deeper integration.

## Role of MTC Hub

MTC Hub should be the lightweight portal or landing page for the ecosystem. It can show cards for MTC Assistant, Math Talent, MTC Cipher, and MTC The Game.

It can include QR codes, short descriptions, and demo links. It should not require login in the first version. It should not require shared auth, shared database, or a cross-product account system. It has high demo value and low blast radius if implemented as a simple static page later.

## Integration Principles

- Link-first before API integration.
- Docs before code.
- Prototype before platform.
- Manual workflow before admin dashboard.
- No shared auth until necessary.
- No cross-product database coupling before boundaries are clear.
- Keep each product independently deployable where practical.
- The ecosystem should degrade gracefully if one product is down.
- MTC Assistant must not be blocked by MTC The Game, Math Talent, or MTC Hub failures.

## June 9 Presentation Scope

Realistic before 2026-06-09:

- Stable MTC Assistant demo.
- MTC The Game link or mention if the URL is available and safe.
- Math Talent concept or teaser.
- MTC Cipher concept/prototype only if it does not risk MTC Assistant stability.
- MTC Hub mockup or simple landing page only if time allows.
- Clear presentation narrative.

Do not attempt before June 9:

- Shared login.
- Full dashboard auth implementation.
- Full Math Talent content platform.
- Full MTC Cipher production version.
- MTC The Game leaderboard integration.
- Cross-product account/profile system.
- Large refactors.

## Suggested Presentation Narrative

MTC Assistant solves real classroom utility problems through a LINE Bot that students can already use.

MTC The Game shows the creative and community side of the project.

Math Talent and MTC Cipher show the applied math learning direction, where math becomes something students can experiment with.

MTC Hub connects the projects into one visible ecosystem. The long-term goal is handoff-friendly tools for future MTC generations.

## Risk Sheet

Deliverable:
Docs-only starter plan for the MTC Ecosystem.

Tightest constraint:
Presentation readiness by 2026-06-09 without destabilizing MTC Assistant.

Blast radius:
Documentation only for this task. Future ecosystem work can affect MTC Assistant production stability, student navigation, public demos, project branding, and perceived product scope.

Dependency graph:
MTC Assistant stability -> learning resources workflow -> safe link surfaces -> optional Hub concept -> optional Math Talent/Cipher teaser -> later deeper integrations.

Load order:
Lock product boundaries first, verify links second, build simple static surfaces third, and defer shared auth/API integration until the need is proven.

Smallest delta:
Create this plan only. Future work should start with safe links or a static Hub mockup, not backend integration.

Architecture smells:
Over-integrating separate products too early can make MTC Assistant fragile. Too many product names can confuse students. If MTC Cipher is not visibly math-based, the math project may look like a computer project. Shared accounts, leaderboards, LINE user IDs, official-school framing, and solo-developer maintenance load are the main ecosystem risks.

Exit criteria:
The plan clearly separates product roles, June 9 scope, non-goals, security boundaries, and next phases without claiming any new implementation exists.

Rollback plan:
If ecosystem framing causes confusion, keep MTC Assistant as the only demo-critical product and present other projects as future links or concepts.

## Brand and UX Direction

Use consistent naming and short descriptions. Keep MTC Assistant practical and friendly. Keep Math Talent educational and interactive. Keep MTC The Game fun and community-oriented. Keep MTC Hub simple and portal-like.

Avoid overwhelming users. Use clear cards, buttons, and QR entry points. Students should not need to understand the architecture to use the ecosystem.

Starter naming/copy style:

- MTC Assistant: ผู้ช่วยประจำห้อง
- Math Talent: พื้นที่เรียนรู้คณิตศาสตร์
- MTC Cipher: ห้องทดลองรหัสเมทริกซ์
- MTC The Game: เกมของชาว MTC
- MTC Hub: ประตูสู่ MTC Ecosystem

## Security and Privacy Checklist

- No secrets in repo.
- No real rosters in ecosystem docs.
- No raw student IDs.
- No shared auth before a real auth design exists.
- No public exposure of LINE user IDs.
- No leaderboard tied to real identities without careful design.
- No anonymous messaging through MTC Cipher.
- No exposing MTC The Game admin/debug tools through the bot.
- Browser must never receive `MTC_DASHBOARD_API_TOKEN`.
- MTC Assistant should remain stable if ecosystem links fail.
- Use placeholders for URLs unless Mawin provides verified production URLs.

## Phased Plan

Phase A: This docs-only ecosystem starter plan.

Phase B: Add or verify MTC The Game as a safe general link / ecosystem link.

Phase C: Draft MTC Hub landing page concept.

Phase D: Draft Math Talent concept and MTC Cipher math scope.

Phase E: Build MTC Hub static landing page only if it does not threaten June 9 stability.

Phase F: Build MTC Cipher prototype after learning resources workflow is safe.

Phase G: Later evaluate deeper integrations such as LINE command launchers, challenge pages, or dashboard-managed links.

Phase H: Long-term ecosystem governance and handoff docs.

Do not start Phase B implementation until Mawin explicitly requests it. For the current sprint, MTC Assistant stability and learning resources remain higher priority than ecosystem expansion.

## Non-Goals

- No implementation in this task.
- No backend changes.
- No dashboard changes.
- No MTC Hub implementation.
- No Math Talent implementation.
- No MTC Cipher implementation.
- No MTC The Game source changes.
- No shared auth.
- No leaderboard/account/profile integration.
- No deployment changes.
- No Render deploy.
- No Firebase changes.
- No PR or push.
- No claim that the ecosystem is official school infrastructure.

## Open Questions

- What production URL should MTC The Game use?
- Should MTC Hub live inside the MTC Assistant repo or as a separate static site later?
- Should Math Talent live under the same domain/hosting as MTC Assistant assets or separately?
- How much MTC branding is appropriate without official school approval?
- What should be shown on June 9 versus saved for later?
- Should MTC Cipher be web-first, bot-first, or both?
- Who maintains Math Talent content?
- Should future challenges avoid ranking by real student identity?
- How can the ecosystem stay maintainable for a solo developer?

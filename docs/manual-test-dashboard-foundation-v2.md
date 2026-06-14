# Dashboard Foundation v2 Manual Review

## Design Directions

1. Quiet Academic Operations: restrained institutional sidebar, white working surfaces, compact headers, and task-first content.
2. Warm Classroom Desk: warmer paper tones, larger editorial type, and softer content grouping.
3. Dense Operations Ledger: compact tables, stronger dividers, and higher information density for frequent administrators.

Selected direction: Quiet Academic Operations because it best supports teacher-first Thai tasks while preserving clear system administration boundaries.

## Risk Sheet

- Blast radius: Dashboard presentation and state, two read-only Admin API endpoints, and focused tests.
- Dependency graph: Dashboard client -> Next.js proxy -> Flask Admin API -> existing class registry and Paperless collections.
- Load order: authenticated shell loads workspaces first; section queries load only when rendered.
- Smallest delta: no schema migration, no write-contract change, and no backend auth change.
- Architecture smell addressed: the former Dashboard shell combined navigation, API helpers, mutations, and every section in one component.
- Performance budget: no continuous animation, section-aware queries, no chart library use in rendered Dashboard code, and no page-level horizontal overflow.
- Rollback: revert the single milestone commit.

## Automated Checks

- `python -m compileall -q src`
- `python -m unittest tests.test_admin_api`
- focused Admin API test modules
- full backend suite
- `npm run lint`
- `npm run typecheck`
- `npm run build`
- `git diff --check origin/main...HEAD`

## Responsive Checks

- 1440x900: persistent sidebar, compact header, no horizontal overflow.
- 1024x768: compact desktop layout, content remains readable.
- 768x1024: mobile application bar and drawer replace the sidebar.
- 390x844: all menu items reachable, drawer scroll preserved, scrollbar hidden, no page-level horizontal overflow.

## Functional Checks

- Login layout, incorrect password, auth-not-configured copy, logout.
- Workspace loading, selection, versioned persistence, invalid stored selection fallback.
- Direct hash, refresh, Back, Forward, and invalid hash fallback.
- LINE accounts remain masked and copyable.
- Homework and broadcast history use bounded factual data.
- Broadcast copy consistently states the global registered-user audience.
- General Links uses the selected active workspace and exposes only four supported keys.
- Link edit dialog closes with Escape and preserves entered text after save failure.
- System shows factual metrics and Paperless counts without impact estimates.
- Blacklist and Paperless upload actions remain reachable.
- AI credential and policy operations remain reachable without redisplaying raw keys.

## Accessibility Checks

- Visible focus styles.
- Semantic headings and labels.
- `aria-current="page"` on active navigation.
- Drawer and dialog move focus inside, close with Escape, and return focus.
- Status text is not color-only.
- Reduced-motion media query.
- Long Thai copy wraps and controls remain usable at 200% zoom.

## Security Checks

- Browser calls only the Next.js proxy.
- Service token remains server-only.
- Proxy errors do not reveal the Flask base URL.
- No raw credentials, extracted image text, raw LINE IDs, or student records appear in screenshots.
- No hidden feature code, asset, or UI reference is introduced.

## Correctness Follow-up

Verified on 2026-06-14 against the local branch with mocked Admin API responses:

- Global pages show `ข้อมูลรวมทั้งระบบ`; General Links and AI Settings retain the selected room and active term.
- The workspace selector explains that it applies only to General Links and AI Settings.
- Valid, invalid, changed, and empty workspace persistence states behave as specified.
- Service badges distinguish loading, ready, degraded, and request-error states without an outage flash.
- The drawer and announcement dialog trap forward and reverse Tab navigation, lock body scrolling, close with Escape, and restore focus.
- The announcement preview identifies all registered users as the audience.
- General Links announces a successful save, clears old success feedback on the next edit, and preserves the URL and open dialog after failure.
- The document has no page-level horizontal overflow at 1440x900, 1024x768, 768x1024, or 390x844.
- Review screenshot: `%TEMP%\mtc-dashboard-pr6-390.png` (not committed).

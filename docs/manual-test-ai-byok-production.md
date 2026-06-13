# AI/BYOK Production Release Manual-Test Record

## Classification

This is historical manual-test evidence for the production release at the
recorded commit. It is not automatically proof of the current deployment after
later changes.

## Release Record

- Production `main` commit: `410552c`
- Render deployment mode: Manual Deploy
- Render auto-deploy: disabled for `mtc-bot` and `mtc-dashboard`

## Passed Checks

- [x] Bot `/healthz`: healthy
- [x] Dashboard `/api/health`: healthy
- [x] Dashboard login: passed
- [x] Overview/API proxy: passed
- [x] AI Settings no-credential state: passed
- [x] LINE routing smoke tests: passed
- [x] MTC67 regression: passed

No secrets, credentials, tokens, or environment values are recorded here.

## Non-Blocking Warning

The release emitted the Next.js warning:

```text
next start does not work with output standalone
```

This warning is future deployment cleanup. It was not a blocker for this
verified release.

## Result

The AI/BYOK production release was deployed and verified successfully at
commit `410552c`. It is completed current-production history and is not part of
the remaining June 20, 2026 MTC OS v1 Foundation Release implementation scope.

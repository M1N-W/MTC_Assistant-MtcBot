# MTC Assistant Documentation

This index defines documentation authority for MTC Assistant and its evolution
toward MTC OS. When documents conflict, use the higher-authority document in
this index and treat point-in-time test records as evidence, not current-state
specifications.

## Canonical

- [MTC Enviroment Overview](mtc-enviroment-overview.md): official product
  hierarchy, repository boundaries, and integration rules.
- [MTC OS Master Plan](mtc-os-master-plan.md): authoritative roadmap, June 20,
  2026 production scope, locked decisions, dependencies, and exit criteria.
- [Worksheet, Homework, and Learning Resources Boundaries](worksheet-homework-learning-resources-boundaries.md):
  canonical separation of those data domains.
- [Project Context](../CONTEXT.md): current architecture map and domain
  terminology. The canonical roadmap overrides older phase ordering in this
  file where necessary.

## Active Roadmap

- [Dashboard Auth and Admin Roadmap](dashboard-auth-roadmap.md)
- [Exam Calendar and Reminder Roadmap](p3-exam-calendar-reminder-roadmap.md)
- [Learning Resources Seed/Config Workflow](learning-resources-seed-config-workflow.md)
- [VPS Migration Plan](deployment/vps-migration-plan.md)

Active roadmaps provide implementation detail. They must remain consistent with
the canonical product hierarchy and MTC OS master plan.

## Architecture and Operations

- [Dashboard Architecture](dashboard-architecture.md)
- [Term Readiness Check](term-readiness-check.md)
- [Learning Resources Seed Validator Usage](learning-resources-seed-validator-usage.md)

## Historical Manual-Test Evidence

- [AI/BYOK Production Release](manual-test-ai-byok-production.md)
- [MTC13 Multi-Class](manual-test-mtc13-multiclass.md)
- [General Links Config](manual-test-general-links-config.md)
- [MTC67](manual-test-mtc67.md)

Manual-test documents record a result at a specific commit and time. They do
not automatically describe the current deployment, current data, or current
behavior after later changes.

## Superseded

- [MTC Ecosystem Starter Plan](mtc-ecosystem-starter-plan.md): retained as
  historical planning context. The active product map is the MTC Enviroment
  Overview.

## Legacy Idea Backlog

- [Future Features Roadmap](roadmap-future-features.md): non-authoritative idea
  history. It does not set current implementation order.

## Authority Rules

1. Locked product and security decisions in the canonical documents take
   precedence over older examples or plans.
2. Current repository behavior must still be verified in code and tests.
3. Manual-test records prove only the recorded point-in-time result.
4. Recommendations and open questions are not implemented facts.
5. Never infer that every roadmap item already exists in production.

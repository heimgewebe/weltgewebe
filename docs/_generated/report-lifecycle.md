---
id: docs.generated.report-lifecycle
title: Report Lifecycle Overview
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierte Übersicht der Report-Lifecycle-Zustände.
---
# Report Lifecycle Overview

Generated automatically. Do not edit manually.

This overview is descriptive only. It surfaces lifecycle metadata and validator findings for planning; it is not a CI guard and not a policy judgement.

## Summary

| Metric | Count |
| --- | ---: |
| files_scanned | 45 |
| reports_checked | 41 |
| reports_ignored_non_report | 4 |
| reports_with_lifecycle_state | 41 |
| reports_missing_lifecycle_state | 0 |
| findings_total | 0 |

## Lifecycle State Summary

| lifecycle_state | Count |
| --- | ---: |
| active | 32 |
| deferred | 0 |
| superseded | 5 |
| archived | 4 |
| missing | 0 |

## Finding Summary

| Code | Count |
| --- | ---: |
| _None_ | 0 |

## Active Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| docs/reports/auth-persistence-runtime-target-reconciliation.md | active | audit | OPT-API-002 | 2026-07-17 |  |
| docs/reports/auth-pg-002-controlled-preflight.md | active | planning | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-cutover-plan.md | active | planning | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-passkey-db-store.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-passkey-fk-readiness-audit.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-passkey-runtime-audit-heimserver-2026-07-01.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-passkey-runtime-audit-plan.md | active | planning | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-passkey-runtime-facade.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-runtime-schema-readiness-heimserver-2026-07-01.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-002-schema-preflight-ci.md | active | proof | AUTH-PG-002 | 2026-09-30 |  |
| docs/reports/auth-pg-003-backfill-readiness.md | active | proof | AUTH-PG-003 | 2026-09-30 |  |
| docs/reports/auth-pg-003-runtime-audit-heimserver-2026-07-01.md | active | proof | AUTH-PG-003 | 2026-09-30 |  |
| docs/reports/auth-pg-003-runtime-audit-wg-pg-proof-2026-07-01.md | active | proof | AUTH-PG-003 | 2026-09-30 |  |
| docs/reports/cost-report.md | active | generated | DOCMETA-REPORT-LIFECYCLE-001 | 2026-09-29 |  |
| docs/reports/domain-account-email-uniqueness-audit.md | active | audit | OPT-ARC-001 | 2026-07-13 |  |
| docs/reports/domain-account-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-backfill-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-edge-cache-limit-design.md | active | decision-prep | DOMAIN-PG-003 | 2026-09-29 |  |
| docs/reports/domain-edge-reference-audit.md | active | audit | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-edge-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-node-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-postgres-instance-coherence-decision.md | active | audit | DOMAIN-PG-002 | 2026-12-18 |  |
| docs/reports/domain-provider-role-finding.md | active | audit | DEPLOY-DNS-001 | 2026-07-23 |  |
| docs/reports/domain-read-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-runtime-data-source-reconciliation.md | active | audit | DB-PROOF-001 | 2026-07-18 |  |
| docs/reports/github-action-ref-pinning-audit.md | active | audit | OPT-INF-002 | 2026-09-30 |  |
| docs/reports/github-actions-node24-readiness.md | active | audit | OPT-CI-005 | 2026-09-29 |  |
| docs/reports/map-architekturkritik.md | active | audit | DOCMETA-REPORT-LIFECYCLE-001 | 2026-09-29 |  |
| docs/reports/map-basemap-proof-gap-reconciliation.md | active | audit | DOCMETA-REPORT-LIFECYCLE-001 | 2026-09-29 |  |
| docs/reports/optimierungsbericht.md | active | audit | DOCMETA-REPORT-LIFECYCLE-001 | 2026-09-29 |  |
| docs/reports/proof-matrix-generalization-decision.md | active | decision | DOCMETA-PROOF-001 | 2026-09-29 |  |
| docs/reports/repo-audit-2026-07-02.md | active | audit | REPO-AUDIT-001 | 2026-10-31 |  |

## Deferred Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| _None_ | | | | | |

## Superseded Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| docs/reports/auth-persistence-direct-proof-diagnose-audit.md | deprecated | audit | OPT-API-002 |  |  |
| docs/reports/auth-persistence-next-step.md | deprecated | decision-prep | OPT-API-002 |  |  |
| docs/reports/auth-persistence-readiness.md | deprecated | decision-prep | OPT-API-002 |  |  |
| docs/reports/auth-persistence-runtime-proof.md | deprecated | proof | OPT-API-002 |  |  |
| docs/reports/domain-edge-create-semantics-preflight.md | deprecated | decision-prep | OPT-ARC-001 |  |  |

## Archived Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| docs/reports/inwx-zone-reconciliation-plan.md | deprecated | planning | DEPLOY-DNS-001 |  |  |
| docs/reports/passkey-register-verify-prep.md | deprecated | decision-prep | AUTH-PG-002 |  |  |
| docs/reports/planning-registration-findings.md | deprecated | audit | TASK-CTL-005 |  |  |
| docs/reports/report-lifecycle-restbestand-triage.md | deprecated | audit | DOCMETA-REPORT-LIFECYCLE-001 |  |  |

## Unclassified Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| _None_ | | | | | |

## Reports With Findings

| Report | lifecycle_state | status | findings |
| --- | --- | --- | --- |
| _None_ | | | |

## Reports With Missing Currently-Enforced Fields

Fields required by the currently implemented validator rules that are absent, in rule-precedence order. This reflects field presence only; it is not a full normative lifecycle judgement and does not cover enum, date, owner, or relation checks. Future validator rules may surface additional requirements.

| Report | status | lifecycle_state | Missing currently-enforced fields |
| --- | --- | --- | --- |
| _None_ | | | |

## Non-Report Files Under docs/reports

| File | doc_type | status |
| --- | --- | --- |
| docs/reports/agent-readiness-audit.md | documentation | active |
| docs/reports/auth-status-matrix.md | reference | active |
| docs/reports/map-status-matrix.md | status-matrix | active |
| docs/reports/optimierungsstatus.md | status-matrix | active |

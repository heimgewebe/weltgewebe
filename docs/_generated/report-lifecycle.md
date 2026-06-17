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
| files_scanned | 25 |
| reports_checked | 20 |
| reports_ignored_non_report | 5 |
| reports_with_lifecycle_state | 13 |
| reports_missing_lifecycle_state | 7 |
| findings_total | 21 |

## Lifecycle State Summary

| lifecycle_state | Count |
| --- | ---: |
| active | 8 |
| deferred | 0 |
| superseded | 5 |
| archived | 0 |
| missing | 7 |

## Finding Summary

| Code | Count |
| --- | ---: |
| missing_lifecycle | 7 |
| missing_lifecycle_state | 7 |
| missing_review_after | 7 |

## Active Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| docs/reports/auth-persistence-runtime-target-reconciliation.md | active | decision-prep | OPT-API-002 | 2026-07-17 |  |
| docs/reports/domain-account-email-uniqueness-audit.md | active | audit | OPT-ARC-001 | 2026-07-13 |  |
| docs/reports/domain-account-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-backfill-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-edge-reference-audit.md | active | audit | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-edge-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-node-write-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |
| docs/reports/domain-read-path-proof.md | active | proof | OPT-ARC-001 | 2026-07-16 |  |

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
| _None_ | | | | | |

## Unclassified Reports

| Report | status | lifecycle | owner_task | review_after | findings |
| --- | --- | --- | --- | --- | --- |
| docs/reports/domain-provider-role-finding.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/inwx-zone-reconciliation-plan.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/map-architekturkritik.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/map-basemap-proof-gap-reconciliation.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/optimierungsbericht.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/passkey-register-verify-prep.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/planning-registration-findings.md | active |  |  |  | missing_lifecycle, missing_lifecycle_state, missing_review_after |

## Reports With Findings

| Report | lifecycle_state | status | findings |
| --- | --- | --- | --- |
| docs/reports/domain-provider-role-finding.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/inwx-zone-reconciliation-plan.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/map-architekturkritik.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/map-basemap-proof-gap-reconciliation.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/optimierungsbericht.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/passkey-register-verify-prep.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |
| docs/reports/planning-registration-findings.md |  | active | missing_lifecycle, missing_lifecycle_state, missing_review_after |

## Non-Report Files Under docs/reports

| File | doc_type | status |
| --- | --- | --- |
| docs/reports/agent-readiness-audit.md | documentation | active |
| docs/reports/auth-status-matrix.md | reference | active |
| docs/reports/cost-report.md | reference | active |
| docs/reports/map-status-matrix.md | status-matrix | active |
| docs/reports/optimierungsstatus.md | status-matrix | active |

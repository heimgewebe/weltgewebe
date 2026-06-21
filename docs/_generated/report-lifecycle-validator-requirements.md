---
id: docs.generated.report-lifecycle-validator-requirements
title: Report Lifecycle Validator Requirements
doc_type: generated
status: active
canonicality: derived
summary: Automatisch generierte Sicht auf fehlende Felder nach den aktuell implementierten Report-Lifecycle-Validatorregeln.
---
# Report Lifecycle Validator Requirements

Generated automatically. Do not edit manually.

This artifact reports fields missing under the currently implemented
report-lifecycle validator rules. It is distinct from the presence-only
inventory in `docs/_generated/report-lifecycle-inventory.md`.

The shared requirements are not the complete normative lifecycle policy and
do not replace future enum, date, owner, or relation checks.

## Summary

| Metric | Count |
| --- | ---: |
| reports_checked | 23 |
| reports_with_validator_required_missing_fields | 8 |
| reports_without_validator_required_missing_fields | 15 |
| validator_required_missing_fields_total | 24 |

## Reports With Missing Required Fields

| Path | status | lifecycle_state | Missing required fields |
| --- | --- | --- | --- |
| docs/reports/cost-report.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/domain-provider-role-finding.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/domain-runtime-data-source-reconciliation.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/inwx-zone-reconciliation-plan.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/map-architekturkritik.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/map-basemap-proof-gap-reconciliation.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/optimierungsbericht.md | active |  | lifecycle_state, lifecycle, review_after |
| docs/reports/passkey-register-verify-prep.md | active |  | lifecycle_state, lifecycle, review_after |

## Complete Reports

Reports without missing validator-required fields: 15.

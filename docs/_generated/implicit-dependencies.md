---
id: docs.generated.implicit-dependencies
title: Implicit Dependencies
doc_type: generated
status: active
summary: Heuristische Karte impliziter Abhängigkeiten.
---

## Weltgewebe Implicit Dependencies

Generated automatically. Do not edit.

> **Note:** This report uses Makefile-based heuristic inference to identify script execution dependencies. Documentation status validation is not yet fully automated here.

| Source | Inferred Dependency | Evidence | Documented |
| --- | --- | --- | --- |
| Makefile (validate-tests) | unittest | `python3 -m unittest discover scripts/docmeta/tests/` | *unclear* |
| Makefile (validate-tests) | unittest | `python3 -m unittest discover scripts/agent/tests/` | *unclear* |
| Makefile (validate-tests) | scripts.docmeta.generate_claim_evidence_map | `python3 -m scripts.docmeta.generate_claim_evidence_map --check` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.validate_schema | `python3 -m scripts.docmeta.validate_schema` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.validate_relations | `python3 -m scripts.docmeta.validate_relations` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.check_repo_index_consistency | `python3 -m scripts.docmeta.check_repo_index_consistency` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.check_doc_review_age | `python3 -m scripts.docmeta.check_doc_review_age` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.review_impact | `python3 -m scripts.docmeta.review_impact` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.validate_opt_arc_001_db_proof_matrix | `python3 -m scripts.docmeta.validate_opt_arc_001_db_proof_matrix` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.export_docs_index | `python3 -m scripts.docmeta.export_docs_index` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.generate_audit_gaps | `python3 -m scripts.docmeta.generate_audit_gaps` | *unclear* |
| Makefile (validate-core) | scripts.docmeta.check_links | `python3 -m scripts.docmeta.check_links` | *unclear* |
| Makefile (generate-system-map) | scripts.docmeta.generate_system_map | `python3 -m scripts.docmeta.generate_system_map` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/repo-structure-guard.sh | `bash scripts/docmeta/repo-structure-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/docs-relations-guard.sh | `bash scripts/docmeta/docs-relations-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/generated-files-guard.sh | `bash scripts/docmeta/generated-files-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/coverage-guard.sh | `bash scripts/docmeta/coverage-guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_weltgewebe_up_git_branch.sh | `bash scripts/tests/test_weltgewebe_up_git_branch.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_version_guard.sh | `bash scripts/tests/test_version_guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_basemap_mode_guard.sh | `bash scripts/tests/test_basemap_mode_guard.sh` | *unclear* |
| Makefile (generate) | scripts/docmeta/generate-doc-index.sh | `bash scripts/docmeta/generate-doc-index.sh` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_backlinks | `python3 -m scripts.docmeta.generate_backlinks` | *unclear* |
| Makefile (generate) | scripts/docmeta/generate-impl-index.sh | `bash scripts/docmeta/generate-impl-index.sh` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_orphans | `python3 -m scripts.docmeta.generate_orphans` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_supersession_map | `python3 -m scripts.docmeta.generate_supersession_map` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_system_map | `python3 -m scripts.docmeta.generate_system_map` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_architecture_drift | `python3 -m scripts.docmeta.generate_architecture_drift` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_doc_coverage | `python3 -m scripts.docmeta.generate_doc_coverage` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_knowledge_gaps | `python3 -m scripts.docmeta.generate_knowledge_gaps` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_implicit_dependencies | `python3 -m scripts.docmeta.generate_implicit_dependencies` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_change_resonance | `python3 -m scripts.docmeta.generate_change_resonance` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_staleness_report | `python3 -m scripts.docmeta.generate_staleness_report` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_agent_readiness | `python3 -m scripts.docmeta.generate_agent_readiness` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_claim_evidence_map | `python3 -m scripts.docmeta.generate_claim_evidence_map` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_relations_analysis | `python3 -m scripts.docmeta.generate_relations_analysis` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_relates_to_audit | `python3 -m scripts.docmeta.generate_relates_to_audit` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_report_lifecycle_inventory | `python3 -m scripts.docmeta.generate_report_lifecycle_inventory` | *unclear* |
| Makefile (generate) | scripts.docmeta.generate_report_lifecycle | `python3 -m scripts.docmeta.generate_report_lifecycle` | *unclear* |

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
| Makefile (validate-tests) | unittest | `$(CI_TEST_GIT_ENV) python3 -m unittest discover scripts/ci/tests/` | *unclear* |
| Makefile (validate-tests) | pytest | `python3 -m pytest -q scripts/ci/tests/test_semantic_search_production_activation.py` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/repo-structure-guard.sh | `bash scripts/docmeta/repo-structure-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/docs-relations-guard.sh | `bash scripts/docmeta/docs-relations-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/generated-files-guard.sh | `bash scripts/docmeta/generated-files-guard.sh` | *unclear* |
| Makefile (validate-guards) | scripts/docmeta/coverage-guard.sh | `bash scripts/docmeta/coverage-guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_weltgewebe_up_git_branch.sh | `bash scripts/tests/test_weltgewebe_up_git_branch.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_weltgewebe_up_frontend_required.sh | `bash scripts/tests/test_weltgewebe_up_frontend_required.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_weltgewebe_up_deploy_scope.sh | `bash scripts/tests/test_weltgewebe_up_deploy_scope.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_version_guard.sh | `bash scripts/tests/test_version_guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_basemap_mode_guard.sh | `bash scripts/tests/test_basemap_mode_guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_basemap_runtime_proof_contract.sh | `bash scripts/tests/test_basemap_runtime_proof_contract.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_security_headers_guard.sh | `bash scripts/tests/test_security_headers_guard.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_repo_contract_guards.sh | `bash scripts/tests/test_repo_contract_guards.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_postgres_backup_restore_contract.sh | `bash scripts/tests/test_postgres_backup_restore_contract.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_offhost_backup_pull_contract.sh | `bash scripts/tests/test_offhost_backup_pull_contract.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_web_artifact_install_contract.sh | `bash scripts/tests/test_web_artifact_install_contract.sh` | *unclear* |
| Makefile (validate-shell-tests) | scripts/tests/test_api_release_identity_contract.sh | `bash scripts/tests/test_api_release_identity_contract.sh` | *unclear* |
| Makefile (generate) | scripts/docmeta/generate-doc-index.sh | `bash scripts/docmeta/generate-doc-index.sh` | *unclear* |
| Makefile (generate) | scripts/docmeta/generate-impl-index.sh | `bash scripts/docmeta/generate-impl-index.sh` | *unclear* |

# SYSTEM_MAP

## Zone: norm

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|freshness_status|missing_scripts|
|---|---|---|---|---|---|---|---|---|---|
|docmeta.schema|architecture/docmeta.schema.md|norm|docmeta|canonical|2026-02-28||scripts/docmeta/check_doc_review_age.py, scripts/docmeta/check_repo_index_consistency.py, scripts/docmeta/generate_system_map.py|pass||
|overview|architecture/overview.md|norm|governance|canonical|2026-02-28|||pass||
|security|architecture/security.md|norm|governance|canonical|2026-02-28|||pass||

## Zone: reality

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|freshness_status|missing_scripts|
|---|---|---|---|---|---|---|---|---|---|
|runtime.readme|runtime/README.md|reality|runtime|canonical|2026-02-28|||pass||

## Zone: runbooks

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|freshness_status|missing_scripts|
|---|---|---|---|---|---|---|---|---|---|
|runbooks.readme|runbooks/README.md|runbooks|ops|canonical|2026-02-28|||pass||

## Automated Checks

- scripts/docmeta/check_doc_review_age.py
- scripts/docmeta/check_repo_index_consistency.py
- scripts/docmeta/generate_system_map.py

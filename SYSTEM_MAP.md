# SYSTEM_MAP

## Zone: norm

|ID|File|Organ|Status|Last Reviewed|Depends On|Verifies With|
|---|---|---|---|---|---|---|
|docmeta.schema|architecture/docmeta.schema.md|docmeta|canonical|2026-02-28||scripts/docmeta/check_doc_review_age.py, scripts/docmeta/check_repo_index_consistency.py, scripts/docmeta/generate_system_map.py|
|overview|architecture/overview.md|governance|canonical|2026-02-28|||
|security|architecture/security.md|governance|canonical|2026-02-28|||

## Zone: reality

|ID|File|Organ|Status|Last Reviewed|Depends On|Verifies With|
|---|---|---|---|---|---|---|
|runtime.readme|runtime/README.md|runtime|canonical|2026-02-28|||

## Zone: runbooks

|ID|File|Organ|Status|Last Reviewed|Depends On|Verifies With|
|---|---|---|---|---|---|---|
|runbooks.readme|runbooks/README.md|ops|canonical|2026-02-28|||

## Automated Checks

- scripts/docmeta/check_doc_review_age.py
- scripts/docmeta/check_repo_index_consistency.py
- scripts/docmeta/generate_system_map.py

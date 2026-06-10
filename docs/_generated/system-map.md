---
id: docs.generated.system-map
title: System Map
doc_type: generated
status: active
summary: Automatisch generierte System Map.
---
## Weltgewebe System Map

Generated automatically. Do not edit.

Source: scripts/docmeta/generate_system_map.py

## Zone: norm

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|blueprint.docmeta-engine|architecture/blueprint.docmeta-engine.md|norm|governance|canonical|2026-06-09||||
|docmeta.schema|architecture/docmeta.schema.md|norm|docmeta|canonical|2026-06-09||scripts/docmeta/check_doc_review_age.py, scripts/docmeta/check_repo_index_consistency.py, scripts/docmeta/generate_system_map.py, scripts/docmeta/validate_relations.py||
|overview|architecture/overview.md|norm|governance|canonical|2026-06-09||||
|security|architecture/security.md|norm|governance|canonical|2026-06-09||||

## Zone: reality

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|runtime.readme|runtime/README.md|reality|runtime|canonical|2026-06-09||||

## Zone: runbooks

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|runbooks.readme|runbooks/README.md|runbooks|ops|canonical|2026-06-09||||

## Automated Checks

- scripts/docmeta/check_doc_review_age.py
- scripts/docmeta/check_repo_index_consistency.py
- scripts/docmeta/generate_system_map.py

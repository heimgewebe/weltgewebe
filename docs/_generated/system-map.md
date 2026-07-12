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
|docmeta.schema|architecture/docmeta.schema.md|norm|docmeta|canonical|2026-06-09||scripts/docmeta/check_doc_review_age.py, scripts/docmeta/check_repo_index_consistency.py, scripts/docmeta/generate_system_map.py, scripts/docmeta/validate_relations.py||
|overview|architecture/overview.md|norm|governance|canonical|2026-07-11||||
|security|architecture/security.md|norm|governance|canonical|2026-07-11||||

## Zone: policy

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|docs.policies.agent-reading-protocol|docs/policies/agent-reading-protocol.md|norm|governance|canonical|2026-07-11||||
|docs.policies.architecture-critique|docs/policies/architecture-critique.md|norm|governance|canonical|2026-07-11||||

## Zone: product

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|specs.garnrolle-knoten-faden|docs/specs/garnrolle-knoten-faden.md|norm|product-domain|canonical|2026-07-11||apps/web/tests/garnrolle-self-service.spec.ts, apps/web/tests/komposition.spec.ts, contracts/domain/account.schema.json, contracts/domain/edge.schema.json, contracts/domain/node.schema.json||
|specs.map-experience|docs/specs/map-experience.md|norm|product-map|canonical|2026-07-11|specs.ui-interaction, specs.ui-state-machine, specs.garnrolle-knoten-faden|apps/web/src/lib/map/scene.ts, apps/web/src/lib/map/types.ts, apps/web/src/routes/map/+page.svelte, apps/web/src/routes/map/+page.ts, apps/web/tests/edge-visibility.spec.ts, apps/web/tests/map-load-fallback.spec.ts, apps/web/tests/map-url-state.spec.ts||
|specs.ui-interaction|docs/specs/ui-interaction.md|norm|product-ui|canonical|2026-07-11|specs.ui-state-machine, specs.garnrolle-knoten-faden|apps/web/src/lib/components/ActionBar.svelte, apps/web/src/lib/components/ContextPanel.svelte, apps/web/src/lib/components/FilterOverlay.svelte, apps/web/src/lib/components/SearchOverlay.svelte, apps/web/tests/map-interaction.spec.ts, apps/web/tests/ui-filter.spec.ts||
|specs.ui-state-machine|docs/specs/ui-state-machine.md|norm|product-ui|canonical|2026-07-11||apps/web/src/lib/stores/uiInvariants.test.ts, apps/web/src/lib/stores/uiInvariants.ts, apps/web/src/lib/stores/uiView.ts||

## Zone: reality

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|runtime.readme|runtime/README.md|reality|runtime|canonical|2026-07-12||||

## Zone: runbooks

|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|
|---|---|---|---|---|---|---|---|---|
|runbooks.readme|runbooks/README.md|runbooks|ops|canonical|2026-07-11||||

## Automated Checks

- scripts/docmeta/check_doc_review_age.py
- scripts/docmeta/check_repo_index_consistency.py
- scripts/docmeta/generate_system_map.py

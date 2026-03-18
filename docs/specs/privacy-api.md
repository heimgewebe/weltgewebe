---
id: specs.privacy-api
title: Privacy Api
doc_type: reference
status: active
canonicality: derived
summary: Automatisch hinzugefügtes Frontmatter.
---
# Privacy API (ADR-0003)

GET/PUT /me/visibility { radius_m } für verortete Garnrollen.
Das Modell nutzt `mode: "verortet" | "ron"` als basalen Identitätsmodus anstelle eines nachträglichen RoN-Toggles oder visibility-Flags (`private`/`approximate`/`public`).
View: public_role_view (id, public_pos, mode, radius_m).

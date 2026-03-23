---
id: specs.privacy-api
title: Privacy API
doc_type: reference
status: active
summary: API-Spezifikation für datenschutzrelevante Endpunkte.
relations:
  - type: relates_to
    target: docs/specs/privacy-ui.md
  - type: relates_to
    target: docs/konzepte/garnrolle-und-verortung.md
---
# Privacy API (ADR-0003)

GET/PUT /me/visibility { radius_m } für verortete Garnrollen.
Das Modell nutzt `mode: "verortet" | "ron"` als basalen Identitätsmodus anstelle eines nachträglichen RoN-Toggles oder visibility-Flags (`private`/`approximate`/`public`).
View: public_role_view (id, public_pos, mode, radius_m).
Bei `mode=ron` bleibt `public_pos` im individuellen Account leer (None); die spätere öffentliche Wirksamkeit/Projektion erfolgt kollektiv über die Rolle ohne Namen des Stadtteils.

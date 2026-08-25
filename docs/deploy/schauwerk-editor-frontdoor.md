---
id: deploy.schauwerk-editor-frontdoor
title: Schauwerk Editor Frontdoor
doc_type: runbook
status: active
summary: Delivery contract for the separately versioned Schauwerk editor at the shared Weltgewebe HTTPS edge.
relations:
  - type: relates_to
    target: infra/caddy/Caddyfile.vps
  - type: relates_to
    target: infra/compose/compose.vps.override.yml
  - type: relates_to
    target: docs/deploy/vps.md
---
# Schauwerk editor frontdoor

The public product entry point is `https://weltgewebe.net/schaubild/`. Weltgewebe
provides only the shared HTTPS frontdoor. The editor itself remains a separately
versioned Schauwerk static release and is not copied into the Weltgewebe web build.

## Runtime boundary

The VPS stores Schauwerk releases below `/opt/schauwerk-editor` by default:

```text
/opt/schauwerk-editor/
├── current -> releases/<schauwerk-commit>
└── releases/
    └── <schauwerk-commit>/
        ├── app.js
        ├── canvas-import.js
        ├── index.html
        ├── manifest.json
        └── styles.css
```

`infra/compose/compose.vps.override.yml` binds the host root into Caddy at
`/srv/schauwerk-editor-root` read-only. `SCHAUWERK_EDITOR_ROOT` may override the
host root deliberately. The bind uses `create_host_path: false`: a missing release
root must fail the deployment instead of silently creating an empty directory.

The production Caddy contract is intentionally narrow:

- `/schaubild` redirects once to `/schaubild/`;
- `/schaubild/*` is served only from `/srv/schauwerk-editor-root/current`;
- responses use `Cache-Control: no-store` so switching `current` cannot leave a
  stale product shell in browser or intermediary caches;
- the path-specific CSP allows local shell assets and exactly
  `frame-src https://embed.diagrams.net`; the ordinary Weltgewebe frontend CSP
  remains responsible for every other non-API route.

The embedded diagrams.net runtime is therefore still a network dependency. Serving
the Schauwerk shell successfully does not establish offline completeness or a
self-hosted editor engine.

## Release admission

Provision and verify the Schauwerk release **before** deploying a Weltgewebe
revision that contains this bind mount. The normal full VPS path in
`scripts/weltgewebe-up` enforces this release contract before build or container
mutation; bounded `api` and `migration` deployments intentionally do not own this
edge dependency. At minimum, verify all of the following:

1. the release directory is a real directory, not a symlink;
2. `current` is a relative symlink of the form `releases/<schauwerk-commit>`;
   absolute host paths are rejected because the release tree is mounted at a
   different path inside Caddy;
3. `manifest.json` uses `schauwerk-standalone-editor-manifest.v1`;
4. the manifest `editor_origin` equals the Caddy CSP origin;
5. every asset digest listed in the manifest matches the installed file;
6. the transport artifact digest is checked before extraction.

Do not weaken the Schauwerk development server from loopback-only as a deployment
shortcut. Public delivery belongs at this explicit HTTPS edge boundary.

## Post-deploy readback

After the normal exact-commit Weltgewebe deployment, read back the public edge:

```bash
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  https://weltgewebe.net/schaubild
curl -fsSI https://weltgewebe.net/schaubild/
curl -fsS https://weltgewebe.net/schaubild/manifest.json
curl -fsS https://weltgewebe.net/health/proxy
```

Expected evidence:

- `/schaubild` returns `308` to `/schaubild/`;
- `/schaubild/` returns `200` with `Cache-Control: no-store`;
- its CSP contains exactly the intended diagrams.net `frame-src` allowance and
  does not add that allowance to ordinary Weltgewebe frontend responses;
- the public manifest matches the pre-provisioned Schauwerk release identity;
- existing Weltgewebe health and representative frontend/API routes remain healthy.

A successful HTTP readback proves delivery of the static shell and edge policy. It
does **not** by itself prove Safari touch behavior, diagrams.net interaction,
Mermaid/Canvas editing, export behavior or other real-device acceptance.

## Rollback

Keep release directories immutable during an incident. Do not delete the active or
previous release as a first response.

If the shared edge change causes a Weltgewebe regression, use the existing
exact-revision production rollback/deployment path to restore the prior Weltgewebe
revision; the separate `/opt/schauwerk-editor` tree may remain in place because an
older edge revision does not reference it.

If only the Schauwerk release must be rolled back and a verified previous release is
present, atomically repoint `current` to that exact release and repeat the public
manifest, CSP and route readback. Never repoint `current` to an unverified working
directory or mutable checkout.

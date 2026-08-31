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

The public product entry point is `https://commonthing.net/schaubild/`. Weltgewebe
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

`infra/compose/compose.vps.override.yml` uses a two-phase bind contract. The
first, discovery-only Compose render resolves `${SCHAUWERK_EDITOR_ROOT}/current`;
no container effect may use that render. `scripts/weltgewebe-up` then verifies the
repository-owned release lock, resolves the canonical `releases/<schauwerk-commit>`
directory and exports that exact path as `SCHAUWERK_EDITOR_RELEASE_DIR`. Every
subsequent Compose render binds only that admitted directory at
`/srv/schauwerk-editor-release` read-only. The bind uses `create_host_path: false`,
so a missing admitted release fails instead of creating an empty directory.

The production Caddy contract is intentionally narrow:

- `/schaubild` redirects once to `/schaubild/`;
- `/schaubild/*` is served only from `/srv/schauwerk-editor-release`; Caddy has
  no live `/current` reference after admission;
- responses use `Cache-Control: no-store` so a release cutover cannot leave a stale
  product shell in browser or intermediary caches;
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

1. `infra/schauwerk-editor/release-lock.json` is a regular file outside the
   release tree and binds `heimgewebe/schauwerk`, the exact 40-hex source commit,
   the identical release-directory id and the SHA-256 of the raw `manifest.json`
   bytes;
2. the release directory is a real direct child of the configured release collection, not a symlink;
3. `current` is a relative symlink of the form `releases/<schauwerk-commit>` and
   names exactly the commit in the reviewed lock;
4. the raw `manifest.json` SHA-256 equals the independent lock before its JSON is
   trusted; a coherently replaced manifest plus assets or a formatting-only
   manifest rewrite therefore requires a reviewed lock update;
5. the release directory contains exactly `manifest.json`, `app.js`,
   `canvas-import.js`, `index.html` and `styles.css`, all as regular files; extra
   files, directories or symlinks are rejected;
6. `manifest.json` uses `schauwerk-standalone-editor-manifest.v1`, its
   `editor_origin` equals the Caddy CSP origin, and every listed asset digest
   matches the installed file;
7. the provisioning path still verifies the transport artifact digest before
   extraction. The repository lock does not replace transport integrity; it binds
   the admitted bytes to reviewed source identity.

Do not weaken the Schauwerk development server from loopback-only as a deployment
shortcut. Public delivery belongs at this explicit HTTPS edge boundary.

## Post-deploy readback

The normal full VPS deployment must not record its source state until it has read
`/schaubild/` and `manifest.json` back through the freshly deployed Caddy listener.
That bounded local-direct readback bypasses proxy environment variables, resolves
`commonthing.net` to the selected `CADDY_BIND`, requires `200` plus `no-store` for
the editor index, and requires the served manifest SHA-256 to equal the lock-bound
preflight digest. The running Caddy mount must resolve to the same exact admitted
release directory; retargeting host `current` after admission cannot change the
bytes served by that container.

The production reconciler uses the same raw manifest SHA-256 as part of its
same-commit no-op decision. A matching commonThing frontend/API commit is therefore
insufficient when `/schaubild/manifest.json` still belongs to another reviewed
Schauwerk release: that state requires a full exact-revision redeploy so Caddy is
recreated with the lock-bound release. The exact-commit helper also replaces the
web build directory before the full compose pass. Because a Linux bind mount may
stay attached to the removed directory inode, the VPS full-deploy path performs a
targeted `--no-deps --force-recreate caddy` after the normal compose convergence.
This refreshes the web and Schauwerk bind mounts without deliberately recreating
PostgreSQL, NATS, or API dependencies. The reconciler repeats the public identity
checks after deployment before it may record the revision as verified.

After that exact-commit deployment succeeds, read back the public edge as well:

```bash
curl -sS -o /dev/null -w '%{http_code} %{redirect_url}\n' \
  https://commonthing.net/schaubild
curl -fsSI https://commonthing.net/schaubild/
curl -fsS https://commonthing.net/schaubild/manifest.json
curl -fsS https://api.weltgewebe.net/health/proxy
```

Expected evidence:

- `/schaubild` returns `308` to `/schaubild/`;
- `/schaubild/` returns `200` with `Cache-Control: no-store`;
- its CSP contains exactly the intended diagrams.net `frame-src` allowance and
  does not add that allowance to ordinary Weltgewebe frontend responses;
- the public manifest matches the pre-provisioned Schauwerk release identity;
- the canonical commonThing frontend and the preserved Weltgewebe API host remain healthy.

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

If only the Schauwerk release must be rolled back, a `current` relink alone is no
longer a live cutover mechanism. Select a verified previous release, update
`infra/schauwerk-editor/release-lock.json` to its reviewed source commit and raw
manifest SHA-256, atomically repoint `current` to the same release, and run the
normal full exact-revision deployment so Caddy is recreated with that exact bind.
Then repeat manifest, asset, CSP and route readback. Never point the lock or
`current` at an unverified working directory or mutable checkout.

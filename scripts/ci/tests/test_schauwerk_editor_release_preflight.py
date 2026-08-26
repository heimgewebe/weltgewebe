from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "preflight" / "schauwerk_editor_release.py"
SPEC = importlib.util.spec_from_file_location("schauwerk_editor_release", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _write_release(root: Path, *, release_name: str = "abc123") -> Path:
    release = root / "releases" / release_name
    release.mkdir(parents=True)
    payloads = {
        "app.js": b"console.log('ok');\n",
        "canvas-import.js": b"export const ok = true;\n",
        "index.html": b"<!doctype html><title>Schaubild</title>\n",
        "styles.css": b"body { margin: 0; }\n",
    }
    files = []
    for name, payload in payloads.items():
        (release / name).write_bytes(payload)
        files.append({"path": name, "sha256": hashlib.sha256(payload).hexdigest()})
    (release / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": MODULE.MANIFEST_SCHEMA,
                "editor_origin": MODULE.EDITOR_ORIGIN,
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    (root / "current").symlink_to(Path("releases") / release_name)
    return release


def test_valid_release_passes(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    result = MODULE.verify_release(root)
    assert result["release"] == release.name
    assert result["editor_origin"] == MODULE.EDITOR_ORIGIN


@pytest.mark.parametrize(
    "mutation",
    [
        "broken-current",
        "absolute-current",
        "symlink-release",
        "extra-file",
        "extra-symlink",
        "extra-directory",
        "missing-index",
        "wrong-origin",
        "digest-drift",
    ],
)
def test_release_failures_are_closed(tmp_path: Path, mutation: str) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    if mutation == "broken-current":
        (root / "current").unlink()
        (root / "current").symlink_to("releases/missing")
    elif mutation == "absolute-current":
        (root / "current").unlink()
        (root / "current").symlink_to(release.resolve())
    elif mutation == "symlink-release":
        real_release = release.with_name("real")
        release.rename(real_release)
        release.symlink_to(real_release.name, target_is_directory=True)
    elif mutation == "extra-file":
        (release / ".env").write_text("unverified fixture\n", encoding="utf-8")
    elif mutation == "extra-symlink":
        (release / "leak").symlink_to("/etc/passwd")
    elif mutation == "extra-directory":
        (release / "backup").mkdir()
    elif mutation == "missing-index":
        (release / "index.html").unlink()
    elif mutation == "wrong-origin":
        manifest = json.loads((release / "manifest.json").read_text(encoding="utf-8"))
        manifest["editor_origin"] = "https://example.invalid"
        (release / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    elif mutation == "digest-drift":
        (release / "app.js").write_text("changed\n", encoding="utf-8")
    with pytest.raises(MODULE.ReleaseContractError):
        MODULE.verify_release(root)


def test_current_must_not_escape_releases(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "releases").mkdir(parents=True)
    (root / "current").symlink_to(outside)
    with pytest.raises(MODULE.ReleaseContractError, match="relative releases/<release> target"):
        MODULE.verify_release(root)


def test_vps_deploy_resolves_and_verifies_configured_editor_mount_before_build() -> None:
    repo = Path(__file__).resolve().parents[3]
    deploy = (repo / "scripts" / "weltgewebe-up").read_text(encoding="utf-8")
    compose_check = deploy.index('if ! docker compose "${BASE_ARGS[@]}" config > /dev/null; then')
    full_scope_guard = deploy.index(
        'if [[ "$DEPLOY_TARGET" == "vps" && "$DEPLOY_SCOPE" == "full" ]]; then',
        compose_check,
    )
    mount_target = deploy.index('v.get("target") == "/srv/schauwerk-editor-root"')
    mount_contract = deploy.index('mount.get("read_only") is not True')
    helper_call = deploy.index('python3 scripts/preflight/schauwerk_editor_release.py --root "$SCHAUWERK_EDITOR_HOST_ROOT"')
    build_decision = deploy.index('# 4. Build Decision')
    deploying = deploy.index('echo ">> Deploying..."', build_decision)

    assert compose_check < full_scope_guard < mount_target < mount_contract < helper_call < build_decision < deploying
    assert 'bind.get("create_host_path") is not False' in deploy
    assert 'generate_failure_bundle "$msg"' in deploy[mount_target:build_decision]


def test_full_vps_deploy_reads_back_editor_through_caddy_before_state_commit() -> None:
    repo = Path(__file__).resolve().parents[3]
    deploy = (repo / "scripts" / "weltgewebe-up").read_text(encoding="utf-8")

    preflight_digest = deploy.index('SCHAUWERK_EDITOR_EXPECTED_MANIFEST_SHA="${BASH_REMATCH[1]}"')
    deploying = deploy.index('echo ">> Deploying..."')
    postflight_scope = deploy.index(
        'if [[ "$DEPLOY_SCOPE" == "full" && "$SCHAUWERK_EDITOR_POSTFLIGHT_REQUIRED" == "1" ]]; then',
        deploying,
    )
    resolve = deploy.index('SCHAUWERK_RESOLVE="commonthing.net:443:${CADDY_BIND}"', postflight_scope)
    expected_csp = deploy.index('SCHAUWERK_EXPECTED_CSP="default-src', resolve)
    index_url = deploy.index('https://commonthing.net/schaubild/', expected_csp)
    csp_compare = deploy.index('if values != [expected]:', index_url)
    manifest_url = deploy.index('https://commonthing.net/schaubild/manifest.json', csp_compare)
    digest_compare = deploy.index('SCHAUWERK_LIVE_MANIFEST_SHA', manifest_url)
    asset_bindings = deploy.index('SCHAUWERK_ASSET_BINDINGS', digest_compare)
    asset_url = deploy.index('https://commonthing.net/schaubild/${SCHAUWERK_ASSET_NAME}', asset_bindings)
    asset_digest = deploy.index('SCHAUWERK_ASSET_LIVE_SHA', asset_url)
    state_commit = deploy.index('# 8. Update State (Post-Health)')

    assert (
        preflight_digest
        < deploying
        < postflight_scope
        < resolve
        < expected_csp
        < index_url
        < csp_compare
        < manifest_url
        < digest_compare
        < asset_bindings
        < asset_url
        < asset_digest
        < state_commit
    )
    postflight = deploy[postflight_scope:state_commit]
    assert 'SCHAUWERK_EDITOR_POSTFLIGHT_REQUIRED="0"' in deploy[:deploying]
    assert 'SCHAUWERK_EDITOR_POSTFLIGHT_REQUIRED="1"' in deploy[:deploying]
    assert "--noproxy '*'" in postflight
    assert '--resolve "$SCHAUWERK_RESOLVE"' in postflight
    assert 'Cache-Control: no-store' in postflight
    expected_policy = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
        "frame-src https://embed.diagrams.net; connect-src 'none'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
    )
    caddy = (repo / "infra" / "caddy" / "Caddyfile.vps").read_text(encoding="utf-8")
    assert f'SCHAUWERK_EXPECTED_CSP="{expected_policy}"' in postflight
    assert f'>Content-Security-Policy "{expected_policy}"' in caddy
    assert 'values != [expected]' in postflight
    assert 'SCHAUWERK_LIVE_MANIFEST_SHA" != "$SCHAUWERK_EDITOR_EXPECTED_MANIFEST_SHA' in postflight
    assert 'SCHAUWERK_ASSET_LIVE_SHA" != "$SCHAUWERK_ASSET_EXPECTED_SHA' in postflight
    assert 'SCHAUWERK_ASSET_COUNT" != "4"' in postflight

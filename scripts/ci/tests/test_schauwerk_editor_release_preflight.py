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

DEFAULT_RELEASE = "a" * 40
SECOND_RELEASE = "b" * 40


def _write_release(
    root: Path, *, release_name: str = DEFAULT_RELEASE, point_current: bool = True
) -> Path:
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
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    if point_current:
        current = root / "current"
        if current.exists() or current.is_symlink():
            current.unlink()
        current.symlink_to(Path("releases") / release_name)
    return release


def _write_lock(root: Path, release: Path, *, path: Path | None = None) -> Path:
    lock = path or (root.parent / "release-lock.json")
    lock.write_text(
        json.dumps(
            {
                "schema_version": MODULE.LOCK_SCHEMA,
                "source_repository": MODULE.SOURCE_REPOSITORY,
                "source_commit": release.name,
                "release_id": release.name,
                "manifest_file_sha256": hashlib.sha256(
                    (release / "manifest.json").read_bytes()
                ).hexdigest(),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return lock


def test_valid_release_passes(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    lock = _write_lock(root, release)
    result = MODULE.verify_release(root, lock)
    assert result["release"] == release.name
    assert result["release_path"] == str(release.resolve())
    assert result["source_commit"] == release.name
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
    lock = _write_lock(root, release)
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
        MODULE.verify_release(root, lock)


def test_current_must_not_escape_releases(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "releases").mkdir(parents=True)
    (root / "current").symlink_to(outside)
    lock = tmp_path / "release-lock.json"
    lock.write_text(
        json.dumps(
            {
                "schema_version": MODULE.LOCK_SCHEMA,
                "source_repository": MODULE.SOURCE_REPOSITORY,
                "source_commit": DEFAULT_RELEASE,
                "release_id": DEFAULT_RELEASE,
                "manifest_file_sha256": "0" * 64,
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(MODULE.ReleaseContractError, match="relative releases/<release> target"):
        MODULE.verify_release(root, lock)


def test_coherent_manifest_and_asset_replacement_fails_external_lock(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    lock = _write_lock(root, release)
    replacement = b"console.log('coherently replaced');\n"
    (release / "app.js").write_bytes(replacement)
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for item in manifest["files"]:
        if item["path"] == "app.js":
            item["sha256"] = hashlib.sha256(replacement).hexdigest()
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")
    with pytest.raises(MODULE.ReleaseContractError, match="reviewed release lock"):
        MODULE.verify_release(root, lock)


def test_manifest_reformat_fails_raw_byte_lock(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    lock = _write_lock(root, release)
    manifest_path = release / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest, indent=4) + "\n", encoding="utf-8")
    with pytest.raises(MODULE.ReleaseContractError, match="reviewed release lock"):
        MODULE.verify_release(root, lock)


def test_current_retarget_to_other_valid_release_fails_lock(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    lock = _write_lock(root, release)
    _write_release(root, release_name=SECOND_RELEASE, point_current=False)
    (root / "current").unlink()
    (root / "current").symlink_to(Path("releases") / SECOND_RELEASE)
    with pytest.raises(MODULE.ReleaseContractError, match="reviewed release lock"):
        MODULE.verify_release(root, lock)


def test_lock_must_live_outside_release_root_and_not_be_symlink(tmp_path: Path) -> None:
    root = tmp_path / "editor"
    release = _write_release(root)
    external = _write_lock(root, release)
    internal = _write_lock(root, release, path=root / "release-lock.json")
    with pytest.raises(MODULE.ReleaseContractError, match="outside the release root"):
        MODULE.verify_release(root, internal)
    internal.unlink()
    internal.symlink_to(external)
    with pytest.raises(MODULE.ReleaseContractError, match="missing or unsafe"):
        MODULE.verify_release(root, internal)


def test_vps_deploy_admits_and_pins_exact_editor_release_before_build() -> None:
    repo = Path(__file__).resolve().parents[3]
    deploy = (repo / "scripts" / "weltgewebe-up").read_text(encoding="utf-8")
    discovery_override = deploy.index('export SCHAUWERK_EDITOR_RELEASE_DIR=""')
    compose_check = deploy.index('if ! docker compose "${BASE_ARGS[@]}" config > /dev/null; then')
    mount_target = deploy.index('v.get("target") == "/srv/schauwerk-editor-release"')
    pointer_guard = deploy.index('pointer.name != "current"')
    lock_path = deploy.index('infra/schauwerk-editor/release-lock.json')
    helper_call = deploy.index('scripts/preflight/schauwerk_editor_release.py')
    exact_export = deploy.index('export SCHAUWERK_EDITOR_RELEASE_DIR="$SCHAUWERK_EDITOR_RELEASE_PATH"')
    authoritative_mount = deploy.index('mount.get("source") != expected', exact_export)
    build_decision = deploy.index('# 4. Build Decision')
    runtime_preflight = deploy.index('echo ">> Preflight: Validating runtime contract..."', build_decision)
    csp_preflight = deploy.index('echo ">> Preflight: Validating static CSP contract..."', runtime_preflight)
    csp_call = deploy.index('if ! bash scripts/preflight/csp_contract_static.sh; then', csp_preflight)
    deferred_purge = deploy.index('docker rm -f "${ZOMBIE_CONTAINER_IDS_TO_PURGE[@]}"', csp_call)
    deploying = deploy.index('echo ">> Deploying..."', deferred_purge)

    assert (
        discovery_override
        < compose_check
        < mount_target
        < pointer_guard
        < lock_path
        < helper_call
        < exact_export
        < authoritative_mount
        < build_decision
        < runtime_preflight
        < csp_preflight
        < csp_call
        < deferred_purge
        < deploying
    )
    assert 'bind.get("create_host_path") is not False' in deploy[mount_target:build_decision]
    assert '--lock "$SCHAUWERK_EDITOR_LOCK_PATH"' in deploy[mount_target:build_decision]


def test_compose_leak_purge_never_targets_external_edge_gateway() -> None:
    repo = Path(__file__).resolve().parents[3]
    deploy = (repo / "scripts" / "weltgewebe-up").read_text(encoding="utf-8")

    candidate_loop = deploy.index('while IFS= read -r container_name; do')
    edge_guard = deploy.index('if [[ "$container_name" == "$EDGE_GATEWAY_CONTAINER" ]]; then', candidate_loop)
    identity_binding = deploy.index(
        "container_id=\"$(docker inspect --format '{{.Id}}' \"$container_name\")\"",
        edge_guard,
    )
    queued_name = deploy.index('ZOMBIE_CONTAINER_NAMES_TO_PURGE+=("$container_name")', identity_binding)
    deferred_purge = deploy.index('docker rm -f "${ZOMBIE_CONTAINER_IDS_TO_PURGE[@]}"', queued_name)

    assert candidate_loop < edge_guard < identity_binding < queued_name < deferred_purge
    guard = deploy[edge_guard:identity_binding]
    assert "Refusing to auto-purge configured external edge gateway container" in guard
    assert "--purge-compose-leaks does not own EDGE_GATEWAY_CONTAINER" in guard
    assert "exit 1" in guard


def test_full_vps_deploy_reads_back_editor_through_caddy_before_state_commit() -> None:
    repo = Path(__file__).resolve().parents[3]
    deploy = (repo / "scripts" / "weltgewebe-up").read_text(encoding="utf-8")

    preflight_digest = deploy.index("SCHAUWERK_EDITOR_EXPECTED_MANIFEST_SHA")
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

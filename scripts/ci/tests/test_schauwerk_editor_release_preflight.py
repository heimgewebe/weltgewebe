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

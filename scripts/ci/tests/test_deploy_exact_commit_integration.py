from __future__ import annotations

import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[3]
DEPLOY_SCRIPT = ROOT / "scripts" / "ops" / "deploy-exact-commit-vps.sh"
RECONCILE_SCRIPT = ROOT / "scripts" / "ops" / "reconcile-production-main-vps.sh"
VALIDATOR = ROOT / "scripts" / "ops" / "validate_web_deploy_archive.py"


def run(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    effective_env = None if env is None else env.copy()
    if argv and Path(argv[0]).name == "git":
        effective_env = os.environ.copy() if effective_env is None else effective_env
        effective_env["GIT_CONFIG_GLOBAL"] = os.devnull
        effective_env["GIT_CONFIG_NOSYSTEM"] = "1"

    result = subprocess.run(
        argv,
        cwd=cwd,
        env=effective_env,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {argv!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


class GitFixtureIsolationTests(unittest.TestCase):
    def test_run_ignores_inherited_global_git_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            hooks = root / "hooks"
            hooks.mkdir()
            pre_push = hooks / "pre-push"
            pre_push.write_text("#!/bin/sh\nexit 99\n", encoding="utf-8")
            pre_push.chmod(0o755)
            global_config = root / "global.gitconfig"
            global_config.write_text(
                f"[core]\n\thooksPath = {hooks}\n",
                encoding="utf-8",
            )
            remote = root / "remote.git"
            seed = root / "seed"

            with mock.patch.dict(
                os.environ,
                {
                    "GIT_CONFIG_GLOBAL": str(global_config),
                    "GIT_CONFIG_NOSYSTEM": "1",
                },
            ):
                run(["git", "init", "--bare", str(remote)])
                run(["git", "init", "-b", "main", str(seed)])
                run(["git", "config", "user.name", "Integration Test"], cwd=seed)
                run(
                    ["git", "config", "user.email", "integration@example.invalid"],
                    cwd=seed,
                )
                (seed / "fixture.txt").write_text("fixture\n", encoding="utf-8")
                run(["git", "add", "fixture.txt"], cwd=seed)
                run(["git", "commit", "-m", "fixture"], cwd=seed)
                run(["git", "remote", "add", "origin", str(remote)], cwd=seed)
                result = run(["git", "push", "-u", "origin", "main"], cwd=seed)

            self.assertEqual(result.returncode, 0)

    def test_privileged_skips_without_passwordless_sudo(self) -> None:
        denied = subprocess.CompletedProcess(
            args=["/usr/bin/sudo", "-n", "true"],
            returncode=1,
            stdout="",
            stderr="sudo: a password is required",
        )
        with (
            mock.patch.object(os, "geteuid", return_value=1000),
            mock.patch.object(shutil, "which", return_value="/usr/bin/sudo"),
            mock.patch.object(subprocess, "run", return_value=denied) as run_mock,
        ):
            with self.assertRaisesRegex(unittest.SkipTest, "passwordless sudo"):
                DeployExactCommitIntegrationTests.privileged(["chown", "target"])
        run_mock.assert_called_once_with(
            ["/usr/bin/sudo", "-n", "true"],
            text=True,
            capture_output=True,
            check=False,
        )


class DeployExactCommitIntegrationTests(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(self.restore_test_ownership)
        self.remote = self.root / "remote.git"
        self.source = self.root / "source"
        self.seed = self.root / "seed"
        self.releases = self.root / "releases"
        self.state = self.root / "state"
        self.runtime_env = self.root / "runtime.env"
        self.bin = self.root / "bin"
        self.artifact = self.state / "artifacts" / "web.tar.gz"
        self.runtime_env.write_text("TEST_RUNTIME=1\n", encoding="utf-8")
        self.bin.mkdir()

        run(["git", "init", "--bare", str(self.remote)])
        run(["git", "init", "-b", "main", str(self.seed)])
        run(["git", "config", "user.name", "Integration Test"], cwd=self.seed)
        run(
            ["git", "config", "user.email", "integration@example.invalid"],
            cwd=self.seed,
        )
        (self.seed / "apps/web").mkdir(parents=True)
        (self.seed / "scripts").mkdir()
        (self.seed / "apps/web/placeholder.txt").write_text("web\n", encoding="utf-8")
        up_script = self.seed / "scripts/weltgewebe-up"
        up_script.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                if [[ -e /proc/$$/fd/9 ]]; then
                  printf 'production lock descriptor leaked into weltgewebe-up\n' >&2
                  exit 94
                fi
                if [[ -n "${TEST_UP_LOG:-}" ]]; then
                  printf '%s\n' "$*" >> "$TEST_UP_LOG"
                fi
                if [[ ("${ADVANCE_REMOTE_ON_MIGRATION:-0}" == "1" && " $* " == *" --deploy-scope migration "*) || ("${ADVANCE_REMOTE_ON_DEPLOY:-0}" == "1" && " $* " != *" --deploy-scope migration "*) ]]; then
                  work="$(mktemp -d)"
                  git clone --quiet "$TEST_REMOTE" "$work/repo"
                  git -C "$work/repo" config user.name "Integration Test"
                  git -C "$work/repo" config user.email "integration@example.invalid"
                  printf 'advanced\\n' > "$work/repo/advanced.txt"
                  git -C "$work/repo" add advanced.txt
                  git -C "$work/repo" commit --quiet -m advance
                  git -C "$work/repo" push --quiet origin HEAD:main
                  rm -rf "$work"
                fi
                if [[ "${BREAK_REMOTE_ON_MIGRATION:-0}" == "1" && " $* " == *" --deploy-scope migration "* ]]; then
                  mv "$TEST_REMOTE" "${TEST_REMOTE}.offline"
                fi
                if [[ "${FAIL_FULL_DEPLOY:-0}" == "1" && " $* " != *" --deploy-scope migration "* ]]; then
                  exit 42
                fi
                if [[ "${TEMPFAIL_FULL_DEPLOY:-0}" == "1" && " $* " != *" --deploy-scope migration "* ]]; then
                  exit 75
                fi
                if [[ -n "${TEST_DEPLOY_MARKER:-}" && " $* " != *" --deploy-scope migration "* ]]; then
                  touch "$TEST_DEPLOY_MARKER"
                fi
                """
            ),
            encoding="utf-8",
        )
        up_script.chmod(0o755)
        run(["git", "add", "."], cwd=self.seed)
        run(["git", "commit", "-m", "fixture"], cwd=self.seed)
        run(["git", "remote", "add", "origin", str(self.remote)], cwd=self.seed)
        run(["git", "push", "-u", "origin", "main"], cwd=self.seed)
        run(
            [
                "git",
                "--git-dir",
                str(self.remote),
                "symbolic-ref",
                "HEAD",
                "refs/heads/main",
            ]
        )
        run(["git", "clone", "--branch", "main", str(self.remote), str(self.source)])
        self.commit = run(["git", "rev-parse", "HEAD"], cwd=self.source).stdout.strip()

        (self.source / "build/basemap").mkdir(parents=True)
        (self.source / "build/basemap/map.pmtiles").write_bytes(b"pmtiles")

        self.make_artifact()
        self.make_command_shims()

        run(
            self.privileged(
                [
                    "chown",
                    "-R",
                    "root:root",
                    str(self.source),
                    str(self.state),
                    str(self.runtime_env),
                ]
            )
        )
        run(
            self.privileged(
                [
                    "chmod",
                    "-R",
                    "go-w",
                    str(self.source),
                    str(self.state),
                    str(self.runtime_env),
                ]
            )
        )

    def restore_test_ownership(self) -> None:
        if not self.root.exists():
            return
        try:
            command = self.privileged(
                [
                    "chown",
                    "-R",
                    f"{os.getuid()}:{os.getgid()}",
                    str(self.root),
                ]
            )
        except unittest.SkipTest:
            return
        run(command, check=False)

    @staticmethod
    def privileged(argv: list[str]) -> list[str]:
        if os.geteuid() == 0:
            return argv
        sudo = shutil.which("sudo")
        if sudo is None:
            raise unittest.SkipTest(
                "sudo is required for the root-bound deployment integration test"
            )
        probe = subprocess.run(
            [sudo, "-n", "true"],
            text=True,
            capture_output=True,
            check=False,
        )
        if probe.returncode != 0:
            raise unittest.SkipTest(
                "passwordless sudo is unavailable for the root-bound deployment integration test"
            )
        return [sudo, "-n", *argv]

    def make_artifact(self) -> None:
        tree = self.root / "artifact-tree/build"
        (tree / "_app").mkdir(parents=True)
        (tree / "index.html").write_text("<!doctype html>\n", encoding="utf-8")
        (tree / "_app/version.json").write_text(
            json.dumps({"commit": self.commit, "version": self.commit[:8]}) + "\n",
            encoding="utf-8",
        )
        self.artifact.parent.mkdir(parents=True)
        with tarfile.open(self.artifact, "w:gz") as bundle:
            bundle.add(tree, arcname="build")
        self.artifact_sha = run(["sha256sum", str(self.artifact)]).stdout.split()[0]

    def make_command_shims(self) -> None:
        docker = self.bin / "docker"
        docker.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                expected_config="$WELTGEWEBE_DEPLOY_STATE_ROOT/docker-config"
                [[ "${DOCKER_CONFIG:-}" == "$expected_config" ]] || {
                  printf 'unexpected DOCKER_CONFIG: %s\n' "${DOCKER_CONFIG:-<unset>}" >&2
                  exit 91
                }
                [[ -d "$DOCKER_CONFIG" ]] || {
                  printf 'DOCKER_CONFIG directory is missing\n' >&2
                  exit 92
                }
                [[ "$(stat -c %a "$DOCKER_CONFIG")" == "700" ]] || {
                  printf 'DOCKER_CONFIG mode is not 700\n' >&2
                  exit 93
                }
                cat "$TEST_WEB_ARTIFACT"
                """
            ),
            encoding="utf-8",
        )
        docker.chmod(0o755)

        curl = self.bin / "curl"
        curl.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                headers=""
                url="${!#}"
                while (($#)); do
                  if [[ "$1" == "-D" ]]; then
                    headers="$2"
                    shift 2
                  else
                    shift
                  fi
                done
                public_commit="${PUBLIC_COMMIT:-$TEST_COMMIT}"
                if [[ -n "${TEST_DEPLOY_MARKER:-}" && -e "$TEST_DEPLOY_MARKER" ]]; then
                  public_commit="$TEST_COMMIT"
                fi
                if [[ "$url" == *"/api/version" ]]; then
                  if [[ -n "$headers" ]]; then
                    {
                      printf 'HTTP/1.1 200 OK\\r\\n'
                      printf 'X-Weltgewebe-API-Build: %s\\r\\n' "$public_commit"
                      printf 'X-Weltgewebe-Build: %s\\r\\n' "${public_commit:0:8}"
                      printf '\\r\\n'
                    } > "$headers"
                  fi
                  printf '{"commit":"%s","version":"0.1.0"}\\n' "$public_commit"
                else
                  printf '{"commit":"%s","version":"%s"}\\n' \
                    "$public_commit" "${public_commit:0:8}"
                fi
                """
            ),
            encoding="utf-8",
        )
        curl.chmod(0o755)

        verifier = self.bin / "verify-public"
        verifier.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from datetime import datetime, timezone
                from pathlib import Path

                args = sys.argv[1:]
                commit = args[args.index("--expected-commit") + 1]
                output = Path(args[args.index("--output") + 1])
                marker = os.environ.get("TEST_DEPLOY_MARKER")
                deployed = marker is None or Path(marker).exists()
                observed_commit = commit if deployed else os.environ["PUBLIC_COMMIT"]
                passed = observed_commit == commit
                payload = {
                    "schema_version": 2,
                    "expected_commit": commit,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "pass": passed,
                    "reasons": [] if passed else ["public commit differs"],
                    "frontend": {
                        "url": "https://example.invalid/_app/version.json",
                        "status": 200,
                        "commit": observed_commit,
                        "version": observed_commit[:8],
                        "headers": {"cache-control": "no-store"},
                        "error": None,
                    },
                    "api": {
                        "url": "https://example.invalid/api/version",
                        "status": 200,
                        "commit": observed_commit,
                        "version": "0.1.0",
                        "headers": {
                            "x-weltgewebe-api-build": observed_commit,
                            "x-weltgewebe-build": observed_commit[:8],
                        },
                        "error": None,
                    },
                }
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(payload) + "\\n", encoding="utf-8")
                raise SystemExit(0 if passed else 1)
                """
            ),
            encoding="utf-8",
        )
        verifier.chmod(0o755)

        blocking_verifier = self.bin / "blocking-verify-public"
        blocking_verifier.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                : > "$TEST_LOCK_OWNER_READY"
                while [[ ! -e "$TEST_LOCK_OWNER_RELEASE" ]]; do
                  sleep 0.02
                done
                exec "$TEST_VERIFY_PUBLIC" "$@"
                """
            ),
            encoding="utf-8",
        )
        blocking_verifier.chmod(0o755)

        forbidden_deploy = self.bin / "forbidden-deploy"
        forbidden_deploy.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
        forbidden_deploy.chmod(0o755)

        tempfail_deploy = self.bin / "tempfail-deploy"
        tempfail_deploy.write_text("#!/usr/bin/env bash\nexit 75\n", encoding="utf-8")
        tempfail_deploy.chmod(0o755)

        inherited_deploy = self.bin / "inherited-deploy"
        inherited_deploy.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                exec 9<> "$TEST_INHERITED_LOCK_TARGET"
                flock -n 9
                if [[ "${TEST_CLOSE_INHERITED_FD:-0}" == "1" ]]; then
                  exec 9>&-
                fi
                exec "$TEST_DEPLOY_SCRIPT" "$@"
                """
            ),
            encoding="utf-8",
        )
        inherited_deploy.chmod(0o755)

        exit_code_deploy = self.bin / "exit-code-deploy"
        exit_code_deploy.write_text(
            '#!/usr/bin/env bash\nexit "${TEST_DEPLOY_EXIT_CODE:?}"\n',
            encoding="utf-8",
        )
        exit_code_deploy.chmod(0o755)

        terminal_receipt_deploy = self.bin / "terminal-receipt-deploy"
        terminal_receipt_deploy.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                args = sys.argv[1:]
                commit = args[args.index("--commit") + 1]
                receipt = (
                    Path(os.environ["WELTGEWEBE_DEPLOY_STATE_ROOT"])
                    / "receipts"
                    / f"{commit}.json"
                )
                receipt.parent.mkdir(parents=True, exist_ok=True)
                schema_version = int(os.environ.get("TEST_DEPLOY_RECEIPT_SCHEMA", "5"))
                payload = {
                    "schema_version": schema_version,
                    "commit": commit,
                    "result": os.environ["TEST_DEPLOY_RECEIPT_RESULT"],
                    "lock_domain": "weltgewebe-production-deployment-v1",
                    "lock_owner_entrypoint": "reconciler",
                    "lock_handoff": "inherited",
                    "deploy_invocation_id": os.environ[
                        "WELTGEWEBE_DEPLOY_INVOCATION_ID"
                    ],
                }
                if schema_version != 5:
                    payload.pop("deploy_invocation_id")
                receipt.write_text(json.dumps(payload) + "\\n", encoding="utf-8")
                shape = os.environ.get("TEST_DEPLOY_RECEIPT_SHAPE", "regular")
                if shape == "mode":
                    receipt.chmod(0o666)
                elif shape == "owner":
                    os.chown(receipt, 65534, 65534)
                elif shape == "hardlink":
                    os.link(receipt, receipt.with_name(f"{receipt.name}.alias"))
                elif shape == "symlink":
                    receipt.unlink()
                    receipt.symlink_to(Path(os.environ["WELTGEWEBE_RUNTIME_ENV"]))
                elif shape != "regular":
                    raise SystemExit(f"unknown receipt shape: {shape}")
                raise SystemExit(int(os.environ["TEST_DEPLOY_EXIT_CODE"]))
                """
            ),
            encoding="utf-8",
        )
        terminal_receipt_deploy.chmod(0o755)

        contention_receipt_deploy = self.bin / "contention-receipt-deploy"
        contention_receipt_deploy.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json
                import os
                import sys
                from pathlib import Path

                args = sys.argv[1:]
                commit = args[args.index("--commit") + 1]
                receipt = (
                    Path(os.environ["WELTGEWEBE_DEPLOY_STATE_ROOT"])
                    / "receipts"
                    / "last-contention.json"
                )
                receipt.parent.mkdir(parents=True, exist_ok=True)
                schema_version = int(os.environ.get("TEST_CONTENTION_SCHEMA", "2"))
                payload = {
                    "schema_version": schema_version,
                    "kind": "weltgewebe_production_lock_contention",
                    "requested_commit": commit,
                    "lock_domain": "weltgewebe-production-deployment-v1",
                    "entrypoint": "reconciler",
                    "result": "already_running",
                    "deploy_invocation_id": os.environ[
                        "WELTGEWEBE_DEPLOY_INVOCATION_ID"
                    ],
                }
                if schema_version != 2:
                    payload.pop("deploy_invocation_id")
                receipt.write_text(json.dumps(payload) + "\\n", encoding="utf-8")
                shape = os.environ.get("TEST_CONTENTION_RECEIPT_SHAPE", "regular")
                if shape == "mode":
                    receipt.chmod(0o666)
                elif shape == "owner":
                    os.chown(receipt, 65534, 65534)
                elif shape == "hardlink":
                    os.link(receipt, receipt.with_name(f"{receipt.name}.alias"))
                elif shape == "symlink":
                    receipt.unlink()
                    receipt.symlink_to(Path(os.environ["WELTGEWEBE_RUNTIME_ENV"]))
                elif shape != "regular":
                    raise SystemExit(f"unknown contention receipt shape: {shape}")
                raise SystemExit(75)
                """
            ),
            encoding="utf-8",
        )
        contention_receipt_deploy.chmod(0o755)

        lock_contention_deploy = self.bin / "lock-contention-deploy"
        lock_contention_deploy.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                exec 9<> "$WELTGEWEBE_DEPLOY_STATE_ROOT/production-deployment.lock"
                exec "$TEST_DEPLOY_SCRIPT" "$@"
                """
            ),
            encoding="utf-8",
        )
        lock_contention_deploy.chmod(0o755)

        successful_deploy = self.bin / "successful-deploy"
        successful_deploy.write_text(
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            ': "${TEST_DEPLOY_MARKER:?}"\n'
            'touch "$TEST_DEPLOY_MARKER"\n',
            encoding="utf-8",
        )
        successful_deploy.chmod(0o755)

    def base_environment(self) -> dict[str, str]:
        inherited_path = os.environ.get("PATH", "/usr/bin:/bin")
        return {
            "PATH": f"{self.bin}:{inherited_path}",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "WELTGEWEBE_SOURCE_CHECKOUT": str(self.source),
            "WELTGEWEBE_RELEASE_ROOT": str(self.releases),
            "WELTGEWEBE_RUNTIME_ENV": str(self.runtime_env),
            "WELTGEWEBE_DEPLOY_STATE_ROOT": str(self.state),
            "WELTGEWEBE_ARCHIVE_VALIDATOR": str(VALIDATOR),
            "WELTGEWEBE_FRONTEND_VERSION_URL": (
                "https://example.invalid/_app/version.json"
            ),
            "WELTGEWEBE_API_VERSION_URL": "https://example.invalid/api/version",
            "TEST_COMMIT": self.commit,
            "TEST_REMOTE": str(self.remote),
            "TEST_WEB_ARTIFACT": str(self.artifact),
            "TEST_UP_LOG": str(self.root / "weltgewebe-up.log"),
        }

    def deploy(
        self,
        *,
        advance: bool,
        advance_after_migration: bool = False,
        break_remote_after_migration: bool = False,
        fail_full: bool = False,
        umask: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        deploy_env = self.base_environment()
        deploy_env["ADVANCE_REMOTE_ON_DEPLOY"] = "1" if advance else "0"
        deploy_env["ADVANCE_REMOTE_ON_MIGRATION"] = (
            "1" if advance_after_migration else "0"
        )
        deploy_env["BREAK_REMOTE_ON_MIGRATION"] = (
            "1" if break_remote_after_migration else "0"
        )
        deploy_env["FAIL_FULL_DEPLOY"] = "1" if fail_full else "0"
        command = [
            "env",
            *[f"{key}={value}" for key, value in deploy_env.items()],
            str(DEPLOY_SCRIPT),
            "--commit",
            self.commit,
            "--web-artifact",
            str(self.artifact),
            "--web-sha256",
            self.artifact_sha,
        ]
        if umask is not None:
            command = [
                "bash",
                "-c",
                'umask "$1"; shift; exec "$@"',
                "bash",
                umask,
                *command,
            ]
        return run(self.privileged(command), check=False)

    def deploy_with_inherited_handoff(
        self,
        *,
        environment_overrides: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        lock_target = self.state / "production-deployment.lock"
        deploy_env = self.base_environment()
        deploy_env.update(
            {
                "WELTGEWEBE_PRODUCTION_LOCK_FD": "9",
                "WELTGEWEBE_PRODUCTION_LOCK_DOMAIN": (
                    "weltgewebe-production-deployment-v1"
                ),
                "WELTGEWEBE_PRODUCTION_LOCK_OWNER_ENTRYPOINT": "reconciler",
                "WELTGEWEBE_DEPLOY_INVOCATION_ID": "a" * 64,
                "TEST_INHERITED_LOCK_TARGET": str(lock_target),
                "TEST_DEPLOY_SCRIPT": str(DEPLOY_SCRIPT),
            }
        )
        if environment_overrides:
            deploy_env.update(environment_overrides)
        argv = self.privileged(
            [
                "env",
                *[f"{key}={value}" for key, value in deploy_env.items()],
                str(self.bin / "inherited-deploy"),
                "--commit",
                self.commit,
                "--web-artifact",
                str(self.artifact),
                "--web-sha256",
                self.artifact_sha,
            ]
        )
        return run(argv, check=False)

    def install_root_json(self, path: Path, payload: dict[str, object]) -> None:
        source = (
            self.root
            / f"receipt-source-{len(list(self.root.glob('receipt-source-*')))}.json"
        )
        source.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        run(
            self.privileged(
                [
                    "install",
                    "-d",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0700",
                    str(path.parent),
                ]
            )
        )
        run(
            self.privileged(
                [
                    "install",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0600",
                    str(source),
                    str(path),
                ]
            )
        )

    def reconcile_existing_public_commit(self) -> subprocess.CompletedProcess[str]:
        reconcile_env = self.base_environment()
        reconcile_env.update(
            {
                "WELTGEWEBE_BUILD_USER": "root",
                "WELTGEWEBE_LIVE_VERIFIER": str(self.bin / "verify-public"),
                "WELTGEWEBE_DEPLOY_HELPER": str(self.bin / "forbidden-deploy"),
                "WELTGEWEBE_MIN_FREE_KIB": "1",
            }
        )
        argv = self.privileged(
            [
                "env",
                *[f"{key}={value}" for key, value in reconcile_env.items()],
                str(RECONCILE_SCRIPT),
            ]
        )
        return run(argv, check=False)

    def reconcile_stale_public_commit(
        self,
        *,
        advance_after_migration: bool = False,
        advance_during_deploy: bool = False,
        deploy_helper: Path = DEPLOY_SCRIPT,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        reconcile_env = self.base_environment()
        reconcile_env.update(
            {
                "WELTGEWEBE_BUILD_USER": "root",
                "WELTGEWEBE_LIVE_VERIFIER": str(self.bin / "verify-public"),
                "WELTGEWEBE_DEPLOY_HELPER": str(deploy_helper),
                "WELTGEWEBE_MIN_FREE_KIB": "1",
                "PUBLIC_COMMIT": "0" * 40,
                "TEST_DEPLOY_MARKER": str(self.root / "deploy-complete"),
                "ADVANCE_REMOTE_ON_MIGRATION": (
                    "1" if advance_after_migration else "0"
                ),
                "ADVANCE_REMOTE_ON_DEPLOY": "1" if advance_during_deploy else "0",
            }
        )
        if extra_env:
            reconcile_env.update(extra_env)
        argv = self.privileged(
            [
                "env",
                *[f"{key}={value}" for key, value in reconcile_env.items()],
                str(RECONCILE_SCRIPT),
            ]
        )
        return run(argv, check=False)

    def test_reconciler_exports_private_docker_config_to_build(self) -> None:
        result = self.reconcile_stale_public_commit()
        docker_config = self.state / "docker-config"
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(docker_config.stat().st_uid, 0)
        self.assertEqual(docker_config.stat().st_gid, 0)
        self.assertEqual(docker_config.stat().st_mode & 0o777, 0o700)
        self.restore_test_ownership()
        receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "verified")
        deployment_receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(
            deployment_receipt["lock_domain"], "weltgewebe-production-deployment-v1"
        )
        self.assertEqual(deployment_receipt["lock_owner_entrypoint"], "reconciler")
        self.assertEqual(deployment_receipt["lock_handoff"], "inherited")
        self.assertRegex(
            deployment_receipt["deploy_invocation_id"],
            r"^[0-9a-f]{64}$",
        )

    def test_reconciler_projects_migration_only_supersession_exactly(self) -> None:
        result = self.reconcile_stale_public_commit(advance_after_migration=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("production_reconcile=superseded_after_migration", result.stdout)
        deploy_receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        reconcile_receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(deploy_receipt["result"], "superseded_after_migration")
        self.assertEqual(reconcile_receipt["result"], "superseded_after_migration")
        self.assertIn("full deploy skipped", reconcile_receipt["detail"])
        deploy_calls = (self.root / "weltgewebe-up.log").read_text().splitlines()
        self.assertEqual(len(deploy_calls), 1)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        self.assertFalse((self.root / "deploy-complete").exists())

    def test_reconciler_projects_post_deploy_supersession_exactly(self) -> None:
        result = self.reconcile_stale_public_commit(advance_during_deploy=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("production_reconcile=superseded_after_deploy", result.stdout)
        deploy_receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        reconcile_receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(deploy_receipt["result"], "superseded_after_deploy")
        self.assertEqual(reconcile_receipt["result"], "superseded_after_deploy")
        self.assertIn("full deploy completed", reconcile_receipt["detail"])
        deploy_calls = (self.root / "weltgewebe-up.log").read_text().splitlines()
        self.assertEqual(len(deploy_calls), 2)
        self.assertTrue((self.root / "deploy-complete").exists())

    def test_reconciler_rejects_unbound_tempfail_without_supersession(self) -> None:
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "tempfail-deploy"
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "unexplained temporary failure under inherited production lock",
            result.stderr,
        )
        receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "failed")
        self.assertFalse((self.state / "receipts" / f"{self.commit}.json").exists())

    def test_deploy_helper_rejects_each_invalid_inherited_handoff_branch(self) -> None:
        cases = (
            (
                "descriptor number",
                {"WELTGEWEBE_PRODUCTION_LOCK_FD": "8"},
                "inherited production lock descriptor is invalid",
            ),
            (
                "domain",
                {"WELTGEWEBE_PRODUCTION_LOCK_DOMAIN": "other-domain"},
                "inherited production lock domain is invalid",
            ),
            (
                "owner",
                {"WELTGEWEBE_PRODUCTION_LOCK_OWNER_ENTRYPOINT": "deploy-helper"},
                "inherited production lock owner is invalid",
            ),
            (
                "invocation identity",
                {"WELTGEWEBE_DEPLOY_INVOCATION_ID": ""},
                "inherited deploy invocation identity is invalid",
            ),
            (
                "closed descriptor",
                {"TEST_CLOSE_INHERITED_FD": "1"},
                "inherited production lock descriptor is not open",
            ),
            (
                "lock target",
                {
                    "TEST_INHERITED_LOCK_TARGET": str(
                        self.state / "wrong-production.lock"
                    )
                },
                "inherited production lock targets an unexpected file",
            ),
        )
        for label, overrides, expected_error in cases:
            with self.subTest(label=label):
                result = self.deploy_with_inherited_handoff(
                    environment_overrides=overrides
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(expected_error, result.stderr)

    def test_reconciler_rejects_stale_terminal_receipt_for_new_invocation(self) -> None:
        self.install_root_json(
            self.state / "receipts" / f"{self.commit}.json",
            {
                "schema_version": 5,
                "commit": self.commit,
                "result": "superseded_after_migration",
                "lock_domain": "weltgewebe-production-deployment-v1",
                "lock_owner_entrypoint": "reconciler",
                "lock_handoff": "inherited",
                "deploy_invocation_id": "b" * 64,
            },
        )
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "exit-code-deploy",
            extra_env={"TEST_DEPLOY_EXIT_CODE": "79"},
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "terminal deployment receipt does not match current invocation",
            result.stderr,
        )

    def test_reconciler_rejects_both_exit_result_mismatches(self) -> None:
        cases = (
            (79, "superseded_after_deploy"),
            (80, "superseded_after_migration"),
        )
        for exit_code, result_value in cases:
            with self.subTest(exit_code=exit_code, result=result_value):
                result = self.reconcile_stale_public_commit(
                    deploy_helper=self.bin / "terminal-receipt-deploy",
                    extra_env={
                        "TEST_DEPLOY_EXIT_CODE": str(exit_code),
                        "TEST_DEPLOY_RECEIPT_RESULT": result_value,
                    },
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("deploy helper exit/result mismatch", result.stderr)
        self.restore_test_ownership()

    def test_reconciler_identifies_child_tempfail_from_current_failed_receipt(
        self,
    ) -> None:
        contention = self.state / "receipts" / "last-contention.json"
        run(
            self.privileged(
                [
                    "install",
                    "-d",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0700",
                    str(contention.parent),
                ]
            )
        )
        run(self.privileged(["ln", "-s", str(self.runtime_env), str(contention)]))
        result = self.reconcile_stale_public_commit(
            extra_env={"TEMPFAIL_FULL_DEPLOY": "1"}
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "child temporary failure after writing a failed receipt for the current invocation",
            result.stderr,
        )
        receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "failed")
        self.assertRegex(receipt["deploy_invocation_id"], r"^[0-9a-f]{64}$")

    def test_reconciler_ignores_stale_failed_receipt_for_tempfail(self) -> None:
        self.install_root_json(
            self.state / "receipts" / f"{self.commit}.json",
            {
                "schema_version": 5,
                "commit": self.commit,
                "result": "failed",
                "lock_domain": "weltgewebe-production-deployment-v1",
                "lock_owner_entrypoint": "reconciler",
                "lock_handoff": "inherited",
                "deploy_invocation_id": "b" * 64,
            },
        )
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "exit-code-deploy",
            extra_env={"TEST_DEPLOY_EXIT_CODE": "75"},
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "unexplained temporary failure under inherited production lock",
            result.stderr,
        )
        self.assertNotIn("child temporary failure", result.stderr)

    def test_reconciler_rejects_unsafe_tempfail_receipt(self) -> None:
        receipt = self.state / "receipts" / f"{self.commit}.json"
        run(
            self.privileged(
                [
                    "install",
                    "-d",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0700",
                    str(receipt.parent),
                ]
            )
        )
        run(self.privileged(["ln", "-s", str(self.runtime_env), str(receipt)]))
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "exit-code-deploy",
            extra_env={"TEST_DEPLOY_EXIT_CODE": "75"},
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "deploy helper returned temporary failure with unsafe receipt evidence",
            result.stderr,
        )

    def test_reconciler_identifies_actual_inherited_lock_contention(self) -> None:
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "lock-contention-deploy",
            extra_env={"TEST_DEPLOY_SCRIPT": str(DEPLOY_SCRIPT)},
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "production lock contention during inherited handoff",
            result.stderr,
        )
        receipt = json.loads(
            (self.state / "receipts" / "last-contention.json").read_text()
        )
        self.assertEqual(receipt["schema_version"], 2)
        self.assertEqual(receipt["requested_commit"], self.commit)
        self.assertRegex(receipt["deploy_invocation_id"], r"^[0-9a-f]{64}$")

    def remove_deploy_test_receipts(self) -> None:
        receipt_root = self.state / "receipts"
        run(
            self.privileged(
                [
                    "rm",
                    "-f",
                    str(receipt_root / f"{self.commit}.json"),
                    str(receipt_root / f"{self.commit}.json.alias"),
                    str(receipt_root / "last-contention.json"),
                    str(receipt_root / "last-contention.json.alias"),
                ]
            )
        )

    def test_reconciler_rejects_unsafe_terminal_receipt_shapes(self) -> None:
        for shape in ("mode", "owner", "hardlink", "symlink"):
            with self.subTest(shape=shape):
                self.remove_deploy_test_receipts()
                result = self.reconcile_stale_public_commit(
                    deploy_helper=self.bin / "terminal-receipt-deploy",
                    extra_env={
                        "TEST_DEPLOY_EXIT_CODE": "79",
                        "TEST_DEPLOY_RECEIPT_RESULT": "superseded_after_migration",
                        "TEST_DEPLOY_RECEIPT_SHAPE": shape,
                    },
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("terminal deployment receipt is unsafe", result.stderr)
        self.restore_test_ownership()

    def test_reconciler_rejects_schema4_terminal_receipt(self) -> None:
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "terminal-receipt-deploy",
            extra_env={
                "TEST_DEPLOY_EXIT_CODE": "79",
                "TEST_DEPLOY_RECEIPT_RESULT": "superseded_after_migration",
                "TEST_DEPLOY_RECEIPT_SCHEMA": "4",
            },
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "terminal deployment receipt schema is not current", result.stderr
        )

    def test_reconciler_rejects_unsafe_contention_receipt_shapes(self) -> None:
        for shape in ("mode", "owner", "hardlink", "symlink"):
            with self.subTest(shape=shape):
                self.remove_deploy_test_receipts()
                result = self.reconcile_stale_public_commit(
                    deploy_helper=self.bin / "contention-receipt-deploy",
                    extra_env={"TEST_CONTENTION_RECEIPT_SHAPE": shape},
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe receipt evidence", result.stderr)
        self.restore_test_ownership()

    def test_reconciler_rejects_schema1_contention_receipt(self) -> None:
        result = self.reconcile_stale_public_commit(
            deploy_helper=self.bin / "contention-receipt-deploy",
            extra_env={"TEST_CONTENTION_SCHEMA": "1"},
        )
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "unexplained temporary failure under inherited production lock",
            result.stderr,
        )

    def start_blocking_reconciler(self) -> tuple[subprocess.Popen[str], Path]:
        ready = self.root / "lock-owner-ready"
        release = self.root / "lock-owner-release"
        reconcile_env = self.base_environment()
        reconcile_env.update(
            {
                "WELTGEWEBE_BUILD_USER": "root",
                "WELTGEWEBE_LIVE_VERIFIER": str(self.bin / "blocking-verify-public"),
                "WELTGEWEBE_DEPLOY_HELPER": str(self.bin / "forbidden-deploy"),
                "WELTGEWEBE_MIN_FREE_KIB": "1",
                "TEST_LOCK_OWNER_READY": str(ready),
                "TEST_LOCK_OWNER_RELEASE": str(release),
                "TEST_VERIFY_PUBLIC": str(self.bin / "verify-public"),
            }
        )
        argv = self.privileged(
            [
                "env",
                *[f"{key}={value}" for key, value in reconcile_env.items()],
                str(RECONCILE_SCRIPT),
            ]
        )
        process = subprocess.Popen(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for _ in range(250):
            if ready.exists():
                return process, release
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                raise AssertionError(
                    f"blocking reconciler exited early ({process.returncode})\n"
                    f"stdout:\n{stdout}\nstderr:\n{stderr}"
                )
            __import__("time").sleep(0.02)
        process.terminate()
        process.wait(timeout=5)
        raise AssertionError("blocking reconciler did not acquire the production lock")

    def finish_blocking_reconciler(
        self, process: subprocess.Popen[str], release: Path
    ) -> tuple[str, str]:
        release.write_text("release\n", encoding="utf-8")
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
            raise AssertionError(
                f"blocking reconciler did not finish\nstdout:\n{stdout}\nstderr:\n{stderr}"
            )
        self.assertEqual(process.returncode, 0, stderr)
        return stdout, stderr

    def test_timer_and_installer_reconcile_starts_share_one_owner(self) -> None:
        owner, release = self.start_blocking_reconciler()
        try:
            contender = self.reconcile_existing_public_commit()
            self.assertEqual(contender.returncode, 0, contender.stderr)
            self.assertIn("production_reconcile=already_running", contender.stdout)
        finally:
            self.finish_blocking_reconciler(owner, release)
        self.restore_test_ownership()
        receipt = json.loads(
            (self.state / "reconcile-receipts" / "last-contention.json").read_text()
        )
        self.assertEqual(receipt["kind"], "weltgewebe_production_lock_contention")
        self.assertEqual(receipt["entrypoint"], "reconciler")
        self.assertEqual(receipt["result"], "already_running")
        self.assertEqual(receipt["lock_domain"], "weltgewebe-production-deployment-v1")
        self.assertFalse((self.root / "weltgewebe-up.log").exists())

    def test_reconciler_owner_rejects_direct_helper_without_deploy_effects(
        self,
    ) -> None:
        owner, release = self.start_blocking_reconciler()
        try:
            contender = self.deploy(advance=False)
            self.assertEqual(contender.returncode, 75, contender.stderr)
            self.assertIn("production_deployment=already_running", contender.stderr)
        finally:
            self.finish_blocking_reconciler(owner, release)
        self.restore_test_ownership()
        receipt = json.loads(
            (self.state / "receipts" / "last-contention.json").read_text()
        )
        self.assertEqual(receipt["kind"], "weltgewebe_production_lock_contention")
        self.assertEqual(receipt["entrypoint"], "deploy-helper")
        self.assertEqual(receipt["requested_commit"], self.commit)
        self.assertEqual(receipt["result"], "already_running")
        self.assertEqual(receipt["lock_domain"], "weltgewebe-production-deployment-v1")
        self.assertFalse((self.root / "weltgewebe-up.log").exists())

    def test_stale_lock_file_without_owner_does_not_block_deploy(self) -> None:
        lock_path = self.state / "production-deployment.lock"
        run(self.privileged(["touch", str(lock_path)]))
        run(self.privileged(["chmod", "0600", str(lock_path)]))
        result = self.deploy(advance=False)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "verified")
        self.assertEqual(receipt["lock_handoff"], "direct")

    def test_success_marks_exact_commit_current(self) -> None:
        result = self.deploy(advance=False)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        deploy_calls = (
            (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(len(deploy_calls), 2)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        self.assertNotIn("--with-caddy", deploy_calls[0])
        self.assertIn("--with-caddy", deploy_calls[1])
        self.assertNotIn("--deploy-scope migration", deploy_calls[1])
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "verified")
        self.assertEqual(receipt["schema_version"], 5)
        self.assertEqual(receipt["lock_domain"], "weltgewebe-production-deployment-v1")
        self.assertEqual(receipt["lock_owner_entrypoint"], "deploy-helper")
        self.assertEqual(receipt["lock_handoff"], "direct")
        self.assertIsNone(receipt["deploy_invocation_id"])
        self.assertIsInstance(receipt["migration_completed_at"], str)
        self.assertEqual(receipt["observed_main_after_deploy"], self.commit)
        current = (self.state / "current.json").resolve()
        self.assertEqual(current, receipt_path)

    def test_direct_recovery_receipt_is_mode_0600_under_permissive_umask(self) -> None:
        result = self.deploy(advance=False, umask="000")
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = self.state / "receipts" / f"{self.commit}.json"
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    def test_public_noop_migrates_schema4_verified_receipt(self) -> None:
        self.install_root_json(
            self.state / "receipts" / f"{self.commit}.json",
            {
                "schema_version": 4,
                "commit": self.commit,
                "result": "verified",
                "lock_domain": "weltgewebe-production-deployment-v1",
                "lock_owner_entrypoint": "deploy-helper",
                "lock_handoff": "direct",
            },
        )
        result = self.reconcile_existing_public_commit()
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["schema_version"], 5)
        self.assertEqual(receipt["result"], "verified_observed")

    def test_main_advancing_after_migration_is_superseded_before_full_deploy(
        self,
    ) -> None:
        result = self.deploy(advance=False, advance_after_migration=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 79, result.stderr)
        deploy_calls = (
            (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(len(deploy_calls), 1)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "superseded_after_migration")
        self.assertIsInstance(receipt["migration_completed_at"], str)
        self.assertIsNone(receipt["api_commit"])
        self.assertIsNone(receipt["frontend_commit"])
        self.assertNotEqual(receipt["observed_main_after_deploy"], self.commit)
        self.assertFalse((self.state / "current.json").exists())

    def test_full_deploy_failure_after_migration_records_completed_phase(self) -> None:
        result = self.deploy(advance=False, fail_full=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 42, result.stderr)
        deploy_calls = (
            (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(len(deploy_calls), 2)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        self.assertIn("--with-caddy", deploy_calls[1])
        receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "failed")
        self.assertIsInstance(receipt["migration_completed_at"], str)
        self.assertIsNone(receipt["api_commit"])
        self.assertIsNone(receipt["frontend_commit"])
        self.assertFalse((self.state / "current.json").exists())

    def test_main_fetch_failure_after_migration_records_completed_phase(self) -> None:
        result = self.deploy(advance=False, break_remote_after_migration=True)
        self.restore_test_ownership()
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertNotEqual(result.returncode, 75, result.stderr)
        deploy_calls = (
            (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        )
        self.assertEqual(len(deploy_calls), 1)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        receipt = json.loads(
            (self.state / "receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(receipt["result"], "failed")
        self.assertIsInstance(receipt["migration_completed_at"], str)
        self.assertIsNone(receipt["api_commit"])
        self.assertIsNone(receipt["frontend_commit"])
        self.assertFalse((self.state / "current.json").exists())

    def test_main_advancing_during_deploy_is_not_marked_current(self) -> None:
        result = self.deploy(advance=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 80, result.stderr)
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "superseded_after_deploy")
        self.assertNotEqual(receipt["observed_main_after_deploy"], self.commit)
        self.assertFalse((self.state / "current.json").exists())

    def test_public_noop_repairs_missing_deployment_receipt(self) -> None:
        result = self.reconcile_existing_public_commit()
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["schema_version"], 5)
        self.assertEqual(receipt["result"], "verified_observed")
        self.assertEqual(receipt["lock_domain"], "weltgewebe-production-deployment-v1")
        self.assertEqual(receipt["lock_owner_entrypoint"], "reconciler")
        self.assertEqual(receipt["lock_handoff"], "public-observation")
        self.assertIsNone(receipt["deploy_invocation_id"])
        self.assertIsNone(receipt["migration_completed_at"])
        self.assertIsNone(receipt["web_artifact_sha256"])
        self.assertIn("original web artifact hash", receipt["evidence_boundary"])
        self.assertEqual((self.state / "current.json").resolve(), receipt_path)
        reconcile_receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(reconcile_receipt["result"], "verified_observed")


if __name__ == "__main__":
    unittest.main()

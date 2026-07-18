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

        forbidden_deploy = self.bin / "forbidden-deploy"
        forbidden_deploy.write_text("#!/usr/bin/env bash\nexit 99\n", encoding="utf-8")
        forbidden_deploy.chmod(0o755)

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
        self, *, advance: bool, advance_after_migration: bool = False
    ) -> subprocess.CompletedProcess[str]:
        deploy_env = self.base_environment()
        deploy_env["ADVANCE_REMOTE_ON_DEPLOY"] = "1" if advance else "0"
        deploy_env["ADVANCE_REMOTE_ON_MIGRATION"] = (
            "1" if advance_after_migration else "0"
        )
        argv = self.privileged(
            [
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
        )
        return run(argv, check=False)

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

    def reconcile_stale_public_commit(self) -> subprocess.CompletedProcess[str]:
        reconcile_env = self.base_environment()
        reconcile_env.update(
            {
                "WELTGEWEBE_BUILD_USER": "root",
                "WELTGEWEBE_LIVE_VERIFIER": str(self.bin / "verify-public"),
                "WELTGEWEBE_DEPLOY_HELPER": str(self.bin / "successful-deploy"),
                "WELTGEWEBE_MIN_FREE_KIB": "1",
                "PUBLIC_COMMIT": "0" * 40,
                "TEST_DEPLOY_MARKER": str(self.root / "deploy-complete"),
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

    def test_success_marks_exact_commit_current(self) -> None:
        result = self.deploy(advance=False)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 0, result.stderr)
        deploy_calls = (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(deploy_calls), 2)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        self.assertNotIn("--with-caddy", deploy_calls[0])
        self.assertIn("--with-caddy", deploy_calls[1])
        self.assertNotIn("--deploy-scope migration", deploy_calls[1])
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "verified")
        self.assertEqual(receipt["observed_main_after_deploy"], self.commit)
        current = (self.state / "current.json").resolve()
        self.assertEqual(current, receipt_path)

    def test_main_advancing_after_migration_is_superseded_before_full_deploy(self) -> None:
        result = self.deploy(advance=False, advance_after_migration=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 75, result.stderr)
        deploy_calls = (self.root / "weltgewebe-up.log").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(deploy_calls), 1)
        self.assertIn("--deploy-scope migration", deploy_calls[0])
        receipt_path = self.state / "receipts" / f"{self.commit}.json"
        receipt = json.loads(receipt_path.read_text())
        self.assertEqual(receipt["result"], "superseded_after_migration")
        self.assertNotEqual(receipt["observed_main_after_deploy"], self.commit)
        self.assertFalse((self.state / "current.json").exists())

    def test_main_advancing_during_deploy_is_not_marked_current(self) -> None:
        result = self.deploy(advance=True)
        self.restore_test_ownership()
        self.assertEqual(result.returncode, 75, result.stderr)
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
        self.assertEqual(receipt["result"], "verified_observed")
        self.assertIsNone(receipt["web_artifact_sha256"])
        self.assertIn("original web artifact hash", receipt["evidence_boundary"])
        self.assertEqual((self.state / "current.json").resolve(), receipt_path)
        reconcile_receipt = json.loads(
            (self.state / "reconcile-receipts" / f"{self.commit}.json").read_text()
        )
        self.assertEqual(reconcile_receipt["result"], "verified_observed")


if __name__ == "__main__":
    unittest.main()

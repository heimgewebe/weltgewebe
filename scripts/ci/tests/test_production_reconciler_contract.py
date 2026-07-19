from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[3]


class ProductionReconcilerContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_deploy_helper_rechecks_main_after_public_readback(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        self.assertGreaterEqual(script.count("fetch_main"), 3)
        deploy = script.index('"$release_dir/scripts/weltgewebe-up"')
        public_readback = script.index('api_body_file="$(mktemp', deploy)
        post_check = script.index('post_deploy_main="$(fetch_main)"', public_readback)
        verified_link = script.index('ln -sfn "receipts/$COMMIT.json"', post_check)
        self.assertLess(deploy, public_readback)
        self.assertLess(public_readback, post_check)
        self.assertLess(post_check, verified_link)
        self.assertIn("superseded_after_deploy", script)
        self.assertIn("readonly EX_TEMPFAIL=75", script)
        self.assertIn("readonly EXIT_SUPERSEDED_AFTER_MIGRATION=79", script)
        self.assertIn("readonly EXIT_SUPERSEDED_AFTER_DEPLOY=80", script)
        self.assertIn('exit "$EXIT_SUPERSEDED_AFTER_DEPLOY"', script)
        self.assertNotIn("curl -fsSI", script)
        self.assertIn("--max-filesize 1048576", script)
        self.assertIn("write_bounded_response", script)
        self.assertIn('api_body_file="$(mktemp', script)
        self.assertIn("awk -F':'", script)

    def test_deploy_helper_runs_bounded_migrations_before_full_deploy(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        migration = script.index("run_release_deploy migration")
        post_migration_main = script.index('remote_main="$(fetch_main)"', migration)
        full = script.index("run_release_deploy full", post_migration_main)
        public_readback = script.index('api_headers="$(mktemp', full)
        self.assertLess(migration, post_migration_main)
        self.assertLess(post_migration_main, full)
        self.assertLess(full, public_readback)
        self.assertIn('write_deploy_receipt "superseded_after_migration"', script)
        self.assertIn('"$completed_at" "" "" "$remote_main"', script)
        self.assertIn("production_deployment=superseded_after_migration", script)
        self.assertIn("migration_completed_at", script)
        self.assertIn("production_deployment_phase=migration state=starting", script)
        self.assertIn("production_deployment_phase=migration state=completed", script)
        self.assertIn("production_deployment_phase=full state=starting", script)
        self.assertIn('exit "$EXIT_SUPERSEDED_AFTER_MIGRATION"', script)
        self.assertIn("--deploy-scope migration", script)
        self.assertIn('"+refs/heads/main:refs/remotes/origin/main" || return 1', script)
        self.assertIn("rev-parse refs/remotes/origin/main || return 1", script)

    def test_deploy_helper_preserves_legacy_checkout_and_binds_main(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        self.assertIn("+refs/heads/main:refs/remotes/origin/main", script)
        self.assertIn('worktree add --detach "$release_dir" "$COMMIT"', script)
        for forbidden in ("git reset", "git clean", "git switch", "git pull"):
            self.assertNotIn(forbidden, script)
        self.assertIn(
            'PRODUCTION_LOCK_FILE="${STATE_ROOT}/production-deployment.lock"',
            script,
        )
        self.assertIn("WELTGEWEBE_PRODUCTION_LOCK_FD", script)
        self.assertIn('lock_handoff="inherited"', script)
        self.assertIn("production_deployment=already_running", script)
        self.assertIn('"$release_dir/scripts/weltgewebe-up" "${arguments[@]}" 9>&-', script)
        self.assertNotIn('${STATE_ROOT}/deploy.lock', script)
        self.assertIn("ARCHIVE_VALIDATOR", script)
        self.assertIn("validate_release_tree", script)
        self.assertIn("release contains unexpected state", script)
        self.assertIn("release directory is not root-owned", script)
        self.assertIn('find "$release_dir/apps/web/build" -type f -exec chmod 0644', script)
        self.assertIn('ln -s "$basemap_real" "$release_dir/build/basemap"', script)
        self.assertIn("basemap link escapes the canonical data root", script)
        self.assertIn("-type l -print0", script)
        self.assertIn('install -d -o root -g root -m 0700 "$STATE_ROOT/receipts"', script)

    def test_deploy_helper_requires_immutable_root_artifact(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        self.assertIn("web artifact escaped the root-owned artifact directory", script)
        self.assertIn("web artifact is not root-owned", script)
        self.assertIn("web artifact is group- or world-writable", script)
        self.assertIn("web artifact has unexpected hard links", script)
        self.assertIn("web artifact changed during validation", script)
        self.assertGreaterEqual(script.count('sha256sum "$artifact_real"'), 2)
        self.assertIn('write_deploy_receipt \\\n      "failed"', script)

    def test_reconciler_has_bounded_storage_and_state_transitions(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        for state in (
            "observed",
            "building",
            "artifact_validated",
            "deferred",
            "superseded_after_observe",
            "superseded_after_deploy",
            "superseded_after_verify",
            "verified_observed",
            "verified",
            "failed",
        ):
            self.assertIn(f'"{state}"', script)
        self.assertIn("MIN_FREE_KIB", script)
        self.assertIn("prune_artifacts", script)
        self.assertIn("prune_releases", script)
        self.assertIn('rm -f -- "$source_archive"', script)
        self.assertIn('worktree remove "$release_dir"', script)
        self.assertNotIn("worktree remove --force", script)
        self.assertIn("web_artifacts[@]:20", script)
        self.assertIn("repair_observed_deployment_state", script)
        self.assertIn('"migration_completed_at": None', script)
        self.assertIn("original web artifact hash", script)
        self.assertIn('ln -sfn "receipts/$target_commit.json"', script)
        self.assertIn('chmod 0600 "$artifact"', script)
        self.assertIn('DOCKER_CONFIG="$STATE_ROOT/docker-config"', script)
        self.assertIn("export DOCKER_CONFIG", script)
        self.assertIn('"$DEPLOY_RECEIPT_ROOT" "$DOCKER_CONFIG"', script)
        self.assertIn(
            'PRODUCTION_LOCK_FILE="$STATE_ROOT/production-deployment.lock"',
            script,
        )
        self.assertIn("production_reconcile=already_running", script)
        self.assertIn("readonly EX_TEMPFAIL=75", script)
        self.assertIn("readonly EXIT_SUPERSEDED_AFTER_MIGRATION=79", script)
        self.assertIn("readonly EXIT_SUPERSEDED_AFTER_DEPLOY=80", script)
        self.assertIn('case "$deploy_rc" in', script)
        self.assertIn("temporary failure under inherited production lock", script)
        self.assertIn("unexpected superseded reason", script)
        self.assertIn(
            'WELTGEWEBE_PRODUCTION_LOCK_OWNER_ENTRYPOINT="reconciler"',
            script,
        )
        self.assertNotIn('$STATE_ROOT/reconcile.lock', script)

    def test_reconciler_build_cannot_write_release_or_source(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        self.assertIn(
            "docker.io/library/node@sha256:8898f8ed3c0126667837b678979b4ed83306c856a1227c8bf5f5f77740c25cd6",
            script,
        )
        for expected in (
            "docker run --rm",
            "--cap-drop ALL",
            "--security-opt no-new-privileges",
            "--read-only",
            "--pids-limit 512",
            "--memory 2g",
            "--cpus 2",
            "--tmpfs /workspace:rw,exec,nosuid,nodev,size=3g,mode=1777",
            "dst=/source.tar,readonly",
            'GIT_COMMIT_SHA="$target_commit"',
        ):
            self.assertIn(expected, script)
        for forbidden in (
            "/var/run/docker.sock",
            "SSH_AUTH_SOCK",
            "--privileged",
            "dst=/opt/weltgewebe",
            "dst=/opt/weltgewebe-releases",
        ):
            self.assertNotIn(forbidden, script)

    def test_systemd_timer_uses_completion_relative_cadence(self) -> None:
        service = self.read("infra/systemd/system/weltgewebe-production-reconcile.service")
        timer = self.read("infra/systemd/system/weltgewebe-production-reconcile.timer")
        self.assertIn("EnvironmentFile=-/etc/weltgewebe/production-reconciler.env", service)
        self.assertIn("TimeoutStartSec=7200", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("OnUnitInactiveSec=2min", timer)
        self.assertNotIn("OnUnitActiveSec", timer)
        self.assertNotIn("Persistent=true", timer)
        self.assertIn(
            "ExecStart=/usr/local/libexec/weltgewebe-reconcile-production-main",
            service,
        )
        self.assertIn("Unit=weltgewebe-production-reconcile.service", timer)

    def test_installer_is_exact_commit_bound_and_parameterizes_build_user(self) -> None:
        script = self.read("scripts/ops/install-production-reconciler.sh")
        self.assertIn("--commit", script)
        self.assertIn('remote_main" == "$COMMIT', script)
        self.assertIn('git -C "$REPO_DIR" show "$COMMIT:$source_path"', script)
        self.assertIn("production-reconciler.env", script)
        self.assertIn("installed-contract.sha256", script)
        self.assertIn("/var/lib/weltgewebe-main-reconciler/docker-config", script)
        self.assertNotIn("Environment=WELTGEWEBE_BUILD_USER=alex", script)
        self.assertIn(
            "systemctl start weltgewebe-production-reconcile.service", script
        )

    def test_installer_deferred_update_is_atomic_and_non_recursive(self) -> None:
        script = self.read("scripts/ops/install-production-reconciler.sh")
        self.assertIn("--defer-reconcile", script)
        self.assertIn(
            "deferred installation requires an existing enabled and active production reconcile timer",
            script,
        )
        self.assertIn("atomic_install()", script)
        self.assertIn("mv -fT --", script)
        self.assertIn("require_matching_sha256", script)
        for installed_path in (
            "/usr/local/libexec/weltgewebe-deploy-exact-commit",
            "/usr/local/libexec/weltgewebe-reconcile-production-main",
            "/usr/local/libexec/weltgewebe-validate-web-deploy-archive",
            "/usr/local/libexec/weltgewebe-verify-public-release",
            "/etc/systemd/system/weltgewebe-production-reconcile.service",
            "/etc/systemd/system/weltgewebe-production-reconcile.timer",
        ):
            self.assertIn(installed_path, script)
        staged_verify = script.index("systemd-analyze verify")
        self.assertIn(
            '"$staging/weltgewebe-production-reconcile.service"',
            script[staged_verify:],
        )
        first_binary_install = script.index(
            'atomic_install "$staging/weltgewebe-deploy-exact-commit"'
        )
        first_unit_install = script.index(
            'atomic_install "$staging/weltgewebe-production-reconcile.service"'
        )
        self.assertLess(first_binary_install, staged_verify)
        self.assertLess(staged_verify, first_unit_install)
        deferred = script.index(
            "if ((DEFER_RECONCILE == 1)); then",
            script.index("systemctl daemon-reload"),
        )
        normal_start = script.index("else", deferred)
        deferred_branch = script[deferred:normal_start]
        self.assertIn("systemctl is-enabled --quiet", deferred_branch)
        self.assertIn("systemctl is-active --quiet", deferred_branch)
        self.assertNotIn("systemctl start", deferred_branch)
        self.assertIn("mode=$install_mode", script)

    def test_release_activation_is_exact_path_bound_and_precedes_docker(self) -> None:
        activator = self.read(
            "scripts/ops/activate-production-reconciler-from-release.sh"
        )
        up = self.read("scripts/weltgewebe-up")
        self.assertIn("production reconciler activation must run as root", activator)
        self.assertIn(
            '"$release_dir_real" == "$release_root_real/$COMMIT"', activator
        )
        self.assertIn("require_root_safe_directory", activator)
        self.assertIn("require_root_safe_regular_file", activator)
        self.assertIn(
            'require_root_safe_directory "$release_root_real" "resolved release root"',
            activator,
        )
        self.assertIn(
            'require_root_safe_directory "$release_dir_real" "resolved release directory"',
            activator,
        )
        self.assertIn("rev-parse --verify 'HEAD^{commit}'", activator)
        self.assertIn("release directory is not a valid Git repository", activator)
        self.assertIn('release_head" == "$COMMIT', activator)
        self.assertIn("--defer-reconcile", activator)
        self.assertIn(
            'if [[ "$DEPLOY_TARGET" == "vps" && "$PLAN_ONLY" == "0" ]]; then',
            up,
        )
        self.assertIn('release_root="${release_root%/}"', up)
        self.assertIn('release_dir="${REPO_DIR%/}"', up)
        self.assertIn('release_commit="$(basename -- "$release_dir")"', up)
        self.assertIn('activation_owner_uid="$(id -u)"', up)
        self.assertIn('stat --format=%u -- "$reconciler_activator"', up)
        self.assertIn('((8#$activation_mode & 022))', up)
        activation = up.index(">> Production reconciler contract activation:")
        bake = up.index("# --- Bake Configuration ---")
        docker_config = up.index('docker compose "${BASE_ARGS[@]}" config', bake)
        self.assertLess(activation, bake)
        self.assertLess(bake, docker_config)

    def test_weltgewebe_up_normalizes_release_trailing_slashes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="weltgewebe-release-activation-") as tmp:
            root = Path(tmp)
            commit = "a" * 40
            release_root = root / "releases"
            release_dir = release_root / commit
            (release_dir / "infra" / "compose").mkdir(parents=True)
            (release_dir / "scripts" / "ops").mkdir(parents=True)
            (release_dir / "infra" / "compose" / "compose.prod.yml").write_text(
                "services: {}\n", encoding="utf-8"
            )
            runtime_env = root / "runtime.env"
            runtime_env.write_text("TEST_ONLY=1\n", encoding="utf-8")
            activation_log = root / "activation.log"
            activator = (
                release_dir
                / "scripts"
                / "ops"
                / "activate-production-reconciler-from-release.sh"
            )
            activator.write_text(
                "#!/usr/bin/env bash\n"
                "set -eu\n"
                f"printf '%s\\n' \"$*\" > {activation_log!s}\n",
                encoding="utf-8",
            )
            activator.chmod(0o755)

            env = os.environ.copy()
            env.update(
                {
                    "DEPLOY_TARGET": "vps",
                    "ENV_FILE": str(runtime_env),
                    "REPO_DIR": f"{release_dir}/",
                    "WELTGEWEBE_DEPLOY_LOCK_FILE": str(root / "deploy.lock"),
                    "WELTGEWEBE_RELEASE_ROOT": f"{release_root}/",
                    "WELTGEWEBE_STATE_DIR": str(root / "state"),
                }
            )
            completed = subprocess.run(
                [str(ROOT / "scripts" / "weltgewebe-up"), "--no-pull"],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(activation_log.is_file())
            activation_args = activation_log.read_text(encoding="utf-8").strip()
            self.assertIn(f"--release-dir {release_dir}", activation_args)
            self.assertIn(f"--commit {commit}", activation_args)

            activation_log.unlink()
            activator.chmod(0o775)
            unsafe = subprocess.run(
                [str(ROOT / "scripts" / "weltgewebe-up"), "--no-pull"],
                cwd=ROOT,
                env=env,
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertFalse(activation_log.exists())
            self.assertIn(
                "production reconciler activator has unsafe ownership or mode",
                unsafe.stderr,
            )

    def test_release_activator_rejects_unsafe_and_non_git_releases(self) -> None:
        sudo_probe = subprocess.run(
            ["sudo", "-n", "true"],
            check=False,
            capture_output=True,
            text=True,
        )
        if sudo_probe.returncode != 0:
            self.skipTest("passwordless sudo is unavailable for root-safety tests")

        base = Path(tempfile.mkdtemp(prefix="weltgewebe-activator-root-"))
        commit = "b" * 40
        script = ROOT / "scripts" / "ops" / "activate-production-reconciler-from-release.sh"
        build_user = os.environ.get("USER", "runner")
        try:
            unsafe_root = base / "unsafe-releases"
            unsafe_dir = unsafe_root / commit
            (unsafe_dir / "scripts" / "ops").mkdir(parents=True)
            unsafe = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "env",
                    f"WELTGEWEBE_RELEASE_ROOT={unsafe_root}",
                    str(script),
                    "--release-dir",
                    str(unsafe_dir),
                    "--commit",
                    commit,
                    "--build-user",
                    build_user,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(unsafe.returncode, 0)
            self.assertIn("release root is not root-owned", unsafe.stderr)

            safe_root = base / "safe-releases"
            safe_dir = safe_root / commit
            installer = safe_dir / "scripts" / "ops" / "install-production-reconciler.sh"
            subprocess.run(
                [
                    "sudo",
                    "-n",
                    "install",
                    "-d",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0755",
                    str(installer.parent),
                ],
                check=True,
            )
            subprocess.run(
                [
                    "sudo",
                    "-n",
                    "install",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0755",
                    "/bin/true",
                    str(installer),
                ],
                check=True,
            )
            invalid_git = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "env",
                    f"WELTGEWEBE_RELEASE_ROOT={safe_root}",
                    str(script),
                    "--release-dir",
                    str(safe_dir),
                    "--commit",
                    commit,
                    "--build-user",
                    build_user,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(invalid_git.returncode, 0)
            self.assertIn("release directory is not a valid Git repository", invalid_git.stderr)

            release_root_link = base / "release-root-link"
            release_root_link.symlink_to(safe_root, target_is_directory=True)
            symlinked = subprocess.run(
                [
                    "sudo",
                    "-n",
                    "env",
                    f"WELTGEWEBE_RELEASE_ROOT={release_root_link}",
                    str(script),
                    "--release-dir",
                    str(safe_dir),
                    "--commit",
                    commit,
                    "--build-user",
                    build_user,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(symlinked.returncode, 0)
            self.assertIn("release root is missing or unsafe", symlinked.stderr)
        finally:
            subprocess.run(
                ["sudo", "-n", "rm", "-rf", "--", str(base)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_staged_unit_verification_allows_missing_initial_env_file(self) -> None:
        installer = self.read("scripts/ops/install-production-reconciler.sh")
        service = self.read(
            "infra/systemd/system/weltgewebe-production-reconcile.service"
        )
        self.assertIn(
            "EnvironmentFile=-/etc/weltgewebe/production-reconciler.env", service
        )
        staged_verify = installer.index("systemd-analyze verify")
        env_install = installer.index(
            'atomic_install "$staging/production-reconciler.env"'
        )
        self.assertLess(staged_verify, env_install)

    def test_release_activator_rejects_non_root_execution(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("non-root guard requires a non-root test process")
        completed = subprocess.run(
            [
                str(
                    ROOT
                    / "scripts"
                    / "ops"
                    / "activate-production-reconciler-from-release.sh"
                ),
                "--release-dir",
                "/tmp/not-a-production-release",
                "--commit",
                "0" * 40,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("must run as root", completed.stderr)

    def test_github_contract_serializes_main_observers(self) -> None:
        workflow = self.read(".github/workflows/production-live-contract.yml")
        self.assertIn("production-live-main", workflow)
        self.assertIn("github.event_name == 'pull_request' || github.event_name == 'push'", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn('cron: "*/5 * * * *"', workflow)
        self.assertIn("wait_seconds=1200", workflow)
        self.assertNotIn("production-live-contract-${{ github.event_name }}", workflow)
        self.assertIn("+refs/heads/main:refs/remotes/origin/main", workflow)
        self.assertIn('BASE_SHA="$(git rev-parse refs/remotes/origin/main)"', workflow)
        self.assertIn('git diff --binary "$BASE_SHA...$HEAD_SHA"', workflow)
        self.assertIn("review-diff-manifest.txt", workflow)
        self.assertIn("review-diff-pr-", workflow)
        self.assertIn(
            '"scripts/ops/activate-production-reconciler-from-release.sh"', workflow
        )
        self.assertIn('"scripts/weltgewebe-up"', workflow)
        self.assertIn(
            "bash -n scripts/ops/activate-production-reconciler-from-release.sh",
            workflow,
        )
        self.assertIn("bash -n scripts/weltgewebe-up", workflow)


if __name__ == "__main__":
    unittest.main()

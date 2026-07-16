from __future__ import annotations

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
        public_readback = script.index('api_body="$(curl', deploy)
        post_check = script.index('post_deploy_main="$(fetch_main)"', public_readback)
        verified_link = script.index('ln -sfn "receipts/$COMMIT.json"', post_check)
        self.assertLess(deploy, public_readback)
        self.assertLess(public_readback, post_check)
        self.assertLess(post_check, verified_link)
        self.assertIn("superseded_after_deploy", script)
        self.assertIn("exit 75", script)
        self.assertNotIn("curl -fsSI", script)

    def test_deploy_helper_preserves_legacy_checkout_and_binds_main(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        self.assertIn("+refs/heads/main:refs/remotes/origin/main", script)
        self.assertIn('worktree add --detach "$release_dir" "$COMMIT"', script)
        for forbidden in ("git reset", "git clean", "git switch", "git pull"):
            self.assertNotIn(forbidden, script)
        self.assertIn("flock -n 9", script)
        self.assertIn("ARCHIVE_VALIDATOR", script)
        self.assertIn("validate_release_tree", script)
        self.assertIn("release contains unexpected state", script)
        self.assertIn("release directory is not root-owned", script)
        self.assertIn('find "$release_dir/apps/web/build" -type f -exec chmod 0644', script)
        self.assertIn('ln -s "$basemap_real" "$release_dir/build/basemap"', script)
        self.assertIn("basemap link escapes the canonical data root", script)
        self.assertIn("-type l -print0", script)
        self.assertIn('install -d -m 0700 "$STATE_ROOT/receipts"', script)

    def test_reconciler_has_bounded_storage_and_state_transitions(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        for state in (
            "observed",
            "building",
            "artifact_validated",
            "deferred",
            "superseded_after_deploy",
            "superseded_after_verify",
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

    def test_installer_is_exact_commit_bound_and_parameterizes_build_user(self) -> None:
        script = self.read("scripts/ops/install-production-reconciler.sh")
        self.assertIn("--commit", script)
        self.assertIn('remote_main" == "$COMMIT', script)
        self.assertIn('git -C "$REPO_DIR" show "$COMMIT:$source_path"', script)
        self.assertIn("production-reconciler.env", script)
        self.assertIn("installed-contract.sha256", script)
        self.assertNotIn("Environment=WELTGEWEBE_BUILD_USER=alex", script)

    def test_github_contract_serializes_main_observers(self) -> None:
        workflow = self.read(".github/workflows/production-live-contract.yml")
        self.assertIn("production-live-main", workflow)
        self.assertIn("github.event_name == 'pull_request' || github.event_name == 'push'", workflow)
        self.assertIn("ref: main", workflow)
        self.assertIn('cron: "*/5 * * * *"', workflow)
        self.assertIn("wait_seconds=1200", workflow)
        self.assertNotIn("production-live-contract-${{ github.event_name }}", workflow)
        self.assertIn(
            "+refs/heads/main:refs/remotes/origin/main", workflow
        )
        self.assertIn(
            'BASE_SHA="$(git rev-parse refs/remotes/origin/main)"', workflow
        )
        self.assertIn('git diff --binary "$BASE_SHA...$HEAD_SHA"', workflow)
        self.assertIn("review-diff-manifest.txt", workflow)
        self.assertIn("review-diff-pr-", workflow)


if __name__ == "__main__":
    unittest.main()

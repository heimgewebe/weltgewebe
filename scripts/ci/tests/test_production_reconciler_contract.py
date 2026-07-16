from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[3]


class ProductionReconcilerContractTests(unittest.TestCase):
    def read(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_deploy_helper_preserves_legacy_checkout_and_binds_main(self) -> None:
        script = self.read("scripts/ops/deploy-exact-commit-vps.sh")
        self.assertIn("+refs/heads/main:refs/remotes/origin/main", script)
        self.assertIn('remote_main" == "$COMMIT', script)
        self.assertIn('worktree add --detach "$release_dir" "$COMMIT"', script)
        for forbidden in ("git reset", "git clean", "git switch", "git pull"):
            self.assertNotIn(forbidden, script)
        self.assertIn("flock -n 9", script)
        self.assertIn("live API serves", script)
        self.assertIn("live frontend serves", script)
        self.assertIn("ARCHIVE_VALIDATOR", script)
        self.assertIn("validate_release_tree", script)
        self.assertIn("release contains unexpected state", script)
        self.assertIn("release directory is not root-owned", script)
        self.assertIn('find "$release_dir/apps/web/build" -type f -exec chmod 0644', script)
        self.assertIn('ln -s "$basemap_real" "$release_dir/build/basemap"', script)
        self.assertIn("basemap link escapes the canonical data root", script)
        self.assertIn("-type l -print0", script)
        self.assertNotIn("--reflink=auto", script)
        self.assertNotIn("cp -al", script)
        self.assertIn('install -d -m 0700 "$STATE_ROOT/receipts"', script)

    def test_reconciler_rechecks_main_after_ephemeral_build(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        self.assertGreaterEqual(script.count("refs/remotes/origin/main"), 4)
        self.assertIn("built=$target_commit current=$current_main", script)
        self.assertIn('archive --format=tar --output="$temporary_source"', script)
        self.assertIn('"$DEPLOY_HELPER"', script)
        self.assertIn('"$LIVE_VERIFIER"', script)
        self.assertIn('"$ARCHIVE_VALIDATOR" "$temporary_artifact"', script)
        self.assertNotIn("worktree add", script)
        for forbidden in ("git reset", "git clean", "git switch", "git pull"):
            self.assertNotIn(forbidden, script)

    def test_reconciler_build_cannot_write_release_or_source(self) -> None:
        script = self.read("scripts/ops/reconcile-production-main-vps.sh")
        self.assertIn(
            "docker.io/library/node@sha256:8898f8ed3c0126667837b678979b4ed83306c856a1227c8bf5f5f77740c25cd6",
            script,
        )
        self.assertIn("docker run --rm", script)
        self.assertIn("--cap-drop ALL", script)
        self.assertIn("--security-opt no-new-privileges", script)
        self.assertIn("--read-only", script)
        self.assertIn("--pids-limit 512", script)
        self.assertIn("--memory 2g", script)
        self.assertIn("--cpus 2", script)
        self.assertIn("--tmpfs /workspace:rw,exec,nosuid,nodev,size=3g,mode=1777", script)
        self.assertIn("dst=/source.tar,readonly", script)
        self.assertIn('GIT_COMMIT_SHA="$target_commit"', script)
        self.assertIn(') > "$temporary_artifact"', script)
        self.assertNotIn("/var/run/docker.sock", script)
        self.assertNotIn("SSH_AUTH_SOCK", script)
        self.assertNotIn("--privileged", script)
        self.assertNotIn("dst=/opt/weltgewebe", script)
        self.assertNotIn("dst=/opt/weltgewebe-releases", script)

    def test_systemd_timer_is_vps_local_and_serial(self) -> None:
        service = self.read(
            "infra/systemd/system/weltgewebe-production-reconcile.service"
        )
        timer = self.read(
            "infra/systemd/system/weltgewebe-production-reconcile.timer"
        )
        self.assertIn(
            "/usr/local/libexec/weltgewebe-reconcile-production-main",
            service,
        )
        self.assertIn("RuntimeMaxSec=7200", service)
        self.assertIn("NoNewPrivileges=true", service)
        self.assertIn("OnUnitActiveSec=2min", timer)
        self.assertIn("Persistent=true", timer)

    def test_installer_uses_root_owned_fixed_entrypoints(self) -> None:
        script = self.read("scripts/ops/install-production-reconciler.sh")
        for entrypoint in (
            "weltgewebe-deploy-exact-commit",
            "weltgewebe-reconcile-production-main",
            "weltgewebe-validate-web-deploy-archive",
            "weltgewebe-verify-public-release",
        ):
            self.assertIn(f"/usr/local/libexec/{entrypoint}", script)
        self.assertIn("weltgewebe-production-reconcile.timer", script)
        self.assertIn("systemctl enable --now", script)

    def test_github_contract_detects_stale_production(self) -> None:
        workflow = self.read(".github/workflows/production-live-contract.yml")
        self.assertIn('cron: "*/5 * * * *"', workflow)
        self.assertIn("wait_seconds=1200", workflow)
        self.assertIn("verify_public_release_commit.py", workflow)
        self.assertIn("production-live-receipt.json", workflow)


if __name__ == "__main__":
    unittest.main()

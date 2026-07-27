from __future__ import annotations

import json
import textwrap
import unittest
from pathlib import Path

from scripts.ci.tests.test_deploy_exact_commit_integration import (
    DEPLOY_SCRIPT,
    DeployExactCommitIntegrationTests,
    run,
)


class ProductionReceiptResilienceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = DeployExactCommitIntegrationTests(methodName="runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def test_public_observation_repairs_safe_malformed_deployment_receipt(
        self,
    ) -> None:
        fixture = self.fixture
        malformed = fixture.root / "malformed-receipt.json"
        malformed.write_text("{not-json\n", encoding="utf-8")
        receipt = fixture.state / "receipts" / f"{fixture.commit}.json"
        run(
            fixture.privileged(
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
        run(
            fixture.privileged(
                [
                    "install",
                    "-o",
                    "root",
                    "-g",
                    "root",
                    "-m",
                    "0600",
                    str(malformed),
                    str(receipt),
                ]
            )
        )

        result = fixture.reconcile_existing_public_commit()
        fixture.restore_test_ownership()

        self.assertEqual(result.returncode, 0, result.stderr)
        repaired = json.loads(receipt.read_text(encoding="utf-8"))
        self.assertEqual(repaired["schema_version"], 5)
        self.assertEqual(repaired["result"], "verified_observed")
        self.assertEqual(repaired["commit"], fixture.commit)

    def test_inherited_contention_survives_shared_slot_overwrite(self) -> None:
        fixture = self.fixture
        wrapper = fixture.bin / "contention-race-deploy"
        wrapper.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env bash
                set -euo pipefail
                exec 9<> "$WELTGEWEBE_DEPLOY_STATE_ROOT/production-deployment.lock"
                set +e
                "$TEST_DEPLOY_SCRIPT" "$@"
                inherited_rc=$?
                set -e
                exec 9>&-
                set +e
                env \
                  -u WELTGEWEBE_PRODUCTION_LOCK_FD \
                  -u WELTGEWEBE_PRODUCTION_LOCK_DOMAIN \
                  -u WELTGEWEBE_PRODUCTION_LOCK_OWNER_ENTRYPOINT \
                  -u WELTGEWEBE_DEPLOY_INVOCATION_ID \
                  "$TEST_DEPLOY_SCRIPT" "$@" >/dev/null 2>&1
                set -e
                exit "$inherited_rc"
                """
            ),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)

        result = fixture.reconcile_stale_public_commit(
            deploy_helper=wrapper,
            extra_env={"TEST_DEPLOY_SCRIPT": str(DEPLOY_SCRIPT)},
        )
        fixture.restore_test_ownership()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "production lock contention during inherited handoff",
            result.stderr,
        )
        self.assertNotIn("unexplained temporary failure", result.stderr)
        invocation_receipts = list(
            (fixture.state / "receipts" / "contention").glob("*.json")
        )
        self.assertEqual(len(invocation_receipts), 1)
        self.assertTrue((fixture.state / "receipts" / "last-contention.json").exists())

    def test_permissive_caller_umask_produces_canonical_release_modes(
        self,
    ) -> None:
        fixture = self.fixture
        result = fixture.deploy(advance=False, umask="000")
        fixture.restore_test_ownership()

        self.assertEqual(result.returncode, 0, result.stderr)
        release = fixture.releases / fixture.commit
        self.assertEqual(release.stat().st_mode & 0o777, 0o755)
        self.assertEqual(
            (release / "apps/web/placeholder.txt").stat().st_mode & 0o777,
            0o644,
        )
        receipt = fixture.state / "receipts" / f"{fixture.commit}.json"
        self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)

    def test_reviewed_resilience_preconditions_are_already_present(self) -> None:
        deploy = Path(DEPLOY_SCRIPT).read_text(encoding="utf-8")
        reconciler = (
            Path(DEPLOY_SCRIPT)
            .with_name("reconcile-production-main-vps.sh")
            .read_text(encoding="utf-8")
        )

        for initialized in ('started_at=""', 'api_commit=""', 'frontend_commit=""'):
            self.assertIn(initialized, deploy)
        receipt_root_creation = reconciler.index(
            '"$ARTIFACT_ROOT" "$RECEIPT_ROOT" "$DEPLOY_RECEIPT_ROOT" "$DOCKER_CONFIG"'
        )
        contention_root_creation = reconciler.index(
            'install -d -o root -g root -m 0700 "$DEPLOY_RECEIPT_ROOT/contention"'
        )
        observation = reconciler.index('if "$LIVE_VERIFIER"')
        self.assertLess(receipt_root_creation, observation)
        self.assertLess(contention_root_creation, observation)


if __name__ == "__main__":
    unittest.main()

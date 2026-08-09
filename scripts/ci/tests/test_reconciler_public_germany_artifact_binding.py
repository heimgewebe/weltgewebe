from __future__ import annotations

import unittest

from scripts.ci.tests.test_deploy_exact_commit_integration import (
    DeployExactCommitIntegrationTests,
)


class ReconcilerPublicGermanyArtifactBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = DeployExactCommitIntegrationTests(
            methodName="test_reconciler_keeps_same_commit_germany_public_bundle_as_noop"
        )
        try:
            self.fixture.setUp()
        except Exception:
            self.fixture.doCleanups()
            raise
        self.addCleanup(self.fixture.doCleanups)

    def test_reconciler_rejects_same_size_stale_public_pmtiles_payload(self) -> None:
        curl_shim = self.fixture.bin / "curl"
        shim = curl_shim.read_text(encoding="utf-8")
        expected = '                  head -c 127 "$pmtiles"\n'
        replacement = (
            "                  printf 'PMTiles'\n"
            "                  printf 'x%.0s' {1..120}\n"
        )
        self.assertIn(expected, shim)
        curl_shim.write_text(shim.replace(expected, replacement, 1), encoding="utf-8")
        curl_shim.chmod(0o755)

        result = self.fixture.reconcile_existing_public_commit(
            extra_env={"PUBLIC_COMMIT": self.fixture.commit}
        )
        self.fixture.restore_test_ownership()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("reason=basemap_identity_drift", result.stdout)
        self.assertNotIn("production_reconcile=noop", result.stdout)
        self.assertNotIn("production_reconcile=verified", result.stdout)
        self.assertIn(
            "public Germany PMTiles range response does not match selected Germany artifact",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()

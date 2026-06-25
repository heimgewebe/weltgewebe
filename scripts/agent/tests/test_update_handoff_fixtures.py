from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.agent import update_handoff_fixtures as updater


class TestUpdateHandoffFixtures(unittest.TestCase):
    def test_digest_fixture_inventory_is_complete(self):
        self.assertEqual(
            updater.DIGEST_FIXTURES,
            (
                Path("tests/fixtures/agent/handoff-valid.json"),
                Path("tests/fixtures/agent/handoff-valid-residual-gap.json"),
                Path("tests/fixtures/agent/handoff-invalid-path.json"),
                Path("tests/fixtures/agent/handoff-invalid-outcome.json"),
            ),
        )

    def _repo(self) -> Path:
        root = Path(tempfile.mkdtemp())
        fixture_dir = root / "tests/fixtures/agent"
        fixture_dir.mkdir(parents=True)
        (fixture_dir / "handoff-task.json").write_text('{"task_id":"X-001"}\n')
        for rel in updater.DIGEST_FIXTURES:
            (root / rel).write_text('{"task_contract_sha256":"bad"}\n')
        return root

    def test_check_does_not_write(self):
        root = self._repo()
        path = root / updater.DIGEST_FIXTURES[0]
        before = path.read_text()
        self.assertEqual(
            updater.check_or_update(root, write=False),
            [str(path) for path in updater.DIGEST_FIXTURES],
        )
        self.assertEqual(path.read_text(), before)

    def test_write_is_idempotent(self):
        root = self._repo()
        self.assertTrue(updater.check_or_update(root, write=True))
        self.assertEqual(updater.check_or_update(root, write=True), [])
        expected = updater.task_digest(root)
        for rel in updater.DIGEST_FIXTURES:
            data = json.loads((root / rel).read_text())
            self.assertEqual(data["task_contract_sha256"], expected)


if __name__ == "__main__":
    unittest.main()

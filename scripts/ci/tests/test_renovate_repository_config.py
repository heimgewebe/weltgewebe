from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "renovate.json"
EXPECTED_RULE = {
    "description": "Attach proven governance metadata to allowlisted web tooling patches",
    "matchManagers": ["npm"],
    "matchFileNames": ["apps/web/package.json"],
    "matchPackageNames": ["eslint", "postcss"],
    "matchUpdateTypes": ["patch"],
    "prBodyNotes": [
        "<!-- weltgewebe-risk: R2 -->",
        "<!-- weltgewebe-attention-impact: none -->",
        "<!-- weltgewebe-attention-rationale: Allowlisted dependency-only patch update in apps/web; no attention-domain semantics, prioritization, triggers, or user-facing attention behavior changed. -->",
    ],
}


class RenovateRepositoryConfigTests(unittest.TestCase):
    def test_config_is_narrow_and_non_automerge(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))

        self.assertEqual(
            config,
            {
                "$schema": "https://docs.renovatebot.com/renovate-schema.json",
                "automerge": False,
                "packageRules": [EXPECTED_RULE],
            },
        )

    def test_rule_cannot_expand_beyond_proven_patch_tooling(self) -> None:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        rule = config["packageRules"][0]

        self.assertEqual(rule["matchManagers"], ["npm"])
        self.assertEqual(rule["matchFileNames"], ["apps/web/package.json"])
        self.assertEqual(rule["matchPackageNames"], ["eslint", "postcss"])
        self.assertEqual(rule["matchUpdateTypes"], ["patch"])
        self.assertNotIn("automerge", rule)


if __name__ == "__main__":
    unittest.main()

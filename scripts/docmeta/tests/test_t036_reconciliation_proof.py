from collections import Counter
from pathlib import Path
import re
import unittest


PROOF = Path("docs/proofs/weltgewebe-os-v1-t036-documentation-drift-reconciliation.md")
LIFECYCLE = Path("docs/_generated/report-lifecycle.md")
ROW_RE = re.compile(
    r"^\| DRIFT-(\d{3}) \| P[12] \| "
    r"(weiterhin gültig|bereits behoben|superseded|falsch-positiv) \|"
)
EXPECTED = {
    "weiterhin gültig": 16,
    "bereits behoben": 5,
    "superseded": 8,
    "falsch-positiv": 23,
}
ARCHIVED_BY_T036 = (
    "auth-persistence-runtime-target-reconciliation.md",
    "domain-account-email-uniqueness-audit.md",
    "domain-account-write-path-proof.md",
    "domain-backfill-proof.md",
    "domain-edge-reference-audit.md",
    "domain-node-write-path-proof.md",
    "domain-read-path-proof.md",
)


class T036ReconciliationProofTests(unittest.TestCase):
    def test_all_52_findings_are_uniquely_dispositioned_and_matrix_is_derived(self):
        text = PROOF.read_text(encoding="utf-8")
        rows = [match.groups() for line in text.splitlines() if (match := ROW_RE.match(line))]

        ids = [int(item_id) for item_id, _ in rows]
        self.assertEqual(ids, list(range(1, 53)))
        self.assertEqual(len(set(ids)), 52)

        counts = Counter(disposition for _, disposition in rows)
        self.assertEqual(dict(counts), EXPECTED)
        self.assertEqual(sum(counts.values()), 52)

        matrix_row = "| 52 | 16 | 5 | 8 | 23 |"
        self.assertEqual(text.count(matrix_row), 1)

    def test_generated_lifecycle_projection_contains_t036_archivals(self):
        text = LIFECYCLE.read_text(encoding="utf-8")
        active, archived_and_after = text.split("## Archived Reports", 1)
        for filename in ARCHIVED_BY_T036:
            self.assertNotIn(filename, active.split("## Active Reports", 1)[1])
            self.assertIn(filename, archived_and_after)
        self.assertIn("| active | 26 |", text)
        self.assertIn("| archived | 13 |", text)
        self.assertIn("| findings_total | 0 |", text)


if __name__ == "__main__":
    unittest.main()

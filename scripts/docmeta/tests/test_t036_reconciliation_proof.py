from collections import Counter
from pathlib import Path
import re
import unittest


PROOF = Path("docs/proofs/weltgewebe-os-v1-t036-documentation-drift-reconciliation.md")
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


if __name__ == "__main__":
    unittest.main()

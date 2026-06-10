import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import scripts.docmeta.generate_system_map as gen_mod


class TestGenerateSystemMap(unittest.TestCase):
    def _render_system_map(self) -> str:
        with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as f:
            tmp = f.name
        try:
            real_join = os.path.join

            def patched_join(*args):
                if len(args) >= 2 and args[-1] == 'system-map.md':
                    return tmp
                return real_join(*args)

            with patch('scripts.docmeta.generate_system_map.os.path.join', side_effect=patched_join):
                gen_mod.main()
            return Path(tmp).read_text(encoding='utf-8')
        finally:
            os.unlink(tmp)

    def test_no_freshness_status_in_output(self):
        self.assertNotIn('freshness_status', self._render_system_map())

    def test_last_reviewed_present_in_output(self):
        self.assertIn('last_reviewed', self._render_system_map())

    def test_column_structure_without_freshness(self):
        content = self._render_system_map()
        expected_header = '|id|path|role|organ|status|last_reviewed|depends_on|verifies_with|missing_scripts|'
        expected_sep = '|---|---|---|---|---|---|---|---|---|'
        self.assertIn(expected_header, content)
        self.assertIn(expected_sep, content)
        self.assertEqual(expected_header.count('|'), expected_sep.count('|'))

    def test_generator_deterministic(self):
        self.assertEqual(self._render_system_map(), self._render_system_map())


class TestSystemMapDependsOnColumn(unittest.TestCase):
    """The depends_on column reflects the canonical extract_depends_on semantics."""

    DEPENDS_ON_COLUMN = 6  # |id|path|role|organ|status|last_reviewed|depends_on|...

    def _render_with_fixture(self, repo_index, docs):
        temp_dir = tempfile.mkdtemp()
        try:
            for relpath, content in docs.items():
                full = os.path.join(temp_dir, relpath)
                os.makedirs(os.path.dirname(full), exist_ok=True)
                with open(full, 'w', encoding='utf-8') as f:
                    f.write(content)
            os.makedirs(os.path.join(temp_dir, 'docs', '_generated'), exist_ok=True)
            policy = {"mode": "warn", "strict_manifest": False, "warn_days": 90, "fail_days": 180}
            with patch('scripts.docmeta.generate_system_map.parse_review_policy', return_value=policy), \
                 patch('scripts.docmeta.generate_system_map.parse_repo_index', return_value=repo_index), \
                 patch('scripts.docmeta.generate_system_map.REPO_ROOT', temp_dir):
                gen_mod.main()
            out = os.path.join(temp_dir, 'docs', '_generated', 'system-map.md')
            return Path(out).read_text(encoding='utf-8')
        finally:
            shutil.rmtree(temp_dir)

    def _row_cells(self, content, doc_id):
        # Split on '|' and drop the empty leading/trailing fields produced by the
        # outer pipes. Avoids collapsing trailing empty cells (e.g. empty depends_on).
        for line in content.splitlines():
            if line.startswith(f"|{doc_id}|"):
                return [c.strip() for c in line.split("|")[1:-1]]
        return None

    def test_direct_depends_on_appears_and_empty_stays_empty(self):
        repo_index = {
            "zones": {"norm": {"path": "docs/", "canonical_docs": ["a.md", "b.md"]}},
            "checks": [],
        }
        docs = {
            "docs/a.md": "---\nid: doc-a\nrole: norm\nstatus: canonical\n"
                         "depends_on:\n  - doc-b\nverifies_with: []\n---\n",
            "docs/b.md": "---\nid: doc-b\nrole: norm\nstatus: canonical\n"
                         "depends_on: []\nverifies_with: []\n---\n",
        }
        content = self._render_with_fixture(repo_index, docs)

        a_cells = self._row_cells(content, "doc-a")
        self.assertIsNotNone(a_cells)
        self.assertEqual(a_cells[self.DEPENDS_ON_COLUMN], "doc-b")

        b_cells = self._row_cells(content, "doc-b")
        self.assertIsNotNone(b_cells)
        self.assertEqual(b_cells[self.DEPENDS_ON_COLUMN], "")

    def test_empty_direct_depends_on_wins_over_legacy_relation(self):
        """``depends_on: []`` plus a legacy ``relations[type=depends_on]`` entry
        must produce an empty depends_on column — the direct key is canonical."""
        repo_index = {
            "zones": {"norm": {"path": "docs/", "canonical_docs": ["c.md"]}},
            "checks": [],
        }
        docs = {
            "docs/c.md": (
                "---\n"
                "id: doc-c\nrole: norm\nstatus: canonical\n"
                "depends_on: []\n"
                "verifies_with: []\n"
                "relations:\n"
                "  - type: depends_on\n"
                "    target: docs/old.md\n"
                "---\n"
            ),
        }
        content = self._render_with_fixture(repo_index, docs)
        c_cells = self._row_cells(content, "doc-c")
        self.assertIsNotNone(c_cells)
        self.assertEqual(c_cells[self.DEPENDS_ON_COLUMN], "")

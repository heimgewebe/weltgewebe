import os
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

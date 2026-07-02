import unittest
from unittest.mock import patch

import scripts.docmeta.generate_backlinks as gen

class TestGenerateBacklinks(unittest.TestCase):
    @patch('scripts.docmeta.generate_backlinks.os.makedirs')
    @patch('scripts.docmeta.generate_backlinks.collect_file_relations')
    def test_backlinks_eof_newline_format(self, mock_collect, mock_makedirs):
        # Provide some dummy relations to generate blocks
        mock_collect.return_value = {
            "docs/source_A.md": [{"type": "relates_to", "target": "docs/target_X.md"}],
            "docs/source_B.md": [{"type": "relates_to", "target": "docs/target_X.md"}],
            "docs/source_C.md": [{"type": "implements", "target": "docs/target_Y.md"}],
        }

        full_content = gen.render_backlinks()

        # Basic format checks
        self.assertIn("## docs/target_X.md\n\n- ", full_content, "Must have a blank line after heading")
        self.assertIn("## docs/target_Y.md", full_content)

        # Strict EOF and newline checks
        # 1. Ends with EXACTLY one newline
        self.assertTrue(full_content.endswith("\n"), "Content should end with a newline")
        self.assertFalse(full_content.endswith("\n\n"), "Content must not end with two newlines (no blank line at EOF)")

        # 2. Blocks are cleanly separated by double newlines (\n\n)
        # "docs/target_Y" block comes after "docs/target_X", let's check the transition.
        self.assertIn("\n\n## docs/target_Y.md", full_content, "Blocks must be separated by exactly one blank line (\\n\\n)")

if __name__ == "__main__":
    unittest.main()

import os
import tempfile
import unittest

from scripts.docmeta.docmeta import parse_frontmatter

class TestDocMetaParser(unittest.TestCase):
    def test_parse_frontmatter_crlf_eof(self):
        content = "---\r\nid: test-id\r\nrole: norm\r\n---"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-id')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_spacing(self):
        content = "---\n id : test \n role : norm \n---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

if __name__ == '__main__':
    unittest.main()

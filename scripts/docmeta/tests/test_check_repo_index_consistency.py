import tempfile
import unittest
from pathlib import Path

from scripts.docmeta.check_repo_index_consistency import (
    find_unregistered_canonical_docs,
    registered_canonical_paths,
)


class CanonicalRegistryTests(unittest.TestCase):
    def test_registered_paths_are_repo_relative(self):
        manifest = {
            "zones": {
                "product": {
                    "path": "docs/specs/",
                    "canonical_docs": ["ui.md", "map.md"],
                }
            }
        }
        self.assertEqual(
            registered_canonical_paths(manifest),
            {"docs/specs/ui.md", "docs/specs/map.md"},
        )

    def test_unregistered_canonical_document_is_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs" / "specs").mkdir(parents=True)
            (root / "docs" / "specs" / "registered.md").write_text(
                "---\nid: registered\nstatus: canonical\n---\n",
                encoding="utf-8",
            )
            (root / "docs" / "stray.md").write_text(
                "---\nid: stray\nstatus: canonical\n---\n",
                encoding="utf-8",
            )
            manifest = {
                "zones": {
                    "product": {
                        "path": "docs/specs/",
                        "canonical_docs": ["registered.md"],
                    }
                }
            }
            self.assertEqual(
                find_unregistered_canonical_docs(manifest, str(root)),
                ["docs/stray.md"],
            )

    def test_deprecated_and_generated_documents_are_ignored(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "docs" / "_generated").mkdir(parents=True)
            (root / "docs" / "old.md").write_text(
                "---\nid: old\nstatus: deprecated\n---\n",
                encoding="utf-8",
            )
            (root / "docs" / "_generated" / "map.md").write_text(
                "---\nid: generated\nstatus: canonical\n---\n",
                encoding="utf-8",
            )
            self.assertEqual(find_unregistered_canonical_docs({"zones": {}}, str(root)), [])


if __name__ == "__main__":
    unittest.main()

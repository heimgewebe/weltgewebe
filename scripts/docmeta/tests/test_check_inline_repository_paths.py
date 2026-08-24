import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.docmeta import check_links


class InlineRepositoryPathTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "docs").mkdir()
        (self.root / "apps" / "api" / "src").mkdir(parents=True)
        (self.root / "scripts" / "docmeta").mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_doc(self, name: str, body: str, *, status: str = "active") -> tuple[str, str]:
        rel = f"docs/{name}.md"
        content = (
            "---\n"
            f"id: docs.{name}\n"
            "doc_type: guide\n"
            f"status: {status}\n"
            "---\n\n"
            f"{body}\n"
        )
        (self.root / rel).write_text(content, encoding="utf-8")
        return rel, content

    def test_missing_repo_path_is_reported_for_current_document(self):
        rel, content = self._write_doc(
            "broken",
            "Der Beleg liegt in `apps/api/src/missing.rs`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, ["apps/api/src/missing.rs"])

    def test_existing_repo_path_passes(self):
        (self.root / "apps" / "api" / "src" / "lib.rs").write_text("", encoding="utf-8")
        rel, content = self._write_doc(
            "existing",
            "Der Beleg liegt in `apps/api/src/lib.rs`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, [])

    def test_unknown_first_component_typo_is_not_silently_skipped(self):
        rel, content = self._write_doc(
            "typo",
            "Aktueller Repositorypfad: `apss/api/src/lib.rs`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, ["apss/api/src/lib.rs"])

    def test_package_relative_src_path_is_not_silently_skipped(self):
        rel, content = self._write_doc(
            "package-relative",
            "Aktueller Repositorypfad: `src/lib.rs`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, ["src/lib.rs"])

    def test_tracked_document_discovery_fails_closed(self):
        failure = subprocess.CalledProcessError(128, ["git", "ls-files"])
        with patch("scripts.docmeta.check_links.subprocess.run", side_effect=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                check_links._tracked_markdown_files(str(self.root))

    def test_retired_document_is_not_reactivated_as_path_truth(self):
        rel, content = self._write_doc(
            "retired",
            "Historisch: `apps/api/src/gone.rs`.",
            status="deprecated",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_external_commit_bound_reference_is_not_local_path_claim(self):
        rel, content = self._write_doc(
            "external",
            "Die Evidenz ist an `heimgewebe/heimserver@15dfbd6cc1c8899ec030ac6666464db4bc132c71` "
            "gebunden; dort gilt `scripts/heimberry/install_weltgewebe_ddns.sh`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_explicit_future_target_is_not_current_path_claim(self):
        rel, content = self._write_doc(
            "future",
            "Spec erstellen, bevor `apps/worker/` implementiert wird.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_canonical_status_is_current(self):
        rel, content = self._write_doc(
            "canonical",
            "Aktueller Pfad: `apps/api/src/missing.rs`.",
            status="canonical",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, ["apps/api/src/missing.rs"])


if __name__ == "__main__":
    unittest.main()

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

    def test_assignment_token_is_not_treated_as_repository_path(self):
        rel, content = self._write_doc(
            "assignment",
            "Runtime: `APP_BASE_URL=https://weltgewebe.net`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_equals_inside_repository_path_does_not_evade_check(self):
        candidate = "configs/foo=bar.json"
        rel, content = self._write_doc(
            "equals-path",
            f"Aktueller Repositorypfad: `{candidate}`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual(total, 1)
        self.assertEqual(broken, [candidate])

    def test_symlink_escape_outside_repository_is_rejected(self):
        outside_dir = self.root.parent / f"{self.root.name}-outside-dir"
        outside_dir.mkdir()
        try:
            (outside_dir / "proof.md").write_text("outside", encoding="utf-8")
            (self.root / "docs" / "external-link").symlink_to(outside_dir, target_is_directory=True)
            candidate = "external-link/proof.md"
            rel, content = self._write_doc(
                "symlink-escape",
                f"Aktueller Repositorypfad: `{candidate}`.",
            )
            total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        finally:
            (self.root / "docs" / "external-link").unlink(missing_ok=True)
            (outside_dir / "proof.md").unlink(missing_ok=True)
            outside_dir.rmdir()
        self.assertEqual(total, 1)
        self.assertEqual(broken, [candidate])

    def test_existing_path_outside_repository_is_rejected(self):
        outside = self.root.parent / f"{self.root.name}-escape.md"
        candidate = f"../../{outside.name}"
        outside.write_text("outside repository", encoding="utf-8")
        try:
            rel, content = self._write_doc(
                "escape",
                f"Aktueller Repositorypfad: `{candidate}`.",
            )
            total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        finally:
            outside.unlink(missing_ok=True)
        self.assertEqual(total, 1)
        self.assertEqual(broken, [candidate])

    def test_policy_scope_is_not_treated_as_repository_existence_claim(self):
        rel, content = self._write_doc(
            "policy-scope",
            "| `secrets/` | **Policy-Scope**, Existenz ist nicht erforderlich |",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_hostname_resource_is_not_repository_path(self):
        rel, content = self._write_doc(
            "hostname-resource",
            "Basemap: `tiles.weltgewebe.org/basemap.pmtiles`.",
        )
        total, broken = check_links._inline_path_findings(str(self.root), rel, content)
        self.assertEqual((total, broken), (0, []))

    def test_explicit_ignored_runtime_path_can_be_exempted_without_hiding_typos(self):
        rel, content = self._write_doc(
            "runtime-output",
            "Laufzeitartefakt: `build/runtime-output.json`.",
        )
        total, broken = check_links._inline_path_findings(
            str(self.root),
            rel,
            content,
            ignored_path_predicate=lambda path: path.endswith("build/runtime-output.json"),
        )
        self.assertEqual((total, broken), (1, []))

    def test_git_ignore_probe_fails_closed_on_git_error(self):
        failure = subprocess.CompletedProcess(
            args=["git", "check-ignore"],
            returncode=128,
            stdout=b"",
            stderr=b"fatal",
        )
        with patch("scripts.docmeta.check_links.subprocess.run", return_value=failure):
            with self.assertRaises(subprocess.CalledProcessError):
                check_links._path_is_git_ignored(
                    str(self.root),
                    str(self.root / "build" / "runtime.json"),
                )

    def test_git_ignore_directory_probe_checks_child_sentinel(self):
        not_ignored = subprocess.CompletedProcess(
            args=["git", "check-ignore"], returncode=1, stdout=b"", stderr=b""
        )
        ignored = subprocess.CompletedProcess(
            args=["git", "check-ignore"], returncode=0, stdout=b"", stderr=b""
        )
        with patch(
            "scripts.docmeta.check_links.subprocess.run",
            side_effect=[not_ignored, ignored],
        ):
            self.assertTrue(
                check_links._path_is_git_ignored(
                    str(self.root),
                    str(self.root / "build"),
                )
            )

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

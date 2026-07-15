from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import scripts.quality.review_governance as review_governance
from scripts.quality.review_governance import (
    Bundle,
    DiffStats,
    GovernanceError,
    evaluate_evidence,
    generate_bundle,
    generate_materialized_bundle,
    load_allowed_attesters,
    minimum_risk_for_paths,
    parse_risk_class,
)


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _comment(
    record: dict,
    *,
    association: str = "OWNER",
    author: str = "alex",
    report_text: str | None = None,
    report_sha256: str | None = None,
    comment_id: int = 1,
) -> dict:
    report = report_text or (
        f"Unabhängiger Reviewbericht von {record.get('reviewer')} zur Achse "
        f"{record.get('review_axis')}. Der exakte Diff wurde auf Korrektheit, "
        "Regressionen, Fehlerszenarien und die im Auftrag genannten Invarianten "
        "geprüft. Es bleiben keine unaufgelösten Mergeblocker."
    )
    payload = dict(record)
    normalized_report = report.replace("\r\n", "\n").replace("\r", "\n").strip()
    payload["report_sha256"] = (
        report_sha256 or hashlib.sha256(normalized_report.encode("utf-8")).hexdigest()
    )
    return {
        "id": comment_id,
        "body": report
        + "\n<!-- weltgewebe-review-evidence\n"
        + json.dumps(payload)
        + "\n-->",
        "author_association": association,
        "user": {"login": author},
        "html_url": "https://example.invalid/review",
        "created_at": "2026-07-14T12:00:00Z",
        "updated_at": "2026-07-14T12:00:00Z",
    }


ALLOWED_ATTESTERS = frozenset({"alex"})


def _review(
    bundle: Bundle,
    *,
    state: str = "APPROVED",
    author: str = "alex",
    association: str = "OWNER",
    commit_id: str | None = None,
    review_id: int = 1,
    submitted_at: str = "2026-07-14T12:00:00Z",
) -> dict:
    return {
        "id": review_id,
        "state": state,
        "commit_id": commit_id or bundle.head_sha,
        "author_association": association,
        "user": {"login": author},
        "html_url": "https://example.invalid/native-review",
        "submitted_at": submitted_at,
    }


def _evaluate(
    *,
    bundle: Bundle,
    risk_class: str,
    comments: list[dict],
    reviews: list[dict] | None = None,
) -> dict:
    return evaluate_evidence(
        bundle=bundle,
        risk_class=risk_class,
        comments=comments,
        reviews=reviews or [],
        allowed_attesters=ALLOWED_ATTESTERS,
    )


def _bundle(
    *, paths: tuple[str, ...] = ("docs/example.md",), changed_lines: int = 2
) -> Bundle:
    additions = changed_lines // 2
    deletions = changed_lines - additions
    return Bundle(
        pr_number=42,
        base_sha="a" * 40,
        head_sha="b" * 40,
        merge_base_sha="c" * 40,
        diff_sha256="d" * 64,
        patch_sha256="e" * 64,
        manifest_path=Path("manifest.json"),
        diff_path=Path("change.diff"),
        patch_path=Path("change.patch"),
        request_path=Path("request.md"),
        stats=DiffStats(paths, additions, deletions, ()),
    )


def _record(
    bundle: Bundle, *, reviewer: str, axis: str, risk: str, verdict: str = "PASS"
) -> dict:
    return {
        "schema_version": 1,
        "pr_number": bundle.pr_number,
        "base_sha": bundle.base_sha,
        "head_sha": bundle.head_sha,
        "diff_sha256": bundle.diff_sha256,
        "risk_class": risk,
        "reviewer": reviewer,
        "review_axis": axis,
        "verdict": verdict,
        "findings_resolved": verdict == "PASS",
    }


class RiskParsingTests(unittest.TestCase):
    def test_exactly_one_risk_marker_is_required(self) -> None:
        self.assertEqual(parse_risk_class("<!-- weltgewebe-risk: R2 -->"), "R2")
        self.assertIsNone(parse_risk_class("none"))
        self.assertIsNone(
            parse_risk_class("<!-- weltgewebe-risk: R1 --><!-- weltgewebe-risk: R2 -->")
        )
        self.assertIsNone(
            parse_risk_class("<!-- weltgewebe-risk: R2 --><!-- weltgewebe-risk: R2 -->")
        )

    def test_sensitive_paths_raise_minimum_risk(self) -> None:
        self.assertEqual(minimum_risk_for_paths(["docs/example.md"]), "R0")
        self.assertEqual(minimum_risk_for_paths(["apps/web/README.md"]), "R0")
        self.assertEqual(minimum_risk_for_paths(["docs/images/map.png"]), "R1")
        self.assertEqual(minimum_risk_for_paths(["apps/web/static/map.webp"]), "R1")
        self.assertEqual(minimum_risk_for_paths(["apps/web/src/app.ts"]), "R2")
        self.assertEqual(minimum_risk_for_paths([".github/workflows/ci.yml"]), "R3")
        self.assertEqual(
            minimum_risk_for_paths([".github/review-evidence-authorities.json"]),
            "R3",
        )
        self.assertEqual(
            minimum_risk_for_paths(["scripts/quality/review_governance.py"]),
            "R3",
        )
        self.assertEqual(
            minimum_risk_for_paths(["docs/process/merge-quality-gate.md"]),
            "R3",
        )
        self.assertEqual(minimum_risk_for_paths(["apps/api/src/auth.rs"]), "R3")


class BundleTests(unittest.TestCase):
    def test_bundle_hash_is_deterministic_for_same_commits(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _git(repo, "init")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.invalid")
            (repo / "README.md").write_text("one\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "base")
            base = _git(repo, "rev-parse", "HEAD")
            (repo / "README.md").write_text("one\ntwo\n", encoding="utf-8")
            _git(repo, "commit", "-am", "change")
            head = _git(repo, "rev-parse", "HEAD")

            first = generate_bundle(
                repo=repo,
                output_dir=Path(temp_dir) / "out-1",
                base_revision=base,
                head_revision=head,
                pr_number=7,
                risk_class="R0",
            )
            second = generate_bundle(
                repo=repo,
                output_dir=Path(temp_dir) / "out-2",
                base_revision=base,
                head_revision=head,
                pr_number=7,
                risk_class="R0",
            )
            self.assertEqual(first.diff_sha256, second.diff_sha256)
            self.assertEqual(first.patch_sha256, second.patch_sha256)
            self.assertEqual(
                first.diff_path.read_bytes(), second.diff_path.read_bytes()
            )
            self.assertEqual(first.stats.changed_files, ("README.md",))

    def test_local_binary_bundle_marks_binary_as_opaque(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.invalid")
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            _git(repo, "add", "README.md")
            _git(repo, "commit", "-m", "base")
            base = _git(repo, "rev-parse", "HEAD")

            (repo / "image.bin").write_bytes(b"\x00\x01binary-payload\xff")
            _git(repo, "add", "image.bin")
            _git(repo, "commit", "-m", "add binary")
            head = _git(repo, "rev-parse", "HEAD")

            bundle = generate_bundle(
                repo=repo,
                output_dir=Path(temp_dir) / "out",
                base_revision=base,
                head_revision=head,
                pr_number=9,
                risk_class="R2",
            )
            self.assertEqual(bundle.stats.binary_files, ("image.bin",))
            self.assertEqual(bundle.stats.opaque_files, ("image.bin",))
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["stats"]["binary_files"], ["image.bin"])
            self.assertEqual(manifest["stats"]["opaque_files"], ["image.bin"])
            self.assertIn(
                "Nicht zuverlässig prüfbare und daher blockierende Dateien",
                bundle.request_path.read_text(encoding="utf-8"),
            )

    def test_local_binary_rename_uses_destination_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.invalid")
            (repo / "old.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00binary")
            _git(repo, "add", "old.png")
            _git(repo, "commit", "-m", "base image")
            base = _git(repo, "rev-parse", "HEAD")
            (repo / "docs").mkdir()
            _git(repo, "mv", "old.png", "docs/new.png")
            _git(repo, "commit", "-m", "rename image")
            head = _git(repo, "rev-parse", "HEAD")

            bundle = generate_bundle(
                repo=repo,
                output_dir=Path(temp_dir) / "out",
                base_revision=base,
                head_revision=head,
                pr_number=10,
                risk_class="R1",
            )
            self.assertEqual(bundle.stats.changed_files, ("docs/new.png",))
            self.assertEqual(bundle.stats.binary_files, ("docs/new.png",))

    def test_materialized_github_bundle_is_hash_bound_and_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            diff_file = root / "pr.diff"
            patch_file = root / "pr.patch"
            metadata_file = root / "metadata.json"
            diff_file.write_bytes(
                b"diff --git a/a.txt b/a.txt\n+new\n"
                b"diff --git a/image.png b/image.png\nBinary files differ\n"
            )
            patch_file.write_bytes(b"From abc Mon Sep 17 00:00:00 2001\n+new\n")
            metadata = {
                "schema_version": 1,
                "pr_number": 17,
                "base_sha": "a" * 40,
                "head_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
                "changed_file_count": 2,
                "changed_files": ["a.txt", "image.png"],
                "additions": 1,
                "deletions": 0,
                "opaque_files": ["image.png"],
            }
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            bundle = generate_materialized_bundle(
                output_dir=root / "out",
                metadata_file=metadata_file,
                diff_file=diff_file,
                patch_file=patch_file,
                risk_class="R2",
            )
            self.assertEqual(
                bundle.diff_sha256,
                __import__("hashlib").sha256(diff_file.read_bytes()).hexdigest(),
            )
            self.assertEqual(bundle.stats.opaque_files, ("image.png",))
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["source"], "github-pull-api")
            self.assertEqual(manifest["stats"]["opaque_files"], ["image.png"])

            metadata["changed_file_count"] = 1
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaises(GovernanceError):
                generate_materialized_bundle(
                    output_dir=root / "invalid",
                    metadata_file=metadata_file,
                    diff_file=diff_file,
                    patch_file=patch_file,
                    risk_class="R2",
                )

            metadata["changed_file_count"] = 2
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            diff_file.write_bytes(b"diff --git a/a.txt b/a.txt\n+new\n")
            with self.assertRaisesRegex(GovernanceError, "diff file count"):
                generate_materialized_bundle(
                    output_dir=root / "truncated",
                    metadata_file=metadata_file,
                    diff_file=diff_file,
                    patch_file=patch_file,
                    risk_class="R2",
                )

            metadata["changed_file_count"] = True
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(GovernanceError, "non-negative integer"):
                generate_materialized_bundle(
                    output_dir=root / "boolean-count",
                    metadata_file=metadata_file,
                    diff_file=diff_file,
                    patch_file=patch_file,
                    risk_class="R2",
                )

    def test_materialized_paths_reject_controls_and_opaque_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            diff_file = root / "pr.diff"
            patch_file = root / "pr.patch"
            metadata_file = root / "metadata.json"
            diff_file.write_bytes(b"diff --git a/a.txt b/a.txt\n+new\n")
            patch_file.write_bytes(b"From abc Mon Sep 17 00:00:00 2001\n+new\n")
            metadata = {
                "schema_version": 1,
                "pr_number": 17,
                "base_sha": "a" * 40,
                "head_sha": "b" * 40,
                "merge_base_sha": "c" * 40,
                "changed_file_count": 1,
                "changed_files": ["bad\nname.txt"],
                "additions": 1,
                "deletions": 0,
                "opaque_files": [],
            }
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(GovernanceError, "invalid path"):
                generate_materialized_bundle(
                    output_dir=root / "bad-path",
                    metadata_file=metadata_file,
                    diff_file=diff_file,
                    patch_file=patch_file,
                    risk_class="R2",
                )

            metadata["changed_files"] = ["a.txt"]
            metadata["opaque_files"] = ["a.txt", "a.txt"]
            metadata_file.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(GovernanceError, "opaque_files.*duplicates"):
                generate_materialized_bundle(
                    output_dir=root / "duplicate-opaque",
                    metadata_file=metadata_file,
                    diff_file=diff_file,
                    patch_file=patch_file,
                    risk_class="R2",
                )

    def test_materialized_bundle_enforces_artifact_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            diff_file = root / "pr.diff"
            patch_file = root / "pr.patch"
            metadata_file = root / "metadata.json"
            diff_file.write_bytes(b"diff --git a/a.txt b/a.txt\n" + b"x" * 80)
            patch_file.write_bytes(b"p" * 80)
            metadata_file.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "pr_number": 17,
                        "base_sha": "a" * 40,
                        "head_sha": "b" * 40,
                        "merge_base_sha": "c" * 40,
                        "changed_file_count": 1,
                        "changed_files": ["a.txt"],
                        "additions": 1,
                        "deletions": 0,
                        "opaque_files": [],
                    }
                ),
                encoding="utf-8",
            )
            original = review_governance.MAX_ARTIFACT_BYTES
            review_governance.MAX_ARTIFACT_BYTES = 64
            try:
                with self.assertRaisesRegex(GovernanceError, "safety limit"):
                    generate_materialized_bundle(
                        output_dir=root / "out",
                        metadata_file=metadata_file,
                        diff_file=diff_file,
                        patch_file=patch_file,
                        risk_class="R1",
                    )
            finally:
                review_governance.MAX_ARTIFACT_BYTES = original

    def test_local_patch_uses_merge_base_not_moving_base_tip(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "repo"
            repo.mkdir()
            _git(repo, "init", "-b", "main")
            _git(repo, "config", "user.name", "Test")
            _git(repo, "config", "user.email", "test@example.invalid")
            (repo / "common.txt").write_text("base\n", encoding="utf-8")
            _git(repo, "add", "common.txt")
            _git(repo, "commit", "-m", "common base")
            _git(repo, "branch", "feature")

            (repo / "main-only.txt").write_text("main side\n", encoding="utf-8")
            _git(repo, "add", "main-only.txt")
            _git(repo, "commit", "-m", "main side change")
            main_tip = _git(repo, "rev-parse", "HEAD")

            _git(repo, "checkout", "feature")
            (repo / "feature.txt").write_text("feature side\n", encoding="utf-8")
            _git(repo, "add", "feature.txt")
            _git(repo, "commit", "-m", "feature side change")
            feature_tip = _git(repo, "rev-parse", "HEAD")

            bundle = generate_bundle(
                repo=repo,
                output_dir=Path(temp_dir) / "out",
                base_revision=main_tip,
                head_revision=feature_tip,
                pr_number=8,
                risk_class="R2",
            )
            patch = bundle.patch_path.read_text(encoding="utf-8")
            self.assertIn("feature side change", patch)
            self.assertNotIn("main side change", patch)


class AuthorityTests(unittest.TestCase):
    def test_authority_file_is_strict_and_normalized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "authorities.json"
            path.write_text(
                json.dumps(
                    {"schema_version": 1, "allowed_attesters": ["Alex-DerMohr"]}
                ),
                encoding="utf-8",
            )
            self.assertEqual(load_allowed_attesters(path), frozenset({"alex-dermohr"}))
            path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "allowed_attesters": ["alex", "ALEX"],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(GovernanceError):
                load_allowed_attesters(path)


class EvidenceTests(unittest.TestCase):
    def test_r1_accepts_one_exact_authorized_review(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[
                _comment(
                    _record(
                        bundle, reviewer="Reviewer A", axis="correctness", risk="R1"
                    )
                )
            ],
        )
        self.assertTrue(result["pass"], result["reasons"])

    def test_stale_review_is_rejected(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        record = _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1")
        record["head_sha"] = "f" * 40
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[_comment(record)])
        self.assertFalse(result["pass"])
        self.assertEqual(result["stale_evidence_count"], 1)

    def test_r2_requires_distinct_reviewer_identities_and_axes(self) -> None:
        bundle = _bundle(paths=("apps/web/src/app.ts",))
        comments = [
            _comment(
                _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R2")
            ),
            _comment(_record(bundle, reviewer="Reviewer B", axis="testing", risk="R2")),
        ]
        result = _evaluate(bundle=bundle, risk_class="R2", comments=comments)
        self.assertTrue(result["pass"], result["reasons"])

        duplicate = [
            _comment(
                _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R2")
            ),
            _comment(_record(bundle, reviewer="Reviewer A", axis="testing", risk="R2")),
        ]
        result = _evaluate(bundle=bundle, risk_class="R2", comments=duplicate)
        self.assertFalse(result["pass"])
        self.assertIn("two distinct reviewer identities", " ".join(result["reasons"]))

    def test_r3_requires_high_risk_axis(self) -> None:
        bundle = _bundle(paths=(".github/workflows/ci.yml",))
        low_risk_comments = [
            _comment(
                _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R3")
            ),
            _comment(_record(bundle, reviewer="Reviewer B", axis="testing", risk="R3")),
        ]
        result = _evaluate(bundle=bundle, risk_class="R3", comments=low_risk_comments)
        self.assertFalse(result["pass"])
        self.assertIn("R3 requires", " ".join(result["reasons"]))

        high_risk_comments = low_risk_comments + [
            _comment(_record(bundle, reviewer="Reviewer C", axis="security", risk="R3"))
        ]
        result = _evaluate(bundle=bundle, risk_class="R3", comments=high_risk_comments)
        self.assertTrue(result["pass"], result["reasons"])

    def test_report_hash_must_match_substantive_comment_text(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        mismatched = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1"),
            report_sha256="0" * 64,
        )
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[mismatched])
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

        too_short = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1"),
            report_text="zu kurz",
        )
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[too_short])
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

    def test_r2_requires_distinct_review_report_hashes(self) -> None:
        bundle = _bundle(paths=("apps/web/src/app.ts",))
        shared_report = (
            "Derselbe ausführliche Bericht wird absichtlich zweimal verwendet. "
            "Er beschreibt Korrektheit, Tests, Regressionen und Fehlerszenarien, "
            "darf aber nicht als zwei unabhängige Prüfberichte gezählt werden."
        )
        comments = [
            _comment(
                _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R2"),
                report_text=shared_report,
            ),
            _comment(
                _record(bundle, reviewer="Reviewer B", axis="testing", risk="R2"),
                report_text=shared_report,
            ),
        ]
        result = _evaluate(bundle=bundle, risk_class="R2", comments=comments)
        self.assertFalse(result["pass"])
        self.assertIn("two distinct review reports", " ".join(result["reasons"]))

    def test_safe_raster_asset_is_reviewable_with_r1_approval(self) -> None:
        base = _bundle(paths=("docs/images/map.png",), changed_lines=0)
        bundle = Bundle(
            pr_number=base.pr_number,
            base_sha=base.base_sha,
            head_sha=base.head_sha,
            merge_base_sha=base.merge_base_sha,
            diff_sha256=base.diff_sha256,
            patch_sha256=base.patch_sha256,
            manifest_path=base.manifest_path,
            diff_path=base.diff_path,
            patch_path=base.patch_path,
            request_path=base.request_path,
            stats=DiffStats(
                ("docs/images/map.png",),
                0,
                0,
                (),
                ("docs/images/map.png",),
            ),
        )
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[],
            reviews=[_review(bundle)],
        )
        self.assertTrue(result["pass"], result["reasons"])
        self.assertEqual(result["reviewable_opaque_files"], ["docs/images/map.png"])
        self.assertEqual(result["blocking_opaque_files"], [])

    def test_unsafe_opaque_file_still_blocks(self) -> None:
        base = _bundle(paths=("docs/report.pdf",), changed_lines=0)
        bundle = Bundle(
            pr_number=base.pr_number,
            base_sha=base.base_sha,
            head_sha=base.head_sha,
            merge_base_sha=base.merge_base_sha,
            diff_sha256=base.diff_sha256,
            patch_sha256=base.patch_sha256,
            manifest_path=base.manifest_path,
            diff_path=base.diff_path,
            patch_path=base.patch_path,
            request_path=base.request_path,
            stats=DiffStats(("docs/report.pdf",), 0, 0, (), ("docs/report.pdf",)),
        )
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[],
            reviews=[_review(bundle)],
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["blocking_opaque_files"], ["docs/report.pdf"])
        self.assertIn("opaque files outside", " ".join(result["reasons"]))

    def test_r1_accepts_native_current_head_approval(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[],
            reviews=[_review(bundle)],
        )
        self.assertTrue(result["pass"], result["reasons"])
        self.assertEqual(result["accepted_reviews"][0]["kind"], "github-approval")

    def test_native_approval_must_match_current_head_and_does_not_replace_r2_reports(
        self,
    ) -> None:
        r1_bundle = _bundle(paths=("config/example.json",))
        stale = _evaluate(
            bundle=r1_bundle,
            risk_class="R1",
            comments=[],
            reviews=[_review(r1_bundle, commit_id="f" * 40)],
        )
        self.assertFalse(stale["pass"])
        self.assertEqual(stale["stale_native_review_count"], 1)

        r2_bundle = _bundle(paths=("apps/web/src/app.ts",))
        r2 = _evaluate(
            bundle=r2_bundle,
            risk_class="R2",
            comments=[],
            reviews=[_review(r2_bundle)],
        )
        self.assertFalse(r2["pass"])
        self.assertEqual(r2["accepted_review_count"], 0)

    def test_native_approval_requires_trusted_github_association(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[],
            reviews=[
                _review(
                    bundle,
                    author="outside-reviewer",
                    association="CONTRIBUTOR",
                )
            ],
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["unauthorized_native_review_count"], 1)

    def test_current_head_changes_requested_blocks_r1(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[],
            reviews=[_review(bundle, state="CHANGES_REQUESTED")],
        )
        self.assertFalse(result["pass"])
        self.assertIn("request changes", " ".join(result["reasons"]))

    def test_report_hash_normalizes_crlf_and_bare_cr(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        report = (
            "Ausführlicher Bericht zur Korrektheit.\r\n"
            "Geprüft wurden Regressionen, Fehlerszenarien und Invarianten.\r"
            "Es verbleiben keine Mergeblocker und alle Befunde sind aufgelöst."
        )
        result = _evaluate(
            bundle=bundle,
            risk_class="R1",
            comments=[
                _comment(
                    _record(
                        bundle, reviewer="Reviewer A", axis="correctness", risk="R1"
                    ),
                    report_text=report,
                )
            ],
        )
        self.assertTrue(result["pass"], result["reasons"])

    def test_malformed_and_multiple_evidence_blocks_are_diagnostic(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        malformed = {
            "id": 1,
            "body": "Bericht<!-- weltgewebe-review-evidence {kaputt} -->",
            "author_association": "OWNER",
            "user": {"login": "alex"},
        }
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[malformed])
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

        first = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1")
        )
        first["body"] += first["body"][
            first["body"].index("<!-- weltgewebe-review-evidence") :
        ]
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[first])
        self.assertFalse(result["pass"])
        self.assertGreaterEqual(result["malformed_evidence_count"], 2)

    def test_unicode_equivalent_reviewer_names_are_not_distinct(self) -> None:
        bundle = _bundle(paths=("apps/web/src/app.ts",))
        composed = "Revér A"
        decomposed = "Reve\u0301r A"
        comments = [
            _comment(
                _record(bundle, reviewer=composed, axis="correctness", risk="R2"),
                comment_id=1,
            ),
            _comment(
                _record(bundle, reviewer=decomposed, axis="testing", risk="R2"),
                comment_id=2,
            ),
        ]
        result = _evaluate(bundle=bundle, risk_class="R2", comments=comments)
        self.assertFalse(result["pass"])
        self.assertIn("two distinct reviewer identities", " ".join(result["reasons"]))

    def test_same_timestamp_uses_higher_comment_id_deterministically(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        passed = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1"),
            comment_id=10,
        )
        blocked = _comment(
            _record(
                bundle,
                reviewer="Reviewer A",
                axis="correctness",
                risk="R1",
                verdict="BLOCKED",
            ),
            comment_id=11,
        )
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[blocked, passed])
        self.assertFalse(result["pass"])
        self.assertIn("blocking verdicts", " ".join(result["reasons"]))

    def test_findings_resolved_must_be_true_for_pass(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        record = _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1")
        record["findings_resolved"] = False
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[_comment(record)])
        self.assertFalse(result["pass"])
        self.assertEqual(result["accepted_review_count"], 0)

    def test_evidence_schema_and_reviewer_are_strict(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        extra = _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1")
        extra["unexpected"] = "not allowed"
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[_comment(extra)])
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

        boolean_schema = _record(
            bundle, reviewer="Reviewer A", axis="correctness", risk="R1"
        )
        boolean_schema["schema_version"] = True
        result = _evaluate(
            bundle=bundle, risk_class="R1", comments=[_comment(boolean_schema)]
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

        control_name = _record(
            bundle, reviewer="Reviewer\nA", axis="correctness", risk="R1"
        )
        result = _evaluate(
            bundle=bundle, risk_class="R1", comments=[_comment(control_name)]
        )
        self.assertFalse(result["pass"])
        self.assertEqual(result["malformed_evidence_count"], 1)

    def test_latest_blocking_verdict_overrides_prior_pass(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        passed = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1")
        )
        blocked = _comment(
            _record(
                bundle,
                reviewer="Reviewer A",
                axis="correctness",
                risk="R1",
                verdict="BLOCKED",
            )
        )
        blocked["updated_at"] = "2026-07-14T13:00:00Z"
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[passed, blocked])
        self.assertFalse(result["pass"])
        self.assertIn("blocking verdicts", " ".join(result["reasons"]))

    def test_r0_fails_closed_for_non_markdown_or_large_change(self) -> None:
        code_bundle = _bundle(paths=("script.py",), changed_lines=2)
        result = _evaluate(bundle=code_bundle, risk_class="R0", comments=[])
        self.assertFalse(result["pass"])

        large_bundle = _bundle(paths=("docs/example.md",), changed_lines=51)
        result = _evaluate(bundle=large_bundle, risk_class="R0", comments=[])
        self.assertFalse(result["pass"])

    def test_unauthorized_comment_does_not_count(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        comment = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1"),
            association="NONE",
        )
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[comment])
        self.assertFalse(result["pass"])
        self.assertEqual(result["unauthorized_evidence_count"], 1)

    def test_unlisted_attester_does_not_count_even_with_owner_role(self) -> None:
        bundle = _bundle(paths=("config/example.json",))
        comment = _comment(
            _record(bundle, reviewer="Reviewer A", axis="correctness", risk="R1"),
            association="OWNER",
            author="mallory",
        )
        result = _evaluate(bundle=bundle, risk_class="R1", comments=[comment])
        self.assertFalse(result["pass"])
        self.assertEqual(result["unauthorized_evidence_count"], 1)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parents[3]
        self.workflow = (
            self.repo_root / ".github/workflows/review-evidence.yml"
        ).read_text(encoding="utf-8")

    def test_privileged_workflow_executes_only_literal_main_code(self) -> None:
        self.assertIn("pull_request_target:", self.workflow)
        self.assertIn("issue_comment:", self.workflow)
        self.assertIn("pull_request_review:", self.workflow)
        self.assertIn("ref: main", self.workflow)
        self.assertIn("fetch-depth: 1", self.workflow)
        self.assertIn("persist-credentials: false", self.workflow)
        self.assertNotIn("github.event.pull_request.head", self.workflow)
        self.assertNotIn("actions/checkout@v", self.workflow)
        self.assertNotIn("git fetch", self.workflow)
        self.assertNotIn("refs/pull/", self.workflow)
        self.assertNotIn("git checkout", self.workflow)
        self.assertIn("Accept: application/vnd.github.diff", self.workflow)
        self.assertIn("Accept: application/vnd.github.patch", self.workflow)
        self.assertIn("pr-before.json", self.workflow)
        self.assertIn("pr-after.json", self.workflow)
        self.assertIn("diff_file_count", self.workflow)
        self.assertIn("max_artifact_bytes", self.workflow)
        self.assertIn("/reviews?per_page=100", self.workflow)
        self.assertIn("--reviews-file", self.workflow)
        self.assertIn("Refresh current-head evidence before publication", self.workflow)
        self.assertNotIn("continue-on-error: true", self.workflow)
        self.assertIn(
            "scripts/quality/review_governance.py evaluate-materialized",
            self.workflow,
        )
        self.assertIn(
            "--authorities-file .github/review-evidence-authorities.json",
            self.workflow,
        )

    def test_all_actions_are_pinned_to_full_commit_sha(self) -> None:
        action_lines = [
            line.strip()
            for line in self.workflow.splitlines()
            if line.strip().startswith("uses:")
        ]
        self.assertGreaterEqual(len(action_lines), 2)
        for line in action_lines:
            match = re.fullmatch(r"uses: [^@\s]+@([0-9a-f]{40})(?:\s+#.*)?", line)
            self.assertIsNotNone(match, line)

    def test_status_context_matches_required_checks_contract(self) -> None:
        required = json.loads(
            (self.repo_root / ".github/grabowski-required-checks.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertIn("Review evidence gate", required["required_checks"])
        self.assertGreaterEqual(
            self.workflow.count("context='Review evidence gate'"), 2
        )

    def test_pr_template_contains_single_risk_marker(self) -> None:
        template = (self.repo_root / ".github/PULL_REQUEST_TEMPLATE.md").read_text(
            encoding="utf-8"
        )
        self.assertEqual(template.count("<!-- weltgewebe-risk: R? -->"), 1)
        self.assertIn("R3 = auth, privacy, security", template)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

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


def _comment(record: dict, *, association: str = "OWNER", author: str = "alex") -> dict:
    return {
        "body": "Review text\n<!-- weltgewebe-review-evidence\n"
        + json.dumps(record)
        + "\n-->",
        "author_association": association,
        "user": {"login": author},
        "html_url": "https://example.invalid/review",
        "created_at": "2026-07-14T12:00:00Z",
        "updated_at": "2026-07-14T12:00:00Z",
    }


ALLOWED_ATTESTERS = frozenset({"alex"})


def _evaluate(*, bundle: Bundle, risk_class: str, comments: list[dict]) -> dict:
    return evaluate_evidence(
        bundle=bundle,
        risk_class=risk_class,
        comments=comments,
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

    def test_sensitive_paths_raise_minimum_risk(self) -> None:
        self.assertEqual(minimum_risk_for_paths(["docs/example.md"]), "R0")
        self.assertEqual(minimum_risk_for_paths(["apps/web/src/app.ts"]), "R2")
        self.assertEqual(minimum_risk_for_paths([".github/workflows/ci.yml"]), "R3")
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

    def test_materialized_github_bundle_is_hash_bound_and_validated(self) -> None:
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

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.docmeta.attention_impact_guard import (
    canonical_product_docs,
    evaluate_attention_impact,
    product_logic_changes,
    pull_request_context_from_environment,
)


PRODUCT_DOCS = {
    "docs/specs/governance-antraege.md",
    "docs/specs/private-nachrichten.md",
}


class AttentionImpactGuardTests(unittest.TestCase):
    def test_non_product_changes_need_no_marker(self):
        self.assertEqual(
            evaluate_attention_impact(
                pr_body="",
                changed_files=["docs/README.md", "scripts/docmeta/foo.py"],
                product_docs=PRODUCT_DOCS,
            ),
            [],
        )

    def test_apps_and_domain_contracts_are_product_logic(self):
        self.assertEqual(
            product_logic_changes(
                [
                    "apps/web/src/routes/foo.ts",
                    "contracts/domain/message.schema.json",
                    "docs/specs/private-nachrichten.md",
                ]
            ),
            [
                "apps/web/src/routes/foo.ts",
                "contracts/domain/message.schema.json",
            ],
        )

    def test_product_change_without_marker_fails(self):
        errors = evaluate_attention_impact(
            pr_body="",
            changed_files=["apps/web/src/routes/foo.ts"],
            product_docs=PRODUCT_DOCS,
        )
        self.assertTrue(any("exactly one" in error for error in errors), errors)

    def test_contract_decision_requires_changed_canonical_product_doc(self):
        body = "<!-- weltgewebe-attention-impact: contract -->"
        errors = evaluate_attention_impact(
            pr_body=body,
            changed_files=["apps/api/src/routes/foo.rs"],
            product_docs=PRODUCT_DOCS,
        )
        self.assertTrue(any("canonical product contract" in error for error in errors), errors)

        self.assertEqual(
            evaluate_attention_impact(
                pr_body=body,
                changed_files=[
                    "apps/api/src/routes/foo.rs",
                    "docs/specs/governance-antraege.md",
                ],
                product_docs=PRODUCT_DOCS,
            ),
            [],
        )

    def test_none_decision_requires_concrete_rationale(self):
        body = "<!-- weltgewebe-attention-impact: none -->"
        errors = evaluate_attention_impact(
            pr_body=body,
            changed_files=["apps/web/src/lib/foo.ts"],
            product_docs=PRODUCT_DOCS,
        )
        self.assertTrue(any("rationale" in error for error in errors), errors)

        too_short = (
            "<!-- weltgewebe-attention-impact: none -->\n"
            "<!-- weltgewebe-attention-rationale: refactor -->"
        )
        errors = evaluate_attention_impact(
            pr_body=too_short,
            changed_files=["apps/web/src/lib/foo.ts"],
            product_docs=PRODUCT_DOCS,
        )
        self.assertTrue(any("between" in error for error in errors), errors)

        valid = (
            "<!-- weltgewebe-attention-impact: none -->\n"
            "<!-- weltgewebe-attention-rationale: Pure refactor; no user-visible or personal domain semantics change. -->"
        )
        self.assertEqual(
            evaluate_attention_impact(
                pr_body=valid,
                changed_files=["apps/web/src/lib/foo.ts"],
                product_docs=PRODUCT_DOCS,
            ),
            [],
        )

    def test_duplicate_impact_markers_fail(self):
        body = (
            "<!-- weltgewebe-attention-impact: none -->\n"
            "<!-- weltgewebe-attention-impact: contract -->\n"
            "<!-- weltgewebe-attention-rationale: This is intentionally long enough to pass the rationale length. -->"
        )
        errors = evaluate_attention_impact(
            pr_body=body,
            changed_files=["apps/web/src/lib/foo.ts"],
            product_docs=PRODUCT_DOCS,
        )
        self.assertTrue(any("exactly one" in error for error in errors), errors)

    def test_manifest_product_docs_are_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "manifest").mkdir()
            (root / "manifest" / "repo-index.yaml").write_text(
                "zones:\n"
                "  product:\n"
                "    path: docs/specs/\n"
                "    canonical_docs:\n"
                "      - alpha.md\n"
                "      - beta.md\n",
                encoding="utf-8",
            )
            self.assertEqual(
                canonical_product_docs(root),
                {"docs/specs/alpha.md", "docs/specs/beta.md"},
            )

    def test_pull_request_context_reads_exact_event_binding(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(
                {
                    "pull_request": {
                        "base": {"sha": "a" * 40},
                        "head": {"sha": "b" * 40},
                        "body": "body",
                    }
                },
                handle,
            )
            event_path = handle.name
        try:
            with patch.dict(
                os.environ,
                {
                    "GITHUB_EVENT_NAME": "pull_request",
                    "GITHUB_EVENT_PATH": event_path,
                },
                clear=False,
            ):
                self.assertEqual(
                    pull_request_context_from_environment(),
                    ("a" * 40, "b" * 40, "body"),
                )
        finally:
            os.unlink(event_path)

    def test_non_pull_request_context_skips(self):
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}, clear=False):
            self.assertIsNone(pull_request_context_from_environment())


if __name__ == "__main__":
    unittest.main()

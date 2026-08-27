from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "scripts" / "guard" / "commonthing_naming_guard.py"
SPEC = importlib.util.spec_from_file_location("commonthing_naming_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


def diff(path: str, line: str, *, line_number: int = 1) -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +{line_number},1 @@\n"
        f"+{line}\n"
    )


class CommonThingNamingGuardTests(unittest.TestCase):
    def test_rejects_new_product_name(self) -> None:
        text = diff("apps/web/src/routes/example/+page.svelte", "<h1>Weltgewebe</h1>")
        violations = GUARD.find_violations(text, lambda _: "<h1>Weltgewebe</h1>\n")
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reason, "retired product name")

    def test_rejects_new_legacy_web_origin(self) -> None:
        text = diff("docs/deploy/example.md", "curl https://weltgewebe.net/health")
        violations = GUARD.find_violations(
            text,
            lambda _: "curl https://weltgewebe.net/health\n",
        )
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reason, "legacy public web origin")

    def test_accepts_commonthing_current_name(self) -> None:
        text = diff("apps/web/src/routes/example/+page.svelte", "<h1>commonThing</h1>")
        self.assertEqual(
            GUARD.find_violations(text, lambda _: "<h1>commonThing</h1>\n"),
            [],
        )

    def test_accepts_explicit_legacy_marker_on_previous_line(self) -> None:
        text = (
            "diff --git a/infra/example.conf b/infra/example.conf\n"
            "--- a/infra/example.conf\n"
            "+++ b/infra/example.conf\n"
            "@@ -0,0 +1,2 @@\n"
            "+# commonthing-naming: legacy\n"
            "+legacy=https://weltgewebe.net/path\n"
        )
        current = "# commonthing-naming: legacy\nlegacy=https://weltgewebe.net/path\n"
        self.assertEqual(GUARD.find_violations(text, lambda _: current), [])

    def test_policy_documents_can_explain_legacy_names(self) -> None:
        for path in GUARD.POLICY_EXEMPT_PATHS:
            with self.subTest(path=path):
                text = diff(path, "Weltgewebe -> https://weltgewebe.net")
                self.assertEqual(
                    GUARD.find_violations(text, lambda _: "Weltgewebe -> https://weltgewebe.net\n"),
                    [],
                )

    def test_api_legacy_host_is_not_mistaken_for_legacy_web_origin(self) -> None:
        text = diff("docs/deploy/example.md", "https://api.weltgewebe.net/health/ready")
        self.assertEqual(
            GUARD.find_violations(
                text,
                lambda _: "https://api.weltgewebe.net/health/ready\n",
            ),
            [],
        )


if __name__ == "__main__":
    unittest.main()

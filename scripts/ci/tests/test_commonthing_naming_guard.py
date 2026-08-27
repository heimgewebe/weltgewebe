from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO / "scripts" / "guard" / "commonthing_naming_guard.py"
SPEC = importlib.util.spec_from_file_location("commonthing_naming_guard", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
GUARD = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = GUARD
SPEC.loader.exec_module(GUARD)

RETIRED_PRODUCT = "Welt" + "gewebe"
LEGACY_WEB_HOST = "welt" + "gewebe.net"
LEGACY_WEB_ORIGIN = f"https://{LEGACY_WEB_HOST}"
LEGACY_API_ORIGIN = "https://api.welt" + "gewebe.net"
LEGACY_CONTACT = "kontakt@welt" + "gewebe.net"


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
        current = f"<h1>{RETIRED_PRODUCT}</h1>\n"
        text = diff("apps/web/src/routes/example/+page.svelte", current.rstrip())
        violations = GUARD.find_violations(text, lambda _: current)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reason, "retired product name")

    def test_rejects_new_legacy_web_origin(self) -> None:
        current = f"curl {LEGACY_WEB_ORIGIN}/health\n"
        text = diff("docs/deploy/example.md", current.rstrip())
        violations = GUARD.find_violations(text, lambda _: current)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reason, "legacy public web host")

    def test_rejects_new_bare_legacy_web_host(self) -> None:
        current = f"public host: {LEGACY_WEB_HOST}\n"
        text = diff("docs/deploy/example.md", current.rstrip())
        violations = GUARD.find_violations(text, lambda _: current)
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].reason, "legacy public web host")

    def test_accepts_commonthing_current_name(self) -> None:
        text = diff("apps/web/src/routes/example/+page.svelte", "<h1>commonThing</h1>")
        self.assertEqual(
            GUARD.find_violations(text, lambda _: "<h1>commonThing</h1>\n"),
            [],
        )

    def test_accepts_explicit_legacy_marker_on_previous_line(self) -> None:
        current = (
            "# commonthing-naming: legacy\n"
            f"legacy={LEGACY_WEB_ORIGIN}/path\n"
        )
        text = (
            "diff --git a/infra/example.conf b/infra/example.conf\n"
            "--- a/infra/example.conf\n"
            "+++ b/infra/example.conf\n"
            "@@ -0,0 +1,2 @@\n"
            "+# commonthing-naming: legacy\n"
            f"+legacy={LEGACY_WEB_ORIGIN}/path\n"
        )
        self.assertEqual(GUARD.find_violations(text, lambda _: current), [])

    def test_policy_documents_can_explain_legacy_names(self) -> None:
        current = f"{RETIRED_PRODUCT} -> {LEGACY_WEB_ORIGIN}\n"
        for path in GUARD.POLICY_EXEMPT_PATHS:
            with self.subTest(path=path):
                text = diff(path, current.rstrip())
                self.assertEqual(
                    GUARD.find_violations(text, lambda _: current),
                    [],
                )

    def test_api_legacy_host_is_not_mistaken_for_public_web_host(self) -> None:
        current = f"{LEGACY_API_ORIGIN}/health/ready\n"
        text = diff("docs/deploy/example.md", current.rstrip())
        self.assertEqual(
            GUARD.find_violations(text, lambda _: current),
            [],
        )

    def test_legacy_mail_address_is_not_mistaken_for_public_web_host(self) -> None:
        current = f"mail alias: {LEGACY_CONTACT}\n"
        text = diff("docs/deploy/example.md", current.rstrip())
        self.assertEqual(
            GUARD.find_violations(text, lambda _: current),
            [],
        )


if __name__ == "__main__":
    unittest.main()

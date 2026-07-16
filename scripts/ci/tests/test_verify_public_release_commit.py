from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[2] / "ops" / "verify_public_release_commit.py"
SPEC = importlib.util.spec_from_file_location("verify_public_release_commit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

EndpointResult = MODULE.EndpointResult
evaluate = MODULE.evaluate
validate_commit = MODULE.validate_commit


class VerifyPublicReleaseCommitTests(unittest.TestCase):
    commit = "7b65127e852561997fa6a45b8cb3bfcef38e1eb8"

    def endpoint(self, *, api: bool = False, commit: str | None = None) -> EndpointResult:
        resolved = self.commit if commit is None else commit
        headers = (
            {
                "x-weltgewebe-api-build": resolved,
                "x-weltgewebe-build": resolved[:8],
            }
            if api
            else {"cache-control": "public, no-store"}
        )
        return EndpointResult(
            url="https://example.invalid/version",
            status=200,
            commit=resolved,
            version="0.1.0" if api else resolved[:8],
            headers=headers,
        )

    def test_accepts_exact_frontend_and_api_identity(self) -> None:
        result = evaluate(self.commit, self.endpoint(), self.endpoint(api=True))
        self.assertTrue(result.pass_)
        self.assertEqual(result.reasons, [])

    def test_rejects_stale_frontend_commit(self) -> None:
        stale = "1" * 40
        result = evaluate(
            self.commit,
            self.endpoint(commit=stale),
            self.endpoint(api=True),
        )
        self.assertFalse(result.pass_)
        self.assertTrue(any("frontend commit mismatch" in reason for reason in result.reasons))

    def test_rejects_missing_api_build_header(self) -> None:
        api = self.endpoint(api=True)
        api = EndpointResult(api.url, api.status, api.commit, api.version, {})
        result = evaluate(self.commit, self.endpoint(), api)
        self.assertFalse(result.pass_)
        self.assertTrue(any("API build header mismatch" in reason for reason in result.reasons))

    def test_requires_full_lowercase_sha(self) -> None:
        self.assertEqual(validate_commit(self.commit), self.commit)
        for invalid in ("7b65127e", "G" * 40, "", "a" * 41):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    validate_commit(invalid)


if __name__ == "__main__":
    unittest.main()

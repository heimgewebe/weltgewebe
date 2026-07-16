from __future__ import annotations

import importlib.util
import sys
import unittest
from email.message import Message
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[2] / "ops" / "verify_public_release_commit.py"
SPEC = importlib.util.spec_from_file_location("verify_public_release_commit", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

EndpointResult = MODULE.EndpointResult
evaluate = MODULE.evaluate
fetch_endpoint = MODULE.fetch_endpoint
validate_commit = MODULE.validate_commit


class FakeResponse:
    status = 200

    def __init__(self, body: bytes, url: str = "https://example.invalid/version") -> None:
        self.body = body
        self.url = url
        self.headers = Message()
        self.headers["Content-Length"] = str(len(body))

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.body if limit < 0 else self.body[:limit]

    def geturl(self) -> str:
        return self.url


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
        result = evaluate(
            self.commit,
            self.endpoint(commit="1" * 40),
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
        for invalid in ("7b65127e", "A" * 40, "G" * 40, "", "a" * 41):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_commit(invalid)

    def test_rejects_oversized_response(self) -> None:
        response = FakeResponse(b"x" * 12)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1, max_response_bytes=8)
        self.assertIn("response exceeds byte limit", result.error or "")

    def test_rejects_redirected_response(self) -> None:
        response = FakeResponse(b"{}", url="https://other.invalid/version")
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint("https://example.invalid/version", timeout=1)
        self.assertIn("unexpected redirect target", result.error or "")


if __name__ == "__main__":
    unittest.main()

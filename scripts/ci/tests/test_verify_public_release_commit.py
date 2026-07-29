from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from email.message import Message
from io import StringIO
from pathlib import Path
from unittest.mock import patch

MODULE_PATH = Path(__file__).parents[2] / "ops" / "verify_public_release_commit.py"
OPS_PATH = MODULE_PATH.parent
sys.path.insert(0, str(OPS_PATH))
SPEC = importlib.util.spec_from_file_location(
    "verify_public_release_commit", MODULE_PATH
)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

SECURE_IO = sys.modules["weltgewebe_secure_receipt_io"]

ArtifactTreeResult = MODULE.ArtifactTreeResult
EndpointResult = MODULE.EndpointResult
_normalize_headers = MODULE._normalize_headers
evaluate = MODULE.evaluate
fetch_endpoint = MODULE.fetch_endpoint
main = MODULE.main
validate_commit = MODULE.validate_commit
write_receipt = MODULE.write_receipt


class FakeResponse:
    status = 200

    def __init__(
        self, body: bytes, url: str = "https://example.invalid/version"
    ) -> None:
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
    tree_sha256 = "a" * 64

    def artifact_tree(
        self,
        *,
        commit: str | None = None,
        provenance: str = "unattested",
        error: str | None = None,
    ) -> ArtifactTreeResult:
        resolved = self.commit if commit is None else commit
        return ArtifactTreeResult(
            schema_version=1,
            sha256=self.tree_sha256,
            file_count=103,
            compile_revision=resolved,
            provenance=provenance,
            error=error,
        )

    def endpoint(
        self,
        *,
        api: bool = False,
        commit: str | None = None,
        include_artifact_tree: bool | None = None,
        artifact_compile_revision: str | None = None,
        provenance: str = "unattested",
    ) -> EndpointResult:
        resolved = self.commit if commit is None else commit
        headers = (
            {
                "x-weltgewebe-api-build": resolved,
                "x-weltgewebe-build": resolved[:8],
            }
            if api
            else {"cache-control": "public, no-store"}
        )
        include_tree = (
            not api if include_artifact_tree is None else include_artifact_tree
        )
        tree = (
            self.artifact_tree(
                commit=artifact_compile_revision or resolved,
                provenance=provenance,
            )
            if include_tree
            else None
        )
        return EndpointResult(
            url="https://example.invalid/version",
            status=200,
            commit=resolved,
            version="0.1.0" if api else resolved[:8],
            headers=headers,
            artifact_tree=tree,
        )

    def test_accepts_exact_identity_as_limited_unattested_pass(self) -> None:
        result = evaluate(self.commit, self.endpoint(), self.endpoint(api=True))
        self.assertTrue(result.pass_)
        self.assertEqual(result.status, "consistency_pass_unattested")
        self.assertEqual(
            result.pass_scope, "identity_and_declared_artifact_consistency"
        )
        self.assertTrue(result.identity_verified)
        self.assertTrue(result.artifact_tree_declaration_verified)
        self.assertFalse(result.attestation_verified)
        self.assertEqual(result.provenance_status, "unattested")
        self.assertEqual(result.reasons, [])
        self.assertIn("explicitly unattested", " ".join(result.limitations))

    def test_rejects_stale_frontend_commit(self) -> None:
        result = evaluate(
            self.commit,
            self.endpoint(commit="1" * 40),
            self.endpoint(api=True),
        )
        self.assertFalse(result.pass_)
        self.assertEqual(result.status, "failed")
        self.assertTrue(
            any("frontend commit mismatch" in reason for reason in result.reasons)
        )

    def test_rejects_missing_api_build_header(self) -> None:
        api = self.endpoint(api=True)
        api = EndpointResult(api.url, api.status, api.commit, api.version, {})
        result = evaluate(self.commit, self.endpoint(), api)
        self.assertFalse(result.pass_)
        self.assertTrue(
            any("API build header mismatch" in reason for reason in result.reasons)
        )

    def test_rejects_missing_frontend_artifact_tree(self) -> None:
        result = evaluate(
            self.commit,
            self.endpoint(include_artifact_tree=False),
            self.endpoint(api=True),
        )
        self.assertFalse(result.pass_)
        self.assertTrue(result.identity_verified)
        self.assertFalse(result.artifact_tree_declaration_verified)
        self.assertEqual(result.provenance_status, "missing")
        self.assertIn("artifact_tree declaration is missing", " ".join(result.reasons))

    def test_rejects_artifact_compile_revision_mismatch(self) -> None:
        result = evaluate(
            self.commit,
            self.endpoint(artifact_compile_revision="1" * 40),
            self.endpoint(api=True),
        )
        self.assertFalse(result.pass_)
        self.assertIn("compile_revision mismatch", " ".join(result.reasons))

    def test_rejects_unimplemented_attestation_claim(self) -> None:
        result = evaluate(
            self.commit,
            self.endpoint(provenance="slsa-v1"),
            self.endpoint(api=True),
        )
        self.assertFalse(result.pass_)
        self.assertFalse(result.attestation_verified)
        self.assertIn("provenance is unsupported", " ".join(result.reasons))

    def test_fetches_structured_artifact_tree_evidence(self) -> None:
        body = json.dumps(
            {
                "commit": self.commit,
                "version": self.commit[:8],
                "artifact_tree": {
                    "schema_version": 1,
                    "sha256": self.tree_sha256,
                    "file_count": 103,
                    "compile_revision": self.commit,
                    "provenance": "unattested",
                },
            }
        ).encode()
        response = FakeResponse(body)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1)
        self.assertIsNotNone(result.artifact_tree)
        assert result.artifact_tree is not None
        self.assertIsNone(result.artifact_tree.error)
        self.assertEqual(result.artifact_tree.sha256, self.tree_sha256)
        self.assertEqual(result.artifact_tree.file_count, 103)
        self.assertEqual(result.artifact_tree.compile_revision, self.commit)
        self.assertEqual(result.artifact_tree.provenance, "unattested")

    def test_marks_malformed_artifact_tree_invalid(self) -> None:
        body = json.dumps(
            {
                "commit": self.commit,
                "version": self.commit[:8],
                "artifact_tree": {
                    "schema_version": 2,
                    "sha256": "not-a-digest",
                    "file_count": True,
                    "compile_revision": "short",
                    "provenance": "",
                },
            }
        ).encode()
        response = FakeResponse(body)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1)
        self.assertIsNotNone(result.artifact_tree)
        assert result.artifact_tree is not None
        self.assertIn("schema_version", result.artifact_tree.error or "")
        self.assertIn("file_count", result.artifact_tree.error or "")
        self.assertIn("compile_revision", result.artifact_tree.error or "")

    def test_rejects_duplicate_json_keys_at_every_depth(self) -> None:
        body = (
            '{"commit":"%s","version":"%s","artifact_tree":'
            '{"schema_version":1,"sha256":"%s","file_count":103,'
            '"compile_revision":"%s","provenance":"unattested",'
            '"provenance":"unattested"}}'
            % (self.commit, self.commit[:8], self.tree_sha256, self.commit)
        ).encode()
        response = FakeResponse(body)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1)
        self.assertIn("duplicate JSON key: provenance", result.error or "")

    def test_rejects_nonfinite_json_numbers(self) -> None:
        body = (
            '{"commit":"%s","version":NaN,"artifact_tree":'
            '{"schema_version":1,"sha256":"%s","file_count":103,'
            '"compile_revision":"%s","provenance":"unattested"}}'
            % (self.commit, self.tree_sha256, self.commit)
        ).encode()
        response = FakeResponse(body)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1)
        self.assertIn("non-finite JSON number", result.error or "")

    def test_rejects_unknown_artifact_tree_fields(self) -> None:
        body = json.dumps(
            {
                "commit": self.commit,
                "version": self.commit[:8],
                "artifact_tree": {
                    "schema_version": 1,
                    "sha256": self.tree_sha256,
                    "file_count": 103,
                    "compile_revision": self.commit,
                    "provenance": "unattested",
                    "attestation_verified": True,
                },
            }
        ).encode()
        response = FakeResponse(body)
        with patch.object(MODULE.urllib.request, "urlopen", return_value=response):
            result = fetch_endpoint(response.url, timeout=1)
        self.assertIsNotNone(result.artifact_tree)
        assert result.artifact_tree is not None
        self.assertIn(
            "unknown fields: attestation_verified", result.artifact_tree.error or ""
        )

    def test_main_preserves_identity_marker_and_labels_limited_consistency(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            output = Path(raw_root) / "receipt.json"
            stdout = StringIO()
            with (
                patch.object(
                    MODULE,
                    "fetch_endpoint",
                    side_effect=[self.endpoint(), self.endpoint(api=True)],
                ),
                redirect_stdout(stdout),
            ):
                returncode = main(
                    [
                        "--expected-commit",
                        self.commit,
                        "--output",
                        str(output),
                    ]
                )
        self.assertEqual(returncode, 0)
        rendered = stdout.getvalue()
        self.assertIn("production_release_identity=ok", rendered)
        self.assertIn("production_release_consistency=limited", rendered)
        self.assertIn("status=consistency_pass_unattested", rendered)
        self.assertIn("attestation_verified=false", rendered)

    def test_requires_full_lowercase_sha(self) -> None:
        self.assertEqual(validate_commit(self.commit), self.commit)
        for invalid in ("7b65127e", "A" * 40, "G" * 40, "", "a" * 41):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validate_commit(invalid)

    def test_aggregates_duplicate_headers(self) -> None:
        headers = Message()
        headers["Cache-Control"] = "public"
        headers["Cache-Control"] = "no-store"
        normalized = _normalize_headers(headers)
        self.assertEqual(normalized["cache-control"], "public, no-store")

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

    def verification_result(self):
        return evaluate(self.commit, self.endpoint(), self.endpoint(api=True))

    def test_receipt_writer_forces_mode_0600_under_permissive_umask(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            receipt = Path(raw_root) / "receipt.json"
            previous_umask = os.umask(0)
            try:
                write_receipt(receipt, self.verification_result())
            finally:
                os.umask(previous_umask)
            self.assertEqual(receipt.stat().st_mode & 0o777, 0o600)
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertTrue(payload["pass"])
            self.assertEqual(payload["status"], "consistency_pass_unattested")
            self.assertFalse(payload["attestation_verified"])
            self.assertEqual(
                payload["frontend"]["artifact_tree"]["sha256"], self.tree_sha256
            )

    def test_receipt_writer_rejects_precreated_temporary_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            receipt = root / "receipt.json"
            target = root / "target.txt"
            target.write_text("unchanged\n", encoding="utf-8")
            token = "a" * 16
            temporary = root / f".{receipt.name}.{os.getpid()}.{token}.tmp"
            temporary.symlink_to(target)
            with (
                patch.object(SECURE_IO.secrets, "token_hex", return_value=token),
                self.assertRaises(FileExistsError),
            ):
                write_receipt(receipt, self.verification_result())
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged\n")
            self.assertTrue(temporary.is_symlink())
            self.assertFalse(receipt.exists())

    def test_receipt_writer_replaces_output_symlink_without_following_it(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            receipt = root / "receipt.json"
            target = root / "target.txt"
            target.write_text("unchanged\n", encoding="utf-8")
            receipt.symlink_to(target)
            write_receipt(receipt, self.verification_result())
            self.assertFalse(receipt.is_symlink())
            self.assertEqual(target.read_text(encoding="utf-8"), "unchanged\n")
            self.assertTrue(json.loads(receipt.read_text(encoding="utf-8"))["pass"])

    def test_receipt_writer_rejects_writable_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            receipt = root / "receipt.json"
            root.chmod(0o777)
            try:
                with self.assertRaisesRegex(
                    SECURE_IO.SecureMetadataError, "unsafe mode"
                ):
                    write_receipt(receipt, self.verification_result())
            finally:
                root.chmod(0o700)
            self.assertFalse(receipt.exists())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "basemap" / "prove-germany-staging-caddy.py"
SPEC = importlib.util.spec_from_file_location("germany_caddy_proof", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
NOW = dt.datetime(2026, 8, 4, 6, 0, tzinfo=dt.timezone.utc)


class ArtifactHandler(BaseHTTPRequestHandler):
    artifact = b"PMTiles" + bytes(range(256)) * 4
    content_type = "application/octet-stream"
    redirect_location: str | None = None

    def do_GET(self) -> None:
        if self.redirect_location is not None:
            self.send_response(302)
            self.send_header("Location", self.redirect_location)
            self.end_headers()
            return
        if self.path != "/local-basemap/basemap-germany.pmtiles":
            self.send_error(404)
            return
        range_header = self.headers.get("Range")
        if range_header == "bytes=0-126":
            payload = self.artifact[:127]
            self.send_response(206)
            self.send_header("Content-Type", self.content_type)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header(
                "Content-Range", f"bytes 0-126/{len(self.artifact)}"
            )
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(200)
        self.send_header("Content-Type", self.content_type)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(self.artifact)))
        self.end_headers()
        self.wfile.write(self.artifact)

    def log_message(self, _format: str, *_args: object) -> None:
        return


class GermanyStagingCaddyProofTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.artifact = self.root / "basemap-germany-v1.0.0.pmtiles"
        self.artifact.write_bytes(ArtifactHandler.artifact)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), ArtifactHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.origin = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        ArtifactHandler.content_type = "application/octet-stream"
        ArtifactHandler.redirect_location = None
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            origin=self.origin,
            artifact=str(self.artifact),
            output=str(self.root / "proof.json"),
            timeout_seconds=5,
        )

    def test_proves_full_and_range_delivery(self) -> None:
        payload = MODULE.prove(self.args(), now=NOW)
        expected_sha256 = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.assertEqual(payload["verdict"], "PROVEN")
        self.assertEqual(payload["artifact"]["sha256"], expected_sha256)
        self.assertEqual(payload["full_get"]["status"], 200)
        self.assertEqual(payload["full_get"]["sha256"], expected_sha256)
        self.assertEqual(payload["range_get"]["status"], 206)
        self.assertEqual(payload["range_get"]["signature"], "PMTiles")
        self.assertEqual(payload["scope"], "private-staging")

    def test_rejects_public_origin(self) -> None:
        with self.assertRaisesRegex(MODULE.ProofError, "public address"):
            MODULE.validate_staging_origin("https://8.8.8.8")

    def test_rejects_hostname_origin(self) -> None:
        with self.assertRaisesRegex(MODULE.ProofError, "literal private IP address"):
            MODULE.validate_staging_origin("http://staging.example.invalid")

    def test_rejects_redirect_without_following_it(self) -> None:
        ArtifactHandler.redirect_location = "https://example.com/public.pmtiles"
        with self.assertRaisesRegex(MODULE.ProofError, "must not follow redirects"):
            MODULE.prove(self.args(), now=NOW)

    def test_rejects_wrong_content_type(self) -> None:
        original = ArtifactHandler.content_type
        ArtifactHandler.content_type = "text/plain"
        try:
            with self.assertRaisesRegex(MODULE.ProofError, "Content-Type mismatch"):
                MODULE.prove(self.args(), now=NOW)
        finally:
            ArtifactHandler.content_type = original

    def test_rejects_symlinked_artifact(self) -> None:
        link = self.root / "artifact-link.pmtiles"
        link.symlink_to(self.artifact)
        args = self.args()
        args.artifact = str(link)
        with self.assertRaisesRegex(MODULE.ProofError, "must not traverse a symlink"):
            MODULE.prove(args, now=NOW)


if __name__ == "__main__":
    unittest.main()

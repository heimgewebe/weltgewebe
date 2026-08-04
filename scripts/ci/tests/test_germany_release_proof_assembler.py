from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "basemap" / "assemble-germany-release-proof.py"
SPEC = importlib.util.spec_from_file_location("germany_release_proof", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

NOW = dt.datetime(2026, 8, 2, 4, 30, tzinfo=dt.timezone.utc)
COMMIT = "e7d2afe4172562098713a53e694947bc091e9751"
VERSION = "1.0.0"
REGIONS = ("hamburg", "berlin", "cologne", "dresden", "munich")


def region_rows(root: Path, prefix: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for index, region in enumerate(REGIONS):
        screenshot = root / f"{prefix}-{region}.png"
        screenshot.write_bytes(b"\x89PNG\r\n\x1a\n" + bytes([index + 1]) * 64)
        rows.append(
            {
                "id": region,
                "source_loaded": True,
                "rendered_from_expected_source": 3,
                "decoded_source_feature_count": 7,
                "screenshot": str(screenshot),
                "screenshot_sha256": hashlib.sha256(
                    screenshot.read_bytes()
                ).hexdigest(),
                "screenshot_size_bytes": screenshot.stat().st_size,
            }
        )
    return rows



class GermanyReleaseProofAssemblerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.artifact = self.root / "basemap-germany-v1.0.0.pmtiles"
        self.style = self.root / "style-germany.json"
        self.desktop_path = self.root / "desktop.json"
        self.ipad_path = self.root / "ipad.json"
        self.caddy_path = self.root / "caddy.json"
        self.output = self.root / "release.json"
        self.artifact.write_bytes(b"PMTiles" + bytes(range(64)))
        self.style.write_text('{"version":8,"name":"Germany"}\n', encoding="utf-8")
        self.artifact_sha256 = hashlib.sha256(self.artifact.read_bytes()).hexdigest()
        self.style_sha256 = hashlib.sha256(self.style.read_bytes()).hexdigest()
        self.desktop = {
            "verdict": "PROVEN",
            "region": "germany",
            "timestamp": "2026-08-02T04:20:00Z",
            "basemap_version": VERSION,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size_bytes": self.artifact.stat().st_size,
            "frontend_commit": COMMIT,
            "style_sha256": self.style_sha256,
            "style_loaded": True,
            "source_loaded": True,
            "rendered_from_expected_source": 3,
            "decoded_source_feature_count": 7,
            "pmtiles_requests_total": 4,
            "pmtiles_range_requests_observed": 4,
            "pmtiles_206_responses_observed": 4,
            "canvas_dimensions": {"width": 1024, "height": 768},
            "direct_range_status": 206,
            "direct_range_accept_ranges": "bytes",
            "direct_range_content_range": "bytes 0-126/4096",
            "direct_range_content_type": "application/octet-stream",
            "remote_violations": [],
            "unexpected_api_requests": [],
            "failed_responses": [],
            "console_errors": [],
            "five_region_evidence": region_rows(self.root, "desktop"),
        }
        self.caddy = {
            "schema_version": 1,
            "verdict": "PROVEN",
            "contract": "germany-basemap-staging-caddy-v1",
            "proofed_at": "2026-08-02T04:23:00Z",
            "scope": "private-staging",
            "staging_origin": "http://127.0.0.1:8765",
            "artifact": {
                "name": self.artifact.name,
                "sha256": self.artifact_sha256,
                "size_bytes": self.artifact.stat().st_size,
            },
            "full_get": {
                "status": 200,
                "content_type": "application/octet-stream",
                "content_length": self.artifact.stat().st_size,
                "accept_ranges": "bytes",
                "bytes_received": self.artifact.stat().st_size,
                "sha256": self.artifact_sha256,
            },
            "range_get": {
                "status": 206,
                "content_type": "application/octet-stream",
                "content_range": f"bytes 0-126/{self.artifact.stat().st_size}",
                "content_length": 127,
                "accept_ranges": "bytes",
                "payload_size_bytes": 127,
                "signature": "PMTiles",
            },
        }
        self.ipad = {
            "schema_version": 1,
            "verdict": "PROVEN",
            "proofed_at": "2026-08-02T04:25:00+00:00",
            "device_class": "physical-ipad",
            "native_webview": "WKWebView",
            "basemap_version": VERSION,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size_bytes": self.artifact.stat().st_size,
            "frontend_commit": COMMIT,
            "style_sha256": self.style_sha256,
            "staging_range_status": 206,
            "remote_violations": [],
            "regions": region_rows(self.root, "ipad"),
        }
        self.write_inputs()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write_inputs(self) -> None:
        self.desktop_path.write_text(
            json.dumps(self.desktop), encoding="utf-8"
        )
        self.ipad_path.write_text(json.dumps(self.ipad), encoding="utf-8")
        self.caddy_path.write_text(json.dumps(self.caddy), encoding="utf-8")

    def args(self) -> argparse.Namespace:
        return argparse.Namespace(
            artifact=str(self.artifact),
            style=str(self.style),
            desktop_proof=str(self.desktop_path),
            ipad_proof=str(self.ipad_path),
            caddy_proof=str(self.caddy_path),
            version=VERSION,
            frontend_commit=COMMIT,
            output=str(self.output),
        )

    def test_assembles_activation_compatible_proof(self) -> None:
        payload = MODULE.assemble(self.args(), now=NOW)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["verdict"], "PROVEN")
        self.assertEqual(payload["artifact_sha256"], self.artifact_sha256)
        self.assertEqual(payload["artifact_size_bytes"], self.artifact.stat().st_size)
        self.assertEqual(payload["frontend_commit"], COMMIT)
        self.assertEqual(payload["style_sha256"], self.style_sha256)
        self.assertEqual(payload["proofed_at"], "2026-08-02T04:25:00Z")
        self.assertEqual(
            set(payload["proofs"]),
            {
                "desktop-maplibre",
                "ipad-maplibre",
                "five-region-visual",
                "no-external-map-requests",
                "staging-caddy-range",
            },
        )

    def test_rejects_missing_region(self) -> None:
        self.desktop["five_region_evidence"] = region_rows(
            self.root, "desktop-missing"
        )[:-1]
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "must prove exactly"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_external_provider_request(self) -> None:
        self.desktop["remote_violations"] = ["https://tiles.example.invalid"]
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "must be an empty list"):
            MODULE.assemble(self.args(), now=NOW)


    def test_rejects_desktop_artifact_binding_mismatch(self) -> None:
        self.desktop["artifact_sha256"] = "1" * 64
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "desktop proof artifact_sha256 mismatch"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_tampered_region_screenshot(self) -> None:
        region = self.desktop["five_region_evidence"][0]
        screenshot = Path(region["screenshot"])
        screenshot.write_bytes(screenshot.read_bytes() + b"tampered")
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "screenshot size mismatch"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_caddy_artifact_binding_mismatch(self) -> None:
        self.caddy["artifact"]["sha256"] = "2" * 64
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "Caddy proof artifact binding mismatch"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_public_caddy_origin(self) -> None:
        self.caddy["staging_origin"] = "https://example.com"
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "literal private IP address"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_caddy_range_contract_mismatch(self) -> None:
        self.caddy["range_get"]["content_range"] = "bytes 0-126/999"
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "content_range mismatch"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_ipad_artifact_binding_mismatch(self) -> None:
        self.ipad["artifact_sha256"] = "0" * 64
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "artifact_sha256 mismatch"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_non_physical_ipad(self) -> None:
        self.ipad["device_class"] = "emulated-tablet"
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "physical iPad"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_stale_proof(self) -> None:
        self.ipad["proofed_at"] = "2026-07-31T04:25:00Z"
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "older than 24 hours"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_future_proof(self) -> None:
        self.desktop["timestamp"] = "2026-08-02T05:00:01Z"
        self.write_inputs()
        with self.assertRaisesRegex(MODULE.ProofError, "lies in the future"):
            MODULE.assemble(self.args(), now=NOW)

    def test_rejects_symlinked_artifact(self) -> None:
        real = self.artifact
        link = self.root / "artifact-link.pmtiles"
        link.symlink_to(real)
        args = self.args()
        args.artifact = str(link)
        with self.assertRaisesRegex(MODULE.ProofError, "must not traverse a symlink"):
            MODULE.assemble(args, now=NOW)


if __name__ == "__main__":
    unittest.main()

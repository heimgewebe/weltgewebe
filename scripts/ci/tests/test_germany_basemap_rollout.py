from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STYLE_PATH = REPO / "map-style" / "style-germany.json"
BASEMAP_MODULE = REPO / "apps" / "web" / "src" / "lib" / "map" / "basemap.ts"
GENERATOR = REPO / "apps" / "web" / "scripts" / "generate-basemap-config.js"
BUILD_SCRIPT = REPO / "scripts" / "basemap" / "build-germany-pmtiles.sh"
PREPARE_SCRIPT = REPO / "scripts" / "basemap" / "prepare-germany-rollout.sh"
ACTIVATE_SCRIPT = REPO / "scripts" / "basemap" / "activate-germany-basemap.sh"


class GermanyBasemapRolloutTest(unittest.TestCase):
    def setUp(self) -> None:
        self.style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))

    def test_germany_style_declares_one_nationwide_pmtiles_source(self) -> None:
        self.assertEqual(
            self.style["sources"],
            {
                "basemap-germany": {
                    "type": "vector",
                    "url": "pmtiles://basemap-germany.pmtiles",
                }
            },
        )
        self.assertEqual(
            self.style["metadata"]["weltgewebe:variant"], "germany"
        )

    def test_germany_style_has_required_visual_layers(self) -> None:
        source_layers = {
            layer["source-layer"]
            for layer in self.style["layers"]
            if layer.get("source") == "basemap-germany"
        }
        self.assertEqual(
            source_layers,
            {
                "landcover",
                "landuse",
                "water",
                "transportation",
                "building",
                "place",
            },
        )
        layer_ids = [layer["id"] for layer in self.style["layers"]]
        self.assertEqual(len(layer_ids), len(set(layer_ids)))

    def test_style_version_matches_shared_cache_contract(self) -> None:
        module = BASEMAP_MODULE.read_text(encoding="utf-8")
        version = self.style["metadata"]["weltgewebe:version"]
        self.assertIn(f'LOCAL_BASEMAP_STYLE_VERSION = "{version}"', module)
        self.assertIn("LOCAL_BASEMAP_GERMANY_STYLE_URL", module)
        self.assertIn("style-germany.json", module)

    def test_build_generator_defaults_to_regional_and_binds_identity(self) -> None:
        generator = GENERATOR.read_text(encoding="utf-8")
        self.assertIn(
            'const DEFAULT_LOCAL_BASEMAP_VARIANT = "regional"', generator
        )
        self.assertIn('["regional", "germany"]', generator)
        self.assertIn("PUBLIC_BASEMAP_VARIANT", generator)
        self.assertIn("source_commit", generator)
        self.assertIn("style_sha256", generator)
        self.assertIn("PUBLIC_SOURCE_COMMIT", generator)
        self.assertIn("basemap-build.json", generator)

    def test_builder_requires_complete_valid_snapshot_provenance(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "OSM_FILE_WAS_SET",
            "OSM_URL_WAS_SET",
            "OSM_SHA256_WAS_SET",
            "OSM_SNAPSHOT_DATE_WAS_SET",
        ):
            self.assertIn(marker, builder)
        self.assertIn('case "$SNAPSHOT_OVERRIDE_COUNT"', builder)
        self.assertIn("dt.date.fromisoformat", builder)
        self.assertIn("dt.datetime.now(dt.timezone.utc).date()", builder)
        self.assertIn("OSM_SNAPSHOT_DATE lies in the future", builder)
        self.assertLess(
            builder.index("dt.date.fromisoformat"), builder.index("if ! docker")
        )

    def test_builder_never_replaces_version_or_activates_alias(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("versioned output already exists", builder)
        self.assertIn('"activation": "opt-in"', builder)
        self.assertNotIn('mv -f "$PARTIAL_PMTILES"', builder)
        self.assertNotIn("ln -s", builder)
        self.assertNotIn("PUBLIC_BASEMAP_VARIANT=germany", builder)

    def test_prepare_publishes_bound_version_without_alias_switch(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        validation_at = prepare.index("validate:pmtiles")
        envelope_at = prepare.index("germany-pmtiles-prepared-validation-v1")
        publish_at = prepare.index('ln "$ARTIFACT_TMP" "$TARGET_ARTIFACT"')
        self.assertLess(validation_at, envelope_at)
        self.assertLess(envelope_at, publish_at)
        self.assertIn('"artifact": {', prepare)
        self.assertIn('"sha256": os.environ["ARTIFACT_SHA256"]', prepare)
        self.assertIn("ALIAS_ARTIFACT_STATE_BEFORE", prepare)
        self.assertIn("ALIAS_ARTIFACT_STATE_AFTER", prepare)
        self.assertIn("Stable aliases were NOT changed", prepare)
        self.assertNotIn("publish-basemap.sh", prepare)

    def test_activation_revalidates_freshness_immediately_before_aliases(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        second_freshness_at = activate.index(
            "# Re-evaluate freshness immediately before the first externally visible change."
        )
        switch_at = activate.index("if ! switch_alias_pair; then")
        self.assertLess(second_freshness_at, switch_at)
        between = activate[second_freshness_at:switch_at]
        self.assertIn("verify_snapshot_freshness", between)

    def test_activation_binds_prepared_report_by_artifact_content(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("prepared validation artifact binding mismatch", activate)
        self.assertIn('prepared.get("artifact", {})', activate)
        self.assertIn('"name": artifact.name', activate)
        self.assertIn('"sha256": expected_sha256', activate)
        self.assertIn('"size_bytes": expected_size', activate)
        self.assertNotIn("prepared validation archive path mismatch", activate)

    def test_activation_binds_device_proof_to_frontend_style_and_time(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        for contract in (
            "frontend_commit",
            "style_sha256",
            "proofed_at",
            "GERMANY_BASEMAP_RELEASE_PROOF_MAX_AGE_HOURS",
            "desktop-maplibre",
            "ipad-maplibre",
            "five-region-visual",
            "no-external-map-requests",
            "staging-caddy-range",
        ):
            self.assertIn(contract, activate)
        self.assertIn("Germany release proof frontend commit mismatch", activate)
        self.assertIn("Germany release proof style hash mismatch", activate)
        self.assertIn("Germany release proof is too old", activate)

    def test_activation_bounds_all_public_readbacks(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("GERMANY_BASEMAP_HTTP_CONNECT_TIMEOUT_SECONDS", activate)
        self.assertIn("GERMANY_BASEMAP_HTTP_MAX_TIME_SECONDS", activate)
        self.assertIn("--connect-timeout", activate)
        self.assertIn("--max-time", activate)
        self.assertIn('curl "${CURL_COMMON[@]}"', activate)
        self.assertIn("within the readback deadline", activate)

    def test_activation_alias_switch_and_receipt_are_rollback_bound(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("ALIASES_TOUCHED=1", activate)
        self.assertIn("restore_alias_pair", activate)
        self.assertIn("if ! switch_alias_pair; then", activate)
        self.assertIn("if ! write_activation_receipt; then", activate)
        self.assertIn("could not persist the Germany activation receipt", activate)
        self.assertIn('deploy_frontend_variant "regional"', activate)

    def test_activation_hashes_complete_public_artifact_before_receipt(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        range_at = activate.index("Range: bytes=0-126")
        full_hash_at = activate.index("PUBLIC_ARTIFACT_SHA256")
        receipt_call_at = activate.index("if ! write_activation_receipt; then")
        self.assertLess(range_at, full_hash_at)
        self.assertLess(full_hash_at, receipt_call_at)
        self.assertIn("complete public Germany PMTiles hash mismatch", activate)
        self.assertIn("complete-public-artifact-sha256", activate)

    def test_activation_receipt_heredoc_is_inside_if_statement(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        receipt_function = activate.split("write_activation_receipt() {", 1)[1].split(
            "\n}\n", 1
        )[0]
        self.assertIn('if ! RECEIPT_PATH="$receipt_tmp" \\', receipt_function)
        self.assertIn("python3 << 'PY'", receipt_function)
        self.assertIn("\nPY\n  then\n", receipt_function)
        self.assertNotIn("python3 << 'PY' || {", receipt_function)


if __name__ == "__main__":
    unittest.main()

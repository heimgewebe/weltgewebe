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

    def test_germany_style_has_the_required_visual_layer_contract(self) -> None:
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

    def test_style_version_matches_the_shared_cache_contract(self) -> None:
        basemap_module = BASEMAP_MODULE.read_text(encoding="utf-8")
        version = self.style["metadata"]["weltgewebe:version"]
        self.assertIn(
            f'LOCAL_BASEMAP_STYLE_VERSION = "{version}"', basemap_module
        )
        self.assertIn("LOCAL_BASEMAP_GERMANY_STYLE_URL", basemap_module)
        self.assertIn("style-germany.json", basemap_module)

    def test_build_generator_defaults_to_regional_and_requires_opt_in(self) -> None:
        generator = GENERATOR.read_text(encoding="utf-8")
        self.assertIn(
            'const DEFAULT_LOCAL_BASEMAP_VARIANT = "regional"', generator
        )
        self.assertIn('["regional", "germany"]', generator)
        self.assertIn("PUBLIC_BASEMAP_VARIANT", generator)
        self.assertIn('variant: "${variant}"', generator)
        self.assertIn("basemap-build.json", generator)
        self.assertIn("/local-basemap/style-germany.json", generator)

    def test_builder_is_pinned_and_does_not_activate_an_alias(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("germany-260101.osm.pbf", builder)
        self.assertIn("DEFAULT_OSM_SHA256", builder)
        self.assertIn("DEFAULT_OSM_SNAPSHOT_DATE", builder)
        self.assertIn("ghcr.io/onthegomap/planetiler@sha256:", builder)
        self.assertIn('"activation": "opt-in"', builder)
        self.assertNotIn("ln -s", builder)
        self.assertNotIn("PUBLIC_BASEMAP_VARIANT=germany", builder)

    def test_builder_requires_complete_snapshot_provenance_overrides(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "OSM_FILE_WAS_SET",
            "OSM_URL_WAS_SET",
            "OSM_SHA256_WAS_SET",
            "OSM_SNAPSHOT_DATE_WAS_SET",
        ):
            self.assertIn(marker, builder)
        self.assertIn("SNAPSHOT_OVERRIDE_COUNT != 4", builder)
        self.assertIn(
            "override OSM_FILE, OSM_URL, OSM_SHA256 and "
            "OSM_SNAPSHOT_DATE together",
            builder,
        )

    def test_prepare_step_deep_validates_before_publication(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        validate_at = prepare.index("validate:pmtiles")
        publish_at = prepare.index("publish-basemap.sh")
        self.assertLess(validate_at, publish_at)
        self.assertIn('--archive "germany=$ARTIFACT"', prepare)
        self.assertIn("style-germany.json", prepare)
        self.assertIn("Activation was NOT changed", prepare)

    def test_activation_requires_fresh_exact_evidence_and_forced_build(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        fresh_validation_at = activate.index("validate:pmtiles")
        deploy_at = activate.index('PUBLIC_BASEMAP_VARIANT=germany \\\n  "$DEPLOY_COMMAND" --build-web')
        self.assertLess(fresh_validation_at, deploy_at)
        self.assertIn("deploy-germany-pmtiles", activate)
        self.assertIn("GERMANY_BASEMAP_MAX_SOURCE_AGE_DAYS", activate)
        self.assertIn("alias_artifact != versioned_artifact", activate)
        self.assertIn("alias_meta != versioned_meta", activate)
        self.assertIn("basemap-build.json", activate)
        self.assertIn("Content-Type", activate)
        self.assertIn("Content-Range", activate)
        self.assertIn("Accept-Ranges", activate)

    def test_activation_rollback_preserves_deploy_arguments(self) -> None:
        activate = ACTIVATE_SCRIPT.read_text(encoding="utf-8")
        failure_function = activate.split("post_deploy_failure() {", 1)[1].split(
            "}", 1
        )[0]
        self.assertIn('local message="$1"', failure_function)
        self.assertIn("shift", failure_function)
        self.assertIn('rollback_frontend "$@"', failure_function)
        self.assertIn("PUBLIC_BASEMAP_VARIANT=regional", activate)
        self.assertNotIn('rollback_frontend "$message"', activate)


if __name__ == "__main__":
    unittest.main()

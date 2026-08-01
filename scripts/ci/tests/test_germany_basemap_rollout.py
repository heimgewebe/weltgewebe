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
        self.assertIn(
            "LOCAL_BASEMAP_GERMANY_STYLE_URL", basemap_module
        )
        self.assertIn("style-germany.json", basemap_module)

    def test_build_generator_defaults_to_regional_and_requires_opt_in(self) -> None:
        generator = GENERATOR.read_text(encoding="utf-8")
        self.assertIn(
            'const DEFAULT_LOCAL_BASEMAP_VARIANT = "regional"', generator
        )
        self.assertIn('["regional", "germany"]', generator)
        self.assertIn("PUBLIC_BASEMAP_VARIANT", generator)
        self.assertIn('variant: "${variant}"', generator)

    def test_builder_is_pinned_and_does_not_activate_an_alias(self) -> None:
        builder = BUILD_SCRIPT.read_text(encoding="utf-8")
        self.assertIn("germany-260101.osm.pbf", builder)
        self.assertIn("DEFAULT_OSM_SHA256", builder)
        self.assertIn("ghcr.io/onthegomap/planetiler@sha256:", builder)
        self.assertIn('"activation": "opt-in"', builder)
        self.assertNotIn("ln -s", builder)
        self.assertNotIn("PUBLIC_BASEMAP_VARIANT=germany", builder)

    def test_prepare_step_deep_validates_before_publication(self) -> None:
        prepare = PREPARE_SCRIPT.read_text(encoding="utf-8")
        validate_at = prepare.index("validate:pmtiles")
        publish_at = prepare.index("publish-basemap.sh")
        self.assertLess(validate_at, publish_at)
        self.assertIn("--archive \"germany=$ARTIFACT\"", prepare)
        self.assertIn("style-germany.json", prepare)
        self.assertIn("Activation was NOT changed", prepare)


if __name__ == "__main__":
    unittest.main()

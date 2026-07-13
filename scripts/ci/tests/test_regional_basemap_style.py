from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STYLE_PATH = REPO / "map-style" / "style.json"
UP_SCRIPT_PATH = REPO / "scripts" / "weltgewebe-up"
WORKFLOW_PATH = REPO / ".github" / "workflows" / "basemap-runtime-proof.yml"


class RegionalBasemapStyleTest(unittest.TestCase):
    def setUp(self) -> None:
        self.style = json.loads(STYLE_PATH.read_text(encoding="utf-8"))

    def test_style_declares_all_regional_pmtiles_sources(self) -> None:
        sources = self.style["sources"]
        self.assertEqual(
            sources["basemap"]["url"],
            "pmtiles://basemap-hamburg.pmtiles",
        )
        self.assertEqual(
            sources["basemap-schleswig-holstein"]["url"],
            "pmtiles://basemap-schleswig-holstein.pmtiles",
        )

    def test_each_regional_source_has_the_same_visual_layer_set(self) -> None:
        layers = self.style["layers"]
        hamburg = {
            layer["id"]
            for layer in layers
            if layer.get("source") == "basemap"
        }
        schleswig_holstein = {
            layer["id"].removesuffix("-schleswig-holstein")
            for layer in layers
            if layer.get("source") == "basemap-schleswig-holstein"
        }

        self.assertEqual(
            hamburg,
            {"water", "roads", "buildings", "place-labels"},
        )
        self.assertEqual(schleswig_holstein, hamburg)

    def test_layer_ids_are_unique_and_sources_exist(self) -> None:
        sources = self.style["sources"]
        layer_ids = [layer["id"] for layer in self.style["layers"]]
        self.assertEqual(len(layer_ids), len(set(layer_ids)))
        for layer in self.style["layers"]:
            if "source" in layer:
                self.assertIn(layer["source"], sources)

    def test_deploy_readiness_checks_each_regional_metadata_alias(self) -> None:
        script = UP_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "for regional_meta in basemap-hamburg.meta.json "
            "basemap-schleswig-holstein.meta.json; do",
            script,
        )
        expected_url = (
            '"https://weltgewebe.home.arpa/local-basemap/'
            + chr(36)
            + '{regional_meta}"'
        )
        self.assertIn(expected_url, script)

    def test_content_proof_preserves_metadata_hash_variables(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(
            'META_PATH="build/basemap/${META_NAME}"',
            workflow,
        )
        self.assertIn('"${META_PATH}"', workflow)
        self.assertNotIn('META_PATH="build/basemap/"', workflow)


if __name__ == "__main__":
    unittest.main()

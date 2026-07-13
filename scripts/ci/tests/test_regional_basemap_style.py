from __future__ import annotations

import json
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
STYLE_PATH = REPO / "map-style" / "style.json"


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


if __name__ == "__main__":
    unittest.main()

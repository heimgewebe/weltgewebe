"""Static coverage for the route-only VPS HTTP smoke boundary."""

from __future__ import annotations

import pathlib
import unittest


class VpsHttpRouteSmokeDocsTest(unittest.TestCase):
    def test_route_smoke_doc_preserves_no_migration_boundary(self) -> None:
        repo = pathlib.Path(__file__).resolve().parents[3]
        doc = repo / "docs" / "deploy" / "vps-http-route-smoke.md"
        text = doc.read_text(encoding="utf-8")

        self.assertIn("route-only", text)
        self.assertIn("do not run database migrations", text)
        self.assertIn("do not start the production API binary", text)
        self.assertIn("must not claim real API readiness", text)
        self.assertIn("do not change DNS or INWX records", text)


if __name__ == "__main__":
    unittest.main()

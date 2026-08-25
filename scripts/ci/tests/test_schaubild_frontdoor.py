"""Static contract for the separately released Schauwerk editor frontdoor."""

from __future__ import annotations

import pathlib
import unittest


class SchaubildFrontdoorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = pathlib.Path(__file__).resolve().parents[3]
        self.caddy = (self.repo / "infra/caddy/Caddyfile.vps").read_text(encoding="utf-8")
        self.compose = (self.repo / "infra/compose/compose.vps.override.yml").read_text(encoding="utf-8")

    def test_editor_is_a_separate_read_only_release_mount(self) -> None:
        self.assertIn("source: ${SCHAUWERK_EDITOR_ROOT:-/opt/schauwerk-editor}", self.compose)
        self.assertIn("target: /srv/schauwerk-editor-root", self.compose)
        self.assertIn("read_only: true", self.compose)
        self.assertIn("create_host_path: false", self.compose)
        self.assertIn("root * /srv/schauwerk-editor-root/current", self.caddy)
        api_common = self.caddy.split("(api_common)", 1)[1].split("# HTTP sites", 1)[0]
        self.assertNotIn("/srv/schauwerk-editor-root", api_common)

    def test_editor_route_precedes_generic_trailing_slash_and_frontend_routes(self) -> None:
        root_redirect = "@schauwerkRoot path /schaubild"
        route = "handle_path /schaubild/*"
        trailing = "@trailingSlash path_regexp ^/.+/$"
        generic = "# Serve only real files or explicitly prerendered Svelte routes."
        for needle in (root_redirect, route, trailing, generic):
            self.assertIn(needle, self.caddy)
        self.assertLess(self.caddy.index(root_redirect), self.caddy.index(trailing))
        self.assertLess(self.caddy.index(route), self.caddy.index(trailing))
        self.assertLess(self.caddy.index(route), self.caddy.index(generic))
        self.assertIn("redir /schaubild/ 308", self.caddy)
        self.assertIn('header Cache-Control "no-store"', self.caddy)

    def test_editor_gets_exact_cross_origin_frame_csp_not_frontend_csp(self) -> None:
        expected = (
            "header @schauwerkResponse >Content-Security-Policy \"default-src 'self'; "
            "script-src 'self'; style-src 'self'; img-src 'self' data: blob:; "
            "frame-src https://embed.diagrams.net; connect-src 'none'; object-src 'none'; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none';\""
        )
        self.assertIn(expected, self.caddy)
        self.assertIn(
            "not path /api/* /health/* /schaubild /schaubild/*",
            self.caddy,
        )
        self.assertEqual(self.caddy.count("frame-src https://embed.diagrams.net"), 1)


if __name__ == "__main__":
    unittest.main()

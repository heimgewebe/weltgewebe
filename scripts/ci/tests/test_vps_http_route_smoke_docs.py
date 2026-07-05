"""Static coverage for the route-only VPS HTTP smoke boundary."""

from __future__ import annotations

import pathlib
import unittest


class VpsHttpRouteSmokeDocsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = pathlib.Path(__file__).resolve().parents[3]
        self.doc = self.repo / "docs" / "deploy" / "vps-http-route-smoke.md"
        self.risks = self.repo / "docs" / "deploy" / "vps-http-route-smoke-risks.md"
        self.caddyfile = self.repo / "infra" / "caddy" / "Caddyfile.http-smoke"

    def test_route_smoke_doc_preserves_no_migration_boundary(self) -> None:
        text = self.doc.read_text(encoding="utf-8")

        required_phrases = [
            "route-only",
            "do not run database migrations",
            "do not start the production API binary",
            "real API readiness remains unproven",
            "do not change DNS or INWX records",
            "must not claim",
            "closure of an ops issue whose acceptance criteria require a live API health result",
        ]
        for phrase in required_phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_route_smoke_doc_names_allowed_and_disallowed_evidence(self) -> None:
        text = self.doc.read_text(encoding="utf-8")

        for allowed in [
            "/health/proxy",
            "/api/*",
            "/health/*",
            "explicit `http://weltgewebe.net` site address",
            "non-health, non-API paths are not served as the full app",
        ]:
            with self.subTest(allowed=allowed):
                self.assertIn(allowed, text)

        for disallowed in [
            "real API readiness",
            "PostgreSQL connectivity or schema readiness",
            "frontend build, CSP, asset, map, or basemap readiness",
            "DNS, INWX, ACME, HTTPS, mail, or SMTP readiness",
            "production cutover completion",
        ]:
            with self.subTest(disallowed=disallowed):
                self.assertIn(disallowed, text)

    def test_risk_note_is_substantive_and_blocks_overclaiming(self) -> None:
        text = self.risks.read_text(encoding="utf-8")

        for phrase in [
            "Evidence inflation",
            "Hidden database mutation",
            "Frontend/CSP blind spot",
            "Upstream blind spot",
            "DNS/ACME confusion",
            "Drift between config and runtime",
            "Synthetic-upstream overclaim",
        ]:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_http_smoke_caddyfile_stays_route_only(self) -> None:
        text = self.caddyfile.read_text(encoding="utf-8")

        for required in [
            "http://weltgewebe.net",
            "handle /health/proxy",
            "handle_path /api/*",
            "handle /health/*",
            "reverse_proxy api:8080",
            'respond "dns-free smoke only" 404',
        ]:
            with self.subTest(required=required):
                self.assertIn(required, text)

        for forbidden in [
            "https://",
            "tls ",
            "file_server",
            "root * /srv/weltgewebe-web",
            "try_files {path} /index.html",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()

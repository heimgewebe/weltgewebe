"""Regression tests for the repository's canonical truth surfaces."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class CanonicalTruthContractTests(unittest.TestCase):
    def test_docs_guard_installs_all_discovered_ci_test_dependencies(self) -> None:
        workflow = (ROOT / ".github/workflows/docs-guard.yml").read_text(encoding="utf-8")
        self.assertIn("pytest==8.3.4 pyyaml==6.0.2", workflow)

    def test_required_check_catalog_is_strict_and_matches_universal_jobs(self) -> None:
        path = ROOT / ".github/grabowski-required-checks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"schema_version", "required_checks"})
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(
            data["required_checks"],
            ["Required merge gate"],
        )
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for name in data["required_checks"]:
            self.assertIn(f"name: {name}", workflow)

    def test_package_license_metadata_matches_repository_license(self) -> None:
        cargo = (ROOT / "apps/api/Cargo.toml").read_text(encoding="utf-8")
        self.assertRegex(cargo, r'(?m)^license = "AGPL-3\.0-or-later"$')
        for path in (ROOT / "package.json", ROOT / "apps/web/package.json"):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(data.get("license"), "AGPL-3.0-or-later", path)
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        self.assertIn("GNU AFFERO GENERAL PUBLIC LICENSE", license_text)
        deny = (ROOT / "deny.toml").read_text(encoding="utf-8")
        self.assertRegex(deny, r'(?m)^\s*"AGPL-3\.0-or-later",?$')

    def test_readme_describes_active_implementation_not_docs_only_status(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("aktives, im Aufbau befindliches Karteninterface", text)
        self.assertNotRegex(text, r"(?i)formaler\s+\*\*docs-only")
        self.assertNotIn("<!-- Docs-only", text)

    def test_canonical_entrypoints_are_substantive(self) -> None:
        required = {
            "architecture/overview.md": ("## Komponenten", "## Hauptdatenflüsse"),
            "architecture/security.md": ("## Vertrauensgrenzen", "## Authentifizierungsflächen"),
            "runtime/README.md": ("## Laufzeitprofile", "## Domänenquellen"),
            "runbooks/README.md": ("## Einstieg nach Situation", "## Sichere Reihenfolge"),
        }
        for relative, headings in required.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertGreater(len(text.split()), 180, relative)
            for heading in headings:
                self.assertIn(heading, text, relative)

    def test_active_architecture_and_runbook_do_not_claim_missing_subsystems(self) -> None:
        architecture = (ROOT / "docs/architekturstruktur.md").read_text(encoding="utf-8")
        runbook = (ROOT / "docs/runbook.md").read_text(encoding="utf-8")
        orientation = (ROOT / "docs/policies/orientierung.md").read_text(encoding="utf-8")
        self.assertIn("keinen produktiven Outbox-Relay", architecture)
        self.assertNotIn("Outbox/JetStream-Eventing", architecture)
        self.assertRegex(runbook, r"keinen\s+implementierten WAL-/PITR-")
        self.assertNotIn("WAL-Archivierung aktiv", runbook)
        self.assertNotIn("den `outbox`-Relay-Prozess starten", runbook)
        self.assertIn("Compose ist der aktuelle Standard", orientation)

    def test_techstack_separates_current_present_planned_and_nonstandard(self) -> None:
        text = (ROOT / "docs/techstack.md").read_text(encoding="utf-8")
        for heading in (
            "## Heute implementiert und kanonisch",
            "## Im Repository vorhanden, aber nicht allgemein produktiv belegt",
            "## Geplant oder noch unvollständig",
            "## Nicht aktueller Standard",
        ):
            self.assertIn(heading, text)

    def test_data_model_names_actual_sources_and_absent_tables(self) -> None:
        text = (ROOT / "docs/datenmodell.md").read_text(encoding="utf-8")
        self.assertIn("JSONL der Standard", text)
        for table in ("sessions", "domain_accounts", "domain_nodes", "domain_edges", "passkey_credentials"):
            self.assertIn(f"`{table}`", text)
        self.assertIn("keine `conversations`, `messages`, `roles`, `outbox`", text)
        self.assertNotIn("PostgreSQL ist die alleinige Quelle der Wahrheit", text)

    def test_active_privacy_docs_do_not_promise_zero_cookies(self) -> None:
        paths = (
            "README.md",
            "docs/vision.md",
            "docs/inhalt.md",
            "docs/policies/orientierung.md",
            "docs/zusammenstellung.md",
        )
        forbidden = re.compile(r"(?i)(keine cookies|keine cookies/track|also keine cookies)")
        for relative in paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIsNone(forbidden.search(text), relative)
        combined = "\n".join((ROOT / p).read_text(encoding="utf-8") for p in paths)
        self.assertIn("Sitzungscookies", combined)


if __name__ == "__main__":
    unittest.main()

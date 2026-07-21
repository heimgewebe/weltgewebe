"""Regression tests for the repository's canonical truth surfaces."""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class CanonicalTruthContractTests(unittest.TestCase):
    def test_docmeta_ci_jobs_install_the_pinned_yaml_dependency(self) -> None:
        docs_workflow = (ROOT / ".github/workflows/docs-guard.yml").read_text(
            encoding="utf-8"
        )
        main_workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("pytest==8.3.4 pyyaml==6.0.2", docs_workflow)
        self.assertIn("pytest==8.3.4 pyyaml==6.0.2", main_workflow)

    def test_required_check_catalog_is_strict_and_matches_trusted_producers(
        self,
    ) -> None:
        path = ROOT / ".github/grabowski-required-checks.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(data), {"schema_version", "required_checks"})
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(
            data["required_checks"],
            ["Required merge gate", "Review evidence gate"],
        )
        producers = {
            "Required merge gate": ROOT / ".github/workflows/ci.yml",
            "Review evidence gate": ROOT / ".github/workflows/review-evidence.yml",
        }
        self.assertEqual(set(data["required_checks"]), set(producers))
        required_merge_workflow = producers["Required merge gate"].read_text(
            encoding="utf-8"
        )
        self.assertIn("name: Required merge gate", required_merge_workflow)
        review_workflow = producers["Review evidence gate"].read_text(encoding="utf-8")
        self.assertNotIn("\n    name: Review evidence gate\n", review_workflow)
        self.assertIn("name: Review evidence evaluator", review_workflow)
        self.assertGreaterEqual(
            review_workflow.count("context='Review evidence gate'"),
            2,
        )
        self.assertIn("ref: main", review_workflow)
        self.assertIn("fetch-depth: 1", review_workflow)
        self.assertIn("persist-credentials: false", review_workflow)
        self.assertNotIn("git fetch", review_workflow)
        self.assertNotIn("refs/pull/", review_workflow)
        self.assertIn("evaluate-materialized", review_workflow)
        self.assertIn("application/vnd.github.diff", review_workflow)
        self.assertIn("diff_file_count", review_workflow)
        self.assertIn("max_artifact_bytes", review_workflow)
        self.assertIn(
            "--authorities-file .github/review-evidence-authorities.json",
            review_workflow,
        )

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
        self.assertIn("aktives, im Aufbau befindliches Karten- und Koordinationssystem", text)
        self.assertIn("föderierten Weltgewebe OS", text)
        self.assertIn("Docker Compose die heutige reale Runtime", text)
        self.assertNotRegex(text, r"(?i)formaler\s+\*\*docs-only")
        self.assertNotIn("<!-- Docs-only", text)

    def test_canonical_entrypoints_are_substantive(self) -> None:
        required = {
            "architecture/weltgewebe-os.md": ("## 2. Verfassungsprinzipien", "## 7. Plattformarchitektur"),
            "architecture/overview.md": ("## Komponenten", "## Hauptdatenflüsse"),
            "architecture/security.md": (
                "## Vertrauensgrenzen",
                "## Authentifizierungsflächen",
            ),
            "runtime/README.md": ("## Laufzeitprofile", "## Domänenquellen"),
            "runbooks/README.md": (
                "## Einstieg nach Situation",
                "## Sichere Reihenfolge",
            ),
        }
        for relative, headings in required.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertGreater(len(text.split()), 180, relative)
            for heading in headings:
                self.assertIn(heading, text, relative)

    def test_active_architecture_and_runbook_do_not_claim_missing_subsystems(
        self,
    ) -> None:
        architecture = (ROOT / "docs/architekturstruktur.md").read_text(
            encoding="utf-8"
        )
        runbook = (ROOT / "docs/runbook.md").read_text(encoding="utf-8")
        orientation = (ROOT / "docs/policies/orientierung.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("keinen produktiven Outbox-Relay", architecture)
        self.assertNotIn("Outbox/JetStream-Eventing", architecture)
        self.assertRegex(runbook, r"keinen\s+implementierten WAL-/PITR-")
        self.assertNotIn("WAL-Archivierung aktiv", runbook)
        self.assertNotIn("den `outbox`-Relay-Prozess starten", runbook)
        self.assertIn("Compose ist die aktuelle Betriebsrealität", orientation)
        self.assertIn("Kubernetes ist nach ADR-0010 die kanonische Zielplattform", orientation)
        self.assertIn("noch keine heutige Runtime- oder HA-Wahrheit", orientation)

    def test_techstack_separates_current_present_planned_and_nonstandard(self) -> None:
        text = (ROOT / "docs/techstack.md").read_text(encoding="utf-8")
        for heading in (
            "## Heute implementiert und kanonisch",
            "## Im Repository vorhanden, aber nicht allgemein produktiv belegt",
            "## Kanonische Zielplattform, noch nicht als Runtime belegt",
            "## Geplant oder noch unvollständig",
            "## Nicht als heutige Betriebswahrheit belegt",
        ):
            self.assertIn(heading, text)
        self.assertIn("Kubernetes als Primärorchestrierung für Staging und Produktion", text)
        self.assertIn("noch keine Behauptung über eine laufende Produktionsruntime", text)
        self.assertIn("Compose bleibt bis zum belegten Cutover der reale Betriebsweg", text)
        self.assertIn("Nomad als neue Primärzielrichtung", text)

    def test_data_model_names_actual_sources_and_table_truth(self) -> None:
        text = (ROOT / "docs/datenmodell.md").read_text(encoding="utf-8")
        compose_prod = (ROOT / "infra/compose/compose.prod.yml").read_text(
            encoding="utf-8"
        )
        env_example = (ROOT / ".env.example").read_text(encoding="utf-8")
        migrations = "\n".join(
            path.read_text(encoding="utf-8")
            for path in sorted((ROOT / "apps/api/migrations").glob("*.up.sql"))
        )

        self.assertIn("Repository-Produktionsvertrag", text)
        self.assertIn("JSONL bleibt der lokale, testbare Code-Default", text)
        self.assertIn(
            "WELTGEWEBE_DOMAIN_READ_SOURCE: ${WELTGEWEBE_DOMAIN_READ_SOURCE:-postgres}",
            compose_prod,
        )
        self.assertIn("WELTGEWEBE_DOMAIN_READ_SOURCE=jsonl", env_example)
        for table in (
            "sessions",
            "domain_accounts",
            "domain_nodes",
            "domain_edges",
            "passkey_credentials",
            "domain_conversations",
            "domain_messages",
            "domain_outbox",
        ):
            self.assertIn(f"`{table}`", text)
        for table in ("domain_conversations", "domain_messages", "domain_outbox"):
            self.assertRegex(
                migrations,
                rf"(?im)^CREATE TABLE {table} \(",
                f"{table} must remain backed by a PostgreSQL migration",
            )
        self.assertIn("ohne produktive\n`roles`-Tabelle", text)
        self.assertNotRegex(
            migrations,
            r"(?im)^\s*CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?roles\b",
        )
        self.assertNotIn("Domänendaten bleibt JSONL der Standard", text)
        self.assertNotIn("PostgreSQL ist die alleinige Quelle der Wahrheit", text)

    def test_active_privacy_docs_do_not_promise_zero_cookies(self) -> None:
        paths = (
            "README.md",
            "docs/vision.md",
            "docs/inhalt.md",
            "docs/policies/orientierung.md",
            "docs/zusammenstellung.md",
        )
        forbidden = re.compile(
            r"(?i)(keine cookies|keine cookies/track|also keine cookies)"
        )
        for relative in paths:
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertIsNone(forbidden.search(text), relative)
        combined = "\n".join((ROOT / p).read_text(encoding="utf-8") for p in paths)
        self.assertIn("Sitzungscookies", combined)


if __name__ == "__main__":
    unittest.main()

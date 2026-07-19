"""Regression tests for Semantic Search v1 T003 PostgreSQL foundation."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.search.probe_postgres_foundation import RESULT, check_result

ROOT = Path(__file__).resolve().parents[3]
UP_MIGRATION = ROOT / "contracts/search/postgres-foundation.up.sql"
DOWN_MIGRATION = ROOT / "contracts/search/postgres-foundation.down.sql"
SCHEMA = ROOT / "contracts/search/postgres-foundation-receipt.schema.json"
ARCHITECTURE = ROOT / "architecture/semantic-search.md"


class SemanticSearchPostgresFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.receipt = json.loads(RESULT.read_text(encoding="utf-8"))
        cls.up_sql = UP_MIGRATION.read_text(encoding="utf-8")
        cls.down_sql = DOWN_MIGRATION.read_text(encoding="utf-8")
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_checked_in_receipt_is_hash_bound_and_internally_consistent(self) -> None:
        check_result(RESULT)
        self.assertEqual(self.receipt["schema_version"], 1)
        self.assertEqual(self.receipt["task_id"], "WELTGEWEBE-SEMANTIC-SEARCH-V1-T003")
        self.assertEqual(self.receipt["environment"]["external_cost_usd"], 0)
        self.assertEqual(
            self.receipt["quality"]["performance"]["scope"],
            "docker_exec_psql_roundtrip_not_database_only",
        )

    def test_real_postgres_quality_meets_or_exceeds_t002_lexical_reference(self) -> None:
        measured = self.receipt["quality"]["postgres_fts_pg_trgm"]
        reference = self.receipt["quality"]["t002_reference_summary"]
        self.assertGreaterEqual(
            measured["natural_top3_relevant_count"],
            reference["natural_top3_relevant_count"],
        )
        self.assertLessEqual(measured["false_top1_count"], reference["false_top1_count"])
        self.assertEqual(measured["visibility_leak_count"], 0)
        self.assertEqual(len(measured["cases"]), 24)
        self.assertTrue(all(len(case["ranked_node_ids"]) <= 10 for case in measured["cases"]))

    def test_extension_evidence_stops_pgvector_instead_of_assuming_it(self) -> None:
        extensions = self.receipt["postgres"]["extensions"]
        self.assertTrue(extensions["pgcrypto"]["available"])
        self.assertFalse(extensions["pgcrypto"]["installed"])
        self.assertTrue(extensions["pg_trgm"]["installed"])
        self.assertFalse(extensions["vector"]["available"])
        self.assertFalse(extensions["vector"]["installed"])
        self.assertFalse(self.receipt["decision"]["pgvector_ready_on_canonical_image"])
        self.assertFalse(self.receipt["decision"]["embedding_runtime_allowed"])
        self.assertIn("stop_pgvector", self.receipt["postgres"]["pgvector_decision"])

    def test_proof_sql_is_not_an_embedded_production_migration(self) -> None:
        self.assertEqual(UP_MIGRATION.parent, ROOT / "contracts/search")
        self.assertNotIn("CREATE EXTENSION IF NOT EXISTS pgcrypto", self.up_sql)
        self.assertIn("CREATE EXTENSION IF NOT EXISTS pg_trgm", self.up_sql)

    def test_projection_schema_binds_generation_source_and_model_identity(self) -> None:
        required_fragments = (
            "CREATE TABLE search_index_generations",
            "provider TEXT NOT NULL",
            "model_id TEXT NOT NULL",
            "model_revision TEXT NOT NULL",
            "dimension INTEGER NOT NULL",
            "document_revision TEXT NOT NULL",
            "normalization_revision TEXT NOT NULL",
            "source_version BIGINT NOT NULL",
            "source_revision TEXT NOT NULL",
            "content_sha256 TEXT NOT NULL",
            "PRIMARY KEY (generation_id, node_id)",
            "search_index_generations_one_active",
        )
        for fragment in required_fragments:
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.up_sql)

    def test_visibility_deletion_generation_and_authorization_precede_scoring(self) -> None:
        authorized = self.up_sql.index("), authorized AS (")
        scored = self.up_sql.index("), scored AS (")
        self.assertLess(authorized, scored)
        for boundary in (
            "generation.state = 'active'",
            "projection.status = 'active'",
            "p_viewer_scope = ANY(projection.visibility_scopes)",
            "projection.node_id = ANY(p_allowed_node_ids)",
            "projection.kind = ANY(p_kinds)",
            "projection.tags && p_tags",
            "projection.language = ANY(p_languages)",
        ):
            with self.subTest(boundary=boundary):
                self.assertIn(boundary, self.up_sql[authorized:scored])

    def test_multi_instance_and_generation_transitions_are_serialized(self) -> None:
        self.assertGreaterEqual(self.up_sql.count("pg_advisory_xact_lock"), 2)
        integrity = self.receipt["integrity"]
        self.assertEqual(integrity["multi_instance"]["final_source_version"], 3)
        self.assertEqual(integrity["multi_instance"]["idempotent_outcome"], "idempotent")
        self.assertEqual(integrity["multi_instance"]["stale_outcome"], "stale")
        self.assertTrue(integrity["multi_instance"]["equal_version_conflict_rejected"])
        self.assertTrue(
            integrity["multi_instance"]["equal_version_visibility_conflict_rejected"]
        )
        self.assertIn(
            "p_status IS NOT DISTINCT FROM current_row.status",
            self.up_sql,
        )
        self.assertIn(
            "normalized_visibility_scopes IS NOT DISTINCT FROM current_row.visibility_scopes",
            self.up_sql,
        )
        self.assertEqual(integrity["active_generation_count"], 1)
        self.assertTrue(integrity["inactive_generation_returns_no_candidates"])

    def test_regeneration_backup_restore_and_rollback_preserve_truth(self) -> None:
        integrity = self.receipt["integrity"]
        self.assertTrue(integrity["regeneration"]["identical"])
        self.assertEqual(
            integrity["regeneration"]["before_sha256"],
            integrity["regeneration"]["after_sha256"],
        )
        self.assertTrue(integrity["backup_restore"]["identical"])
        self.assertTrue(integrity["backup_restore"]["down_migration_preserves_domain_nodes"])
        self.assertNotIn("DROP TABLE IF EXISTS domain_nodes", self.down_sql)
        self.assertNotIn("DROP EXTENSION", self.down_sql)

    def test_no_ann_index_or_runtime_surface_is_introduced(self) -> None:
        lowered = self.up_sql.lower()
        self.assertNotIn("hnsw", lowered)
        self.assertNotIn("ivfflat", lowered)
        self.assertFalse(self.receipt["schema"]["ann_or_hnsw_present"])
        non_claims = set(self.receipt["does_not_establish"])
        self.assertIn("search API, worker, web UI or backfill", non_claims)
        self.assertIn("production deployment or public semantic live proof", non_claims)
        self.assertIn("SemantAH shutdown authority", non_claims)

    def test_receipt_schema_is_closed_at_the_top_level(self) -> None:
        self.assertEqual(self.schema["type"], "object")
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(
            self.schema["properties"]["task_id"]["const"],
            "WELTGEWEBE-SEMANTIC-SEARCH-V1-T003",
        )

    def test_architecture_documents_t003_boundaries_and_measured_stop(self) -> None:
        text = ARCHITECTURE.read_text(encoding="utf-8")
        for phrase in (
            "T003-Livebeleg",
            "PostgreSQL 16.14",
            "`pg_trgm` 1.6",
            "pgvector ist im kanonischen PostgreSQL-Image nicht verfügbar",
            "14 von 19",
            "keine Search-API",
            "keinen Worker",
            "keinen Produktionsrollout",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()

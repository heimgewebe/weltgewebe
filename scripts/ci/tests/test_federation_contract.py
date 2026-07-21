from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class FederationContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.event_schema = json.loads(
            (ROOT / "contracts/federation/v1/event.schema.json").read_text()
        )
        self.cell_schema = json.loads(
            (ROOT / "contracts/federation/v1/cell-descriptor.schema.json").read_text()
        )
        self.event_example = json.loads(
            (ROOT / "contracts/federation/v1/examples/event.example.json").read_text()
        )
        self.cell_example = json.loads(
            (
                ROOT
                / "contracts/federation/v1/examples/cell-descriptor.example.json"
            ).read_text()
        )

    def test_wire_examples_cover_every_required_field(self) -> None:
        self.assertEqual(
            set(self.event_schema["required"]), set(self.event_example)
        )
        self.assertEqual(
            set(self.cell_schema["required"]), set(self.cell_example)
        )
        self.assertEqual(self.event_example["protocol_version"], "wg-federation/1")
        self.assertEqual(self.event_example["schema_version"], 1)
        self.assertEqual(self.cell_example["active_key"]["algorithm"], "Ed25519")
        self.assertRegex(
            self.event_example["object_address"],
            r"^wg://[a-z0-9.-]+/(node|edge|shared-room)/[A-Za-z0-9._~-]+$",
        )
        self.assertEqual(len(self.event_example["signature"]), 86)
        self.assertNotEqual(self.event_example["signature"], "A" * 86)
        self.assertEqual(len(self.cell_example["active_key"]["public_key"]), 43)

    def test_event_schema_is_closed_and_scope_is_explicit(self) -> None:
        self.assertFalse(self.event_schema["additionalProperties"])
        self.assertEqual(
            self.event_schema["properties"]["scope"]["enum"],
            ["neighbourhood", "global"],
        )
        self.assertNotIn("local", json.dumps(self.event_schema))
        self.assertNotIn("private", json.dumps(self.event_schema))
        self.assertEqual(
            self.event_schema["properties"]["event_type"]["enum"],
            ["object.upserted", "object.deleted"],
        )
        self.assertEqual(
            self.event_schema["properties"]["event_id"]["pattern"],
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        )

    def test_public_boundary_uses_http_contract_not_internal_fabric(self) -> None:
        source = (ROOT / "apps/api/src/federation.rs").read_text()
        self.assertIn('"/federation/v1/cell"', source)
        self.assertIn('"/federation/v1/events"', source)
        self.assertIn('"/federation/v1/objects"', source)
        self.assertNotIn("async_nats", source)
        self.assertNotIn("NATS_URL", source)
        self.assertNotRegex(source, r"kube|kubernetes|cluster\.local")
        self.assertIn("FEDERATION_SIGNING_KEY_B64", source)
        self.assertIn("refusing ephemeral fallback", source)
        self.assertIn("TOO_MANY_REQUESTS", source)
        self.assertIn("pg_advisory_xact_lock", source)
        self.assertIn("peer key is inactive", source)
        self.assertIn("#[serde(deny_unknown_fields)]", source)
        self.assertIn("JsonRejection", source)
        self.assertIn("serde_jcs::to_vec", source)
        self.assertIn("deserialize_canonical_uuid", source)
        self.assertIn("FOR SHARE OF r, k", source)

    def test_wire_signature_is_language_neutral_and_fixture_bound(self) -> None:
        wire = (ROOT / "docs/specs/federation-wire-v1.md").read_text()
        self.assertIn("RFC 8785", wire)
        self.assertIn("JSON Canonicalization Scheme", wire)
        self.assertIn(
            "d0e9fde82180c8e1585f2a3654807853d0b84b8b5dc78ffc741366591b592fb6",
            wire,
        )
        self.assertIn(self.event_example["signature"], wire)

    def test_public_router_is_outside_browser_auth_and_csrf_layers(self) -> None:
        source = (ROOT / "apps/api/src/lib.rs").read_text()
        with_state = source.index(".with_state(state)")
        federation_merge = source.index(".merge(federation_router)")
        self.assertGreater(federation_merge, with_state)
        protected_router = source.index("api_router()")
        self.assertLess(protected_router, with_state)
        self.assertIn("auth_middleware", source[protected_router:with_state])
        self.assertIn("require_csrf", source[protected_router:with_state])
        self.assertIn('.nest("/api", federation_router.clone())', source[with_state:])

    def test_storage_separates_applied_inbox_from_quarantine(self) -> None:
        migration = (
            ROOT
            / "apps/api/migrations/20260720000001_federation_core.up.sql"
        ).read_text()
        for table in (
            "federation_peer_relationships",
            "federation_peer_keys",
            "federation_objects",
            "federation_inbox",
            "federation_quarantine",
            "federation_outbox",
        ):
            self.assertIn(f"CREATE TABLE {table}", migration)
        inbox = migration.split("CREATE TABLE federation_inbox", 1)[1].split(
            "CREATE TABLE federation_quarantine", 1
        )[0]
        self.assertNotIn("quarantined", inbox)
        self.assertIn("envelope_sha256", inbox)
        self.assertRegex(
            migration,
            re.compile(r"federation_peer_keys.*PRIMARY KEY \(remote_cell_id, key_id\)", re.S),
        )
        self.assertIn("UNIQUE (event_id, envelope_sha256, reason)", migration)

        hardening = (
            ROOT
            / "apps/api/migrations/20260721000001_federation_core_hardening.up.sql"
        ).read_text()
        self.assertIn("CREATE TABLE federation_event_receipts", hardening)
        self.assertIn("PRIMARY KEY", hardening)
        self.assertIn("federation_inbox_event_receipt", hardening)
        self.assertIn("federation_outbox_event_receipt", hardening)
        self.assertIn("federation_validate_event_receipt_direction", hardening)

    def test_runtime_and_schema_share_actor_and_version_domains(self) -> None:
        source = (ROOT / "apps/api/src/federation.rs").read_text()
        self.assertIn("value.chars().count() > 128", source)
        self.assertEqual(
            self.event_schema["properties"]["object_version"]["maximum"],
            9223372036854775807,
        )
        previous = self.event_schema["properties"]["previous_version"]["oneOf"][0]
        self.assertEqual(previous["maximum"], 9223372036854775807)

    def test_implementation_registry_binds_runtime_browser_and_database_proofs(self) -> None:
        registry = (ROOT / "audit/impl-registry.yaml").read_text()
        self.assertIn("impl.api.federation-core-v1", registry)
        for evidence in (
            "apps/api/src/federation.rs",
            "apps/api/tests/api_federation_two_cell.rs",
            "apps/api/tests/db_federation_persistence.rs",
            "apps/web/tests/federation-pilot.spec.ts",
            "docs/specs/federation-wire-v1.md",
            "docs/proofs/weltgewebe-os-v1-t005-two-cell-proof.md",
        ):
            self.assertIn(evidence, registry)
            self.assertTrue((ROOT / evidence).exists(), evidence)

    def test_two_cell_proof_covers_partition_and_negative_cases(self) -> None:
        proof = (ROOT / "apps/api/tests/api_federation_two_cell.rs").read_text()
        for evidence in (
            "two_cells_exchange_objects_survive_partition_and_converge",
            "shared-room",
            "Duplicate",
            "signature",
            "noncanonical_event_id",
            "StatusCode::BAD_REQUEST",
            "stale",
            "blocked",
            "tombstone",
        ):
            self.assertIn(evidence, proof)


if __name__ == "__main__":
    unittest.main()

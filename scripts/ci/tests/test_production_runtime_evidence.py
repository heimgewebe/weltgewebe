from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.ops import collect_production_runtime_evidence as evidence
from scripts.ops.check_public_live_readiness import FetchResult


NOW = datetime(2026, 7, 14, 18, 0, tzinfo=timezone.utc)
TABLES = ",".join(evidence.EXPECTED_TABLES)


class ProductionRuntimeEvidenceTest(unittest.TestCase):
    def test_runtime_probe_reads_only_allowlisted_keys_individually(self) -> None:
        calls: list[list[str]] = []
        aliases = {
            "WELTGEWEBE_DOMAIN_READ_SOURCE": "pg\n",
            "WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE": "postgres\n",
            "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE": "db\n",
            "WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE": "postgres\n",
            "WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE": "pg\n",
            "WELTGEWEBE_API_STARTUP_MIGRATIONS": "verify-applied\n",
        }

        def runner(argv):
            calls.append(list(argv))
            return evidence.CommandResult(0, aliases[argv[-1]])

        result = evidence.collect_runtime_modes(
            compose_prefix=["docker", "compose", "-p", "weltgewebe"],
            service="api",
            runner=runner,
        )

        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["complete_environment_read"])
        self.assertFalse(result["confidential_values_read"])
        self.assertEqual(len(calls), len(evidence.RUNTIME_EXPECTATIONS))
        self.assertEqual({call[-1] for call in calls}, set(evidence.RUNTIME_EXPECTATIONS))
        for call in calls:
            self.assertEqual(call[-5:-1], ["exec", "-T", "api", "printenv"])

    def test_runtime_probe_rejects_unknown_value_without_echoing_it(self) -> None:
        secret_like = "postgresql://operator:secret@example/db"

        def runner(argv):
            value = secret_like if argv[-1] == "WELTGEWEBE_DOMAIN_READ_SOURCE" else "postgres"
            return evidence.CommandResult(0, value)

        with self.assertRaises(evidence.EvidenceError) as caught:
            evidence.collect_runtime_modes(
                compose_prefix=["docker", "compose"],
                service="api",
                runner=runner,
            )
        self.assertNotIn(secret_like, str(caught.exception))

    def test_runtime_probe_reports_nonproduction_modes_as_failed_checks(self) -> None:
        def runner(argv):
            key = argv[-1]
            if key == "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE":
                return evidence.CommandResult(0, "jsonl\n")
            if key == "WELTGEWEBE_API_STARTUP_MIGRATIONS":
                return evidence.CommandResult(0, "run\n")
            return evidence.CommandResult(0, "postgres\n")

        result = evidence.collect_runtime_modes(
            compose_prefix=["docker", "compose"],
            service="api",
            runner=runner,
        )
        self.assertEqual(result["status"], "fail")
        failed = {item["key"] for item in result["checks"] if item["status"] == "fail"}
        self.assertEqual(
            failed,
            {"WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE", "WELTGEWEBE_API_STARTUP_MIGRATIONS"},
        )

    def test_public_evidence_binds_ready_and_build_headers(self) -> None:
        def fetcher(url, headers, timeout):
            del headers, timeout
            if url.endswith("/health/ready"):
                body = {"status": "ok", "checks": {"database": True, "nats": True, "policy": True}}
                return FetchResult(url, 200, {}, json.dumps(body).encode())
            if url == "https://api.weltgewebe.net/version":
                body = {"version": "0.1.0", "commit": "a" * 40, "build_timestamp": "2026-07-14T17:00:00Z"}
                return FetchResult(
                    url,
                    200,
                    {"X-Weltgewebe-API-Build": "a" * 40},
                    json.dumps(body).encode(),
                )
            body = {"version": "0.1.0", "commit": "b" * 40}
            return FetchResult(
                url,
                200,
                {"X-Weltgewebe-Build": "b" * 40},
                json.dumps(body).encode(),
            )

        result = evidence.collect_public_evidence(
            domain="weltgewebe.net",
            api_domain="api.weltgewebe.net",
            timeout=1.0,
            fetcher=fetcher,
        )
        self.assertEqual(result["status"], "pass")
        self.assertEqual([item["status"] for item in result["checks"]], ["pass", "pass", "pass"])

    def test_public_evidence_fails_when_header_and_body_commit_diverge(self) -> None:
        def fetcher(url, headers, timeout):
            del headers, timeout
            if url.endswith("/health/ready"):
                payload = {"status": "ok", "checks": {"database": True, "nats": True, "policy": True}}
                return FetchResult(url, 200, {}, json.dumps(payload).encode())
            if "api.weltgewebe.net" in url:
                payload = {"version": "0.1.0", "commit": "a" * 40, "build_timestamp": "x"}
                return FetchResult(url, 200, {"X-Weltgewebe-API-Build": "c" * 40}, json.dumps(payload).encode())
            payload = {"version": "0.1.0", "commit": "b" * 40}
            return FetchResult(url, 200, {"X-Weltgewebe-Build": "b" * 40}, json.dumps(payload).encode())

        result = evidence.collect_public_evidence(
            domain="weltgewebe.net",
            api_domain="api.weltgewebe.net",
            timeout=1.0,
            fetcher=fetcher,
        )
        self.assertEqual(result["status"], "fail")
        api = next(item for item in result["checks"] if item["name"] == "api-release-identity")
        self.assertFalse(api["header_matches_body"])


    def test_public_evidence_reports_unknown_api_identity_without_aborting(self) -> None:
        def fetcher(url, headers, timeout):
            del headers, timeout
            if url.endswith("/health/ready"):
                payload = {"status": "ok", "checks": {"database": True, "nats": True, "policy": True}}
                return FetchResult(url, 200, {}, json.dumps(payload).encode())
            if "api.weltgewebe.net" in url:
                payload = {"version": "0.1.0", "commit": "unknown", "build_timestamp": "unknown"}
                return FetchResult(url, 200, {}, json.dumps(payload).encode())
            payload = {"version": "0.1.0", "commit": "b" * 40}
            return FetchResult(url, 200, {"X-Weltgewebe-Build": "b" * 8}, json.dumps(payload).encode())

        result = evidence.collect_public_evidence(
            domain="weltgewebe.net",
            api_domain="api.weltgewebe.net",
            timeout=1.0,
            fetcher=fetcher,
        )
        self.assertEqual(result["status"], "fail")
        api = next(item for item in result["checks"] if item["name"] == "api-release-identity")
        self.assertEqual(api["commit"], "unknown")
        self.assertFalse(api["commit_valid"])
        self.assertFalse(api["build_header_present"])

    def make_backup_fixture(self, root: Path, *, created_at: str = "2026-07-14T17:00:00Z") -> tuple[Path, Path, str]:
        backup = root / "weltgewebe-postgres-test.sql.gz"
        backup.write_bytes(b"deterministic-backup")
        digest = hashlib.sha256(backup.read_bytes()).hexdigest()
        manifest = root / "weltgewebe-postgres-test.sha256.manifest"
        manifest.write_text(
            "\n".join(
                [
                    "contract=weltgewebe-postgres-backup-v1",
                    f"created_at={created_at}",
                    f"file={backup.name}",
                    f"sha256={digest}",
                    f"bytes={backup.stat().st_size}",
                    "git_commit=" + "d" * 40,
                    f"tables={TABLES}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return manifest, backup, digest

    def make_restore_fixture(self, root: Path, backup: Path, digest: str, *, created_at: str = "2026-07-14T17:30:00Z") -> Path:
        proof = root / "weltgewebe-postgres-test.restore-proof"
        proof.write_text(
            "\n".join(
                [
                    "contract=weltgewebe-postgres-restore-proof-v1",
                    f"created_at={created_at}",
                    f"backup_file={backup.name}",
                    f"backup_sha256={digest}",
                    f"tables={TABLES}",
                    "result=ok",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        return proof

    def test_backup_restore_and_offhost_evidence_bind_same_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            production = root / "production"
            offhost = root / "offhost"
            production.mkdir()
            offhost.mkdir()
            manifest, backup_file, digest = self.make_backup_fixture(production)
            proof = self.make_restore_fixture(production, backup_file, digest)
            offhost_backup = offhost / backup_file.name
            offhost_backup.write_bytes(backup_file.read_bytes())
            offhost_manifest = offhost / manifest.name
            offhost_manifest.write_bytes(manifest.read_bytes())

            backup = evidence.collect_backup_evidence(
                manifest_path=manifest,
                now=NOW,
                max_age=timedelta(hours=26),
            )
            restore = evidence.collect_restore_evidence(
                proof_path=proof,
                backup=backup,
                now=NOW,
                max_age=timedelta(hours=192),
            )
            copied = evidence.collect_offhost_evidence(
                manifest_path=offhost_manifest,
                backup=backup,
            )

            self.assertEqual(backup["status"], "pass")
            self.assertTrue(backup["hash_matches"])
            self.assertEqual(restore["status"], "pass")
            self.assertTrue(restore["backup_matches_manifest"])
            self.assertEqual(copied["status"], "pass")
            self.assertTrue(copied["copied_file_hash_matches"])

    def test_stale_backup_is_reported_without_inflating_the_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, _, _ = self.make_backup_fixture(root, created_at="2026-07-10T00:00:00Z")
            result = evidence.collect_backup_evidence(
                manifest_path=manifest,
                now=NOW,
                max_age=timedelta(hours=26),
            )
            self.assertEqual(result["status"], "fail")
            self.assertFalse(result["fresh"])

    def test_restore_proof_must_match_selected_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, backup_file, digest = self.make_backup_fixture(root)
            proof = self.make_restore_fixture(root, backup_file, "e" * 64)
            backup = evidence.collect_backup_evidence(
                manifest_path=manifest,
                now=NOW,
                max_age=timedelta(hours=26),
            )
            restore = evidence.collect_restore_evidence(
                proof_path=proof,
                backup=backup,
                now=NOW,
                max_age=timedelta(hours=192),
            )
            self.assertEqual(restore["status"], "fail")
            self.assertFalse(restore["backup_matches_manifest"])


    def test_restore_proof_must_not_predate_selected_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, backup_file, digest = self.make_backup_fixture(
                root,
                created_at="2026-07-14T17:00:00Z",
            )
            proof = self.make_restore_fixture(
                root,
                backup_file,
                digest,
                created_at="2026-07-14T16:59:59Z",
            )
            backup = evidence.collect_backup_evidence(
                manifest_path=manifest,
                now=NOW,
                max_age=timedelta(hours=26),
            )
            restore = evidence.collect_restore_evidence(
                proof_path=proof,
                backup=backup,
                now=NOW,
                max_age=timedelta(hours=192),
            )
            self.assertEqual(restore["status"], "fail")
            self.assertFalse(restore["not_before_backup"])

    def test_offhost_is_explicitly_not_proven_when_omitted(self) -> None:
        result = evidence.collect_offhost_evidence(manifest_path=None, backup={})
        self.assertEqual(result["status"], "not-provided")
        self.assertFalse(result["required_for_overall_pass"])

    def test_evidence_envelope_states_scope_and_optional_offhost_boundary(self) -> None:
        passing = {"status": "pass"}
        payload = evidence.build_evidence(
            public=passing,
            runtime=passing,
            backup=passing,
            restore=passing,
            offhost={"status": "not-provided", "required_for_overall_pass": False},
            generated_at=NOW,
        )
        self.assertEqual(payload["status"], "partial")
        self.assertTrue(payload["runtime_collection_read_only"])
        self.assertFalse(payload["runtime_mutation_performed"])
        self.assertTrue(payload["report_write_is_only_mutation"])
        self.assertTrue(payload["values_redacted"])
        self.assertIn(
            "off-host recovery when no off-host manifest is supplied",
            payload["evidence_boundary"]["does_not_prove"],
        )


    def test_evidence_requires_verified_offhost_copy_for_full_pass(self) -> None:
        passing = {"status": "pass"}
        payload = evidence.build_evidence(
            public=passing,
            runtime=passing,
            backup=passing,
            restore=passing,
            offhost={"status": "pass", "required_for_overall_pass": True},
            generated_at=NOW,
        )
        self.assertEqual(payload["status"], "pass")

    def test_atomic_json_output_is_private_and_complete(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / "nested" / "evidence.json"
            payload = {"status": "pass", "schema_version": 1}
            evidence.write_json_atomic(target, payload)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), payload)
            mode = stat.S_IMODE(os.stat(target).st_mode)
            self.assertEqual(mode, 0o600)
            self.assertEqual(list(target.parent.glob(f".{target.name}.*")), [])


    def test_deploy_docs_preserve_redaction_and_partial_status_contract(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        text = (repo / "docs" / "deploy" / "README.md").read_text(encoding="utf-8")
        for phrase in (
            "collect_production_runtime_evidence.py",
            "vollständige Containerumgebung wird weder",
            "status=pass",
            "Zustand `partial`",
            "Code `2`",
            "Dateimodus `0600`",
            "evidence_boundary",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)


    def test_public_text_sanitizer_does_not_echo_secret_shaped_values(self) -> None:
        secret_like = "postgresql://operator:secret@example.test/database"
        self.assertEqual(evidence.safe_public_text(secret_like), "<invalid>")
        self.assertNotIn(secret_like, evidence.safe_public_text(secret_like))


    def test_selected_metadata_and_backup_symlinks_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_metadata = root / "real.manifest"
            real_metadata.write_text("contract=weltgewebe-postgres-backup-v1\n", encoding="utf-8")
            metadata_link = root / "link.manifest"
            metadata_link.symlink_to(real_metadata.name)
            with self.assertRaises(evidence.EvidenceError):
                evidence.read_key_value_file(
                    metadata_link,
                    allowed_keys=evidence.BACKUP_MANIFEST_KEYS,
                )

            real_backup = root / "real.sql.gz"
            real_backup.write_bytes(b"backup")
            backup_link = root / "link.sql.gz"
            backup_link.symlink_to(real_backup.name)
            with self.assertRaises(evidence.EvidenceError):
                evidence.sha256_and_size(backup_link)

    def test_metadata_size_limit_is_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "oversized.manifest"
            path.write_bytes(b"x" * (evidence.MAX_EVIDENCE_METADATA_BYTES + 1))
            with self.assertRaises(evidence.EvidenceError):
                evidence.read_key_value_file(path, allowed_keys=evidence.BACKUP_MANIFEST_KEYS)

    def test_manifest_rejects_unknown_keys_without_echoing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "manifest"
            path.write_text("contract=weltgewebe-postgres-backup-v1\nUNEXPECTED_FIELD=do-not-echo\n", encoding="utf-8")
            with self.assertRaises(evidence.EvidenceError) as caught:
                evidence.read_key_value_file(path, allowed_keys=evidence.BACKUP_MANIFEST_KEYS)
            self.assertNotIn("do-not-echo", str(caught.exception))

    def test_invalid_hostname_and_nonpositive_freshness_fail_closed(self) -> None:
        with self.assertRaises(evidence.EvidenceError):
            evidence.validate_hostname("https://user:secret@example.test/path", field="domain")
        with self.assertRaises(argparse.ArgumentTypeError):
            evidence.positive_hours("0")

    def test_compose_prefix_preserves_explicit_deployment_order(self) -> None:
        result = evidence.build_compose_prefix(
            docker_bin="docker",
            project_name="weltgewebe",
            env_file=Path("/etc/weltgewebe/weltgewebe.env"),
            compose_files=[Path("prod.yml"), Path("vps.yml")],
        )
        self.assertEqual(
            result,
            [
                "docker",
                "compose",
                "--env-file",
                "/etc/weltgewebe/weltgewebe.env",
                "-p",
                "weltgewebe",
                "-f",
                "prod.yml",
                "-f",
                "vps.yml",
            ],
        )


if __name__ == "__main__":
    unittest.main()

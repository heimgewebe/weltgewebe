from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_PATH = ROOT / "scripts/platform/validate_two_operator_pilot.py"
EXAMPLE_PATH = ROOT / "platform/cell-pilot/two-operator-pilot.example.invalid.json"
CONTRACT_PATH = ROOT / "platform/cell-pilot/two-operator-pilot.contract.json"
PROFILE_PATH = ROOT / "platform/cell-profile.contract.json"

spec = importlib.util.spec_from_file_location(
    "two_operator_pilot_validator", VALIDATOR_PATH
)
assert spec and spec.loader
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def _digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def _replace_redacted(value: Any, path: str = "document") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if child == "REDACTED":
                value[key] = _digest(child_path)
            else:
                _replace_redacted(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _replace_redacted(child, f"{path}[{index}]")


def activation_document() -> dict[str, Any]:
    document = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))
    document["document_mode"] = "activation"
    _replace_redacted(document)
    commit = _digest("synthetic-activation-release")[:40]
    api_digest = "sha256:" + _digest("synthetic-api-image")
    web_digest = "sha256:" + _digest("synthetic-web-image")
    activation = document["activation"]
    activation.update(
        {
            "approved": True,
            "approved_by": ["operator-a", "operator-b"],
            "contract_sha256": hashlib.sha256(CONTRACT_PATH.read_bytes()).hexdigest(),
            "source_commit": commit,
        }
    )
    replacements = (
        (
            document["cells"][0],
            "cell-a.operator-a.net",
            "operator-a.net",
            "cell-b.operator-b.net",
            "https://cell-b.operator-b.net",
            "s3://operator-a-backups.net/gewebezelle-a",
        ),
        (
            document["cells"][1],
            "cell-b.operator-b.net",
            "operator-b.net",
            "cell-a.operator-a.net",
            "https://cell-a.operator-a.net",
            "s3://operator-b-backups.net/gewebezelle-b",
        ),
    )
    for cell, cell_id, control_domain, peer_id, peer_url, backup_target in replacements:
        cell["cell_id"] = cell_id
        cell["public_base_url"] = f"https://{cell_id}"
        cell["operator"]["control_domain"] = control_domain
        cell["operator"]["primary_contact"] = f"ops@{control_domain}"
        cell["peer"]["cell_id"] = peer_id
        cell["peer"]["delivery_base_url"] = peer_url
        cell["egress"]["fqdn"] = peer_id
        cell["deployment"].update(
            {
                "source_commit": commit,
                "api_image_digest": api_digest,
                "web_image_digest": web_digest,
            }
        )
        cell["backup_restore"]["target_uri"] = backup_target
        cell["backup_restore"]["restore_source_commit"] = commit
    return document


class TwoOperatorCellPilotTests(unittest.TestCase):
    def setUp(self) -> None:
        self.example = json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))

    def assert_rejected(
        self,
        mutator: Callable[[dict[str, Any]], None],
        code: str,
    ) -> None:
        document = activation_document()
        mutator(document)
        with self.assertRaisesRegex(validator.PilotContractError, rf"^{code}:"):
            validator.validate_document(document, "activation")

    def test_redacted_example_is_valid_but_never_activatable(self) -> None:
        result = validator.validate_document(copy.deepcopy(self.example), "example")
        self.assertEqual(result["status"], "pass")
        self.assertFalse(result["activatable"])
        self.assertEqual(result["document_mode"], "example")
        self.assertTrue(result["structurally_valid"])
        self.assertFalse(result["external_receipt_verification_required"])

    def test_redacted_example_cannot_be_validated_as_activation(self) -> None:
        with self.assertRaisesRegex(validator.PilotContractError, r"^mode-mismatch:"):
            validator.validate_document(copy.deepcopy(self.example), "activation")

    def test_complete_synthetic_activation_contract_passes_without_network(
        self,
    ) -> None:
        document = activation_document()
        before = copy.deepcopy(document)
        with (
            mock.patch.object(
                socket, "socket", side_effect=AssertionError("network forbidden")
            ),
            mock.patch.object(
                socket, "getaddrinfo", side_effect=AssertionError("DNS forbidden")
            ),
        ):
            result = validator.validate_document(document, "activation")
        self.assertEqual(document, before)
        self.assertTrue(result["structurally_valid"])
        self.assertFalse(result["activatable"])
        self.assertTrue(result["external_receipt_verification_required"])
        self.assertTrue(result["authoritative_replay_ledger_required"])
        self.assertEqual(result["operator_ids"], ["operator-a", "operator-b"])

    def test_duplicate_json_keys_are_rejected_before_validation(self) -> None:
        source = EXAMPLE_PATH.read_text(encoding="utf-8")
        duplicate = source.replace(
            '"schema_version": 1,',
            '"schema_version": 1,\n  "schema_version": 1,',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicate.json"
            path.write_text(duplicate, encoding="utf-8")
            with self.assertRaisesRegex(
                validator.PilotContractError, r"^duplicate-key:"
            ):
                validator.validate_path(path, "example")

    def test_schema_version_requires_json_integer(self) -> None:
        for value in (True, 1.0):
            with self.subTest(value=value):
                document = activation_document()
                document["schema_version"] = value
                with self.assertRaisesRegex(
                    validator.PilotContractError, r"^document-version:"
                ):
                    validator.validate_document(document, "activation")

    def test_non_finite_json_numbers_are_rejected(self) -> None:
        source = EXAMPLE_PATH.read_text(encoding="utf-8").replace(
            '"slo_availability_percent": 99.0',
            '"slo_availability_percent": NaN',
            1,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non-finite.json"
            path.write_text(source, encoding="utf-8")
            with self.assertRaisesRegex(
                validator.PilotContractError, r"^invalid-json:"
            ):
                validator.validate_path(path, "example")

    def test_contract_and_profile_are_exactly_digest_bound(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            contract_path = root / "contract.json"
            profile_path = root / "profile.json"
            profile_path.write_bytes(PROFILE_PATH.read_bytes())
            contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
            contract["network_contract"]["port"] = 8443
            contract_path.write_text(json.dumps(contract), encoding="utf-8")
            with (
                mock.patch.object(validator, "CONTRACT_PATH", contract_path),
                mock.patch.object(validator, "PROFILE_PATH", profile_path),
                self.assertRaisesRegex(
                    validator.PilotContractError, r"^contract-drift:"
                ),
            ):
                validator.validate_document(activation_document(), "activation")

            contract_path.write_bytes(CONTRACT_PATH.read_bytes())
            profile_path.write_bytes(PROFILE_PATH.read_bytes() + b"\n")
            with (
                mock.patch.object(validator, "CONTRACT_PATH", contract_path),
                mock.patch.object(validator, "PROFILE_PATH", profile_path),
                self.assertRaisesRegex(
                    validator.PilotContractError, r"^contract-drift:"
                ),
            ):
                validator.validate_document(activation_document(), "activation")

    def test_public_endpoint_and_contact_are_bound_to_control_domain(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0].update(
                {
                    "cell_id": "cell-a.uncontrolled.net",
                    "public_base_url": "https://cell-a.uncontrolled.net",
                }
            ),
            "control-domain-mismatch",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["operator"].update(
                {"primary_contact": "ops team@operator-a.net"}
            ),
            "contact-control-mismatch",
        )

    def test_example_mode_requires_reserved_invalid_hosts(self) -> None:
        document = copy.deepcopy(self.example)
        document["cells"][0].update(
            {
                "cell_id": "cell-a.operator-a.example",
                "public_base_url": "https://cell-a.operator-a.example",
            }
        )
        with self.assertRaisesRegex(validator.PilotContractError, r"^example-host:"):
            validator.validate_document(document, "example")

    def test_obvious_hash_placeholders_are_rejected(self) -> None:
        self.assert_rejected(
            lambda d: (
                d["activation"].update({"source_commit": "a" * 40}),
                d["cells"][0]["deployment"].update({"source_commit": "a" * 40}),
                d["cells"][1]["deployment"].update({"source_commit": "a" * 40}),
                d["cells"][0]["backup_restore"].update(
                    {"restore_source_commit": "a" * 40}
                ),
                d["cells"][1]["backup_restore"].update(
                    {"restore_source_commit": "a" * 40}
                ),
            ),
            "placeholder-digest",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["evidence"].update(
                {"applied_receipt_sha256": "f" * 64}
            ),
            "placeholder-digest",
        )

    def test_timestamps_require_canonical_utc_seconds(self) -> None:
        for value in (
            "2030-01-01T02:00:00.000Z",
            "2030-01-01T02:00Z",
            "2030-01-01T02:00:00+00:00",
        ):
            with self.subTest(value=value):
                self.assert_rejected(
                    lambda d, value=value: d["activation"].update(
                        {"generated_at": value}
                    ),
                    "invalid-timestamp",
                )

    def test_identity_and_operator_independence_is_fail_closed(self) -> None:
        cases = {
            "same cell id": lambda d: (
                d["cells"][1].update(
                    {
                        "cell_id": d["cells"][0]["cell_id"],
                        "public_base_url": d["cells"][0]["public_base_url"],
                    }
                ),
                d["cells"][1]["operator"].update(
                    {
                        "control_domain": "operator-a.net",
                        "primary_contact": "ops-b@operator-a.net",
                    }
                ),
            ),
            "same operator id": lambda d: (
                d["cells"][1]["operator"].update(
                    {"operator_id": d["cells"][0]["operator"]["operator_id"]}
                ),
                d["cells"][1]["dns_tls"].update(
                    {"dns_owner": "operator-a", "tls_owner": "operator-a"}
                ),
                d["cells"][1]["backup_restore"].update({"owner": "operator-a"}),
                d["cells"][1]["operations"].update({"alert_owner": "operator-a"}),
            ),
            "same accountable party": lambda d: d["cells"][1]["operator"].update(
                {"accountable_party": d["cells"][0]["operator"]["accountable_party"]}
            ),
            "same control domain": lambda d: (
                d["cells"][1].update(
                    {
                        "cell_id": "cell-b.operator-a.net",
                        "public_base_url": "https://cell-b.operator-a.net",
                    }
                ),
                d["cells"][1]["operator"].update(
                    {
                        "control_domain": "operator-a.net",
                        "primary_contact": "ops-b@operator-a.net",
                    }
                ),
            ),
            "same key id": lambda d: d["cells"][1]["identity"].update(
                {"active_key_id": d["cells"][0]["identity"]["active_key_id"]}
            ),
            "same public key": lambda d: d["cells"][1]["identity"].update(
                {
                    "active_public_key": d["cells"][0]["identity"]["active_public_key"],
                    "public_key_sha256": d["cells"][0]["identity"]["public_key_sha256"],
                }
            ),
            "same backup target": lambda d: d["cells"][1]["backup_restore"].update(
                {"target_uri": d["cells"][0]["backup_restore"]["target_uri"]}
            ),
            "same backup authority": lambda d: d["cells"][1]["backup_restore"].update(
                {"target_uri": "gs://operator-a-backups.net/gewebezelle-b"}
            ),
        }
        for name, mutator in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, "operator-independence")

    def test_peer_binding_must_be_exact_and_symmetric(self) -> None:
        cases = {
            "wrong cell": lambda d: d["cells"][0]["peer"].update(
                {"cell_id": "third.operator-c.net"}
            ),
            "wrong url": lambda d: (
                d["cells"][0]["peer"].update(
                    {"delivery_base_url": "https://third.operator-c.net"}
                ),
                d["cells"][0]["egress"].update({"fqdn": "third.operator-c.net"}),
            ),
            "wrong key id": lambda d: d["cells"][0]["peer"].update(
                {"expected_key_id": "key-c-2030-01"}
            ),
            "wrong public key": lambda d: d["cells"][0]["peer"].update(
                {"expected_public_key": d["cells"][0]["identity"]["active_public_key"]}
            ),
        }
        for name, mutator in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, "asymmetric-peer")

    def test_event_allowlist_is_exact(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0]["peer"].update(
                {"allowed_event_types": ["object.upserted"]}
            ),
            "event-allowlist",
        )

    def test_egress_must_match_peer_and_forbid_broad_targets(self) -> None:
        cases = {
            "host drift": (
                lambda d: d["cells"][0]["egress"].update(
                    {"fqdn": "third.operator-c.net"}
                ),
                "egress-peer-mismatch",
            ),
            "wildcard": (
                lambda d: d["cells"][0]["egress"].update({"wildcards": ["*.net"]}),
                "broad-egress",
            ),
            "world": (
                lambda d: d["cells"][0]["egress"].update({"to_entities": ["world"]}),
                "broad-egress",
            ),
            "cidr": (
                lambda d: d["cells"][0]["egress"].update({"to_cidrs": ["0.0.0.0/0"]}),
                "broad-egress",
            ),
            "wrong port": (
                lambda d: d["cells"][0]["egress"].update({"port": 8443}),
                "egress-contract",
            ),
        }
        for name, (mutator, code) in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, code)

    def test_legacy_ipv4_literals_are_rejected_without_dns(self) -> None:
        for host in ("127.1", "0177.1", "0x7f.1", "2130706433"):
            with self.subTest(host=host):
                with self.assertRaisesRegex(
                    validator.PilotContractError, r"^ip-literal:"
                ):
                    validator._hostname(host, "test.host", activation=True)

    def test_invalid_url_errors_do_not_echo_secret_port_text(self) -> None:
        sentinel = "TOPSECRET"
        for function, value in (
            (validator._https_base_url, f"https://cell.example:{sentinel}"),
            (validator._backup_target, f"s3://backup.example:{sentinel}/prefix"),
        ):
            with self.subTest(function=function.__name__):
                try:
                    function(value, "test.url", activation=True)
                except validator.PilotContractError as error:
                    self.assertNotIn(sentinel, str(error))
                else:
                    self.fail("invalid port text must fail")

    def test_endpoint_urls_reject_unsafe_forms(self) -> None:
        cases = {
            "http": "http://cell-b.operator-b.net",
            "credentials": "https://user:pass@cell-b.operator-b.net",
            "query": "https://cell-b.operator-b.net?x=1",
            "fragment": "https://cell-b.operator-b.net#x",
            "path": "https://cell-b.operator-b.net/federation",
            "ip": "https://192.0.2.10",
            "custom port": "https://cell-b.operator-b.net:8443",
        }
        for name, url in cases.items():
            with self.subTest(name=name):
                document = activation_document()
                document["cells"][0]["peer"]["delivery_base_url"] = url
                with self.assertRaises(validator.PilotContractError):
                    validator.validate_document(document, "activation")

    def test_backup_targets_are_canonical_and_authority_separated(self) -> None:
        cases = {
            "custom port": "s3://operator-a-backups.net:443/gewebezelle-a",
            "escaped traversal": "s3://operator-a-backups.net/%2e%2e/gewebezelle-a",
            "dot segment": "s3://operator-a-backups.net/../gewebezelle-a",
            "empty segment": "s3://operator-a-backups.net/gewebezelle-a//copy",
            "trailing slash": "s3://operator-a-backups.net/gewebezelle-a/",
            "uppercase authority": "s3://OPERATOR-A-BACKUPS.NET/gewebezelle-a",
        }
        for name, target in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(
                    lambda d, target=target: d["cells"][0]["backup_restore"].update(
                        {"target_uri": target}
                    ),
                    "invalid-backup-target",
                )

    def test_backup_authority_cannot_reuse_cell_or_control_host(self) -> None:
        for target in (
            "s3://cell-a.operator-a.net/backup",
            "s3://operator-a.net/backup",
            "s3://cell-b.operator-b.net/backup",
        ):
            with self.subTest(target=target):
                self.assert_rejected(
                    lambda d, target=target: d["cells"][0]["backup_restore"].update(
                        {"target_uri": target}
                    ),
                    "backup-authority-collision",
                )

    def test_reserved_example_domains_are_rejected_for_activation(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0].update(
                {
                    "cell_id": "cell-a.operator-a.invalid",
                    "public_base_url": "https://cell-a.operator-a.invalid",
                }
            ),
            "reserved-host",
        )

    def test_release_binding_cannot_drift(self) -> None:
        cases = {
            "cell commit": lambda d: (
                d["cells"][1]["deployment"].update(
                    {"source_commit": _digest("drifted-cell-commit")[:40]}
                ),
                d["cells"][1]["backup_restore"].update(
                    {"restore_source_commit": _digest("drifted-cell-commit")[:40]}
                ),
            ),
            "api digest": lambda d: d["cells"][1]["deployment"].update(
                {"api_image_digest": "sha256:" + _digest("drifted-api-image")}
            ),
            "web digest": lambda d: d["cells"][1]["deployment"].update(
                {"web_image_digest": "sha256:" + _digest("drifted-web-image")}
            ),
        }
        for name, mutator in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, "release-drift")
        self.assert_rejected(
            lambda d: d["activation"].update(
                {"source_commit": _digest("drifted-activation-commit")[:40]}
            ),
            "activation-release-mismatch",
        )

    def test_contract_digest_and_joint_approval_are_bound(self) -> None:
        self.assert_rejected(
            lambda d: d["activation"].update({"contract_sha256": "0" * 64}),
            "contract-digest-mismatch",
        )
        self.assert_rejected(
            lambda d: d["activation"].update({"approved": False}),
            "not-approved",
        )
        self.assert_rejected(
            lambda d: d["activation"].update({"approved_by": ["operator-a"]}),
            "joint-approval",
        )

    def test_alerts_and_change_windows_are_independent_and_staggered(self) -> None:
        cases = {
            "shared alert route": (
                lambda d: d["cells"][1]["operations"].update(
                    {"alert_route_id": d["cells"][0]["operations"]["alert_route_id"]}
                ),
                "operator-independence",
            ),
            "late alarm": (
                lambda d: d["cells"][0]["operations"].update(
                    {"delivery_lag_alarm_seconds": 900}
                ),
                "late-alert",
            ),
            "missing burn alarm": (
                lambda d: d["cells"][0]["operations"].update(
                    {"availability_burn_alarm": False}
                ),
                "missing-burn-alarm",
            ),
            "overlapping rollback window": (
                lambda d: d["cells"][1]["operations"].update(
                    {
                        "upgrade_window": {
                            "start": "2030-01-02T02:30:00Z",
                            "end": "2030-01-02T03:30:00Z",
                        },
                        "rollback_deadline": "2030-01-02T04:30:00Z",
                    }
                ),
                "overlapping-change-windows",
            ),
        }
        for name, (mutator, code) in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, code)

    def test_activation_timeline_is_ordered(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0]["backup_restore"].update(
                {"restored_at": "2030-01-01T03:00:00Z"}
            ),
            "restore-after-activation",
        )
        self.assert_rejected(
            lambda d: d["activation"].update({"generated_at": "2030-01-02T01:00:00Z"}),
            "activation-after-change-window",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["backup_restore"].update(
                {"restored_at": d["activation"]["generated_at"]}
            ),
            "restore-after-activation",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["operations"].update(
                {
                    "rollback_deadline": d["cells"][1]["operations"]["upgrade_window"][
                        "start"
                    ]
                }
            ),
            "overlapping-change-windows",
        )

    def test_recovery_and_verification_receipts_are_not_shared(self) -> None:
        cases = {
            "shared restore receipt": lambda d: d["cells"][1]["backup_restore"].update(
                {
                    "restore_receipt_sha256": d["cells"][0]["backup_restore"][
                        "restore_receipt_sha256"
                    ]
                }
            ),
            "same local backup and restore receipt": lambda d: d["cells"][0][
                "backup_restore"
            ].update(
                {
                    "restore_receipt_sha256": d["cells"][0]["backup_restore"][
                        "backup_receipt_sha256"
                    ]
                }
            ),
            "shared peer verification receipt": lambda d: d["cells"][1][
                "verification"
            ].update(
                {
                    "peer_receipt_sha256": d["cells"][0]["verification"][
                        "peer_receipt_sha256"
                    ]
                }
            ),
            "shared mutual proof": lambda d: d["mutual_proofs"].update(
                {"b_to_a_receipt_sha256": d["mutual_proofs"]["a_to_b_receipt_sha256"]}
            ),
            "reused local evidence": lambda d: d["cells"][0]["evidence"].update(
                {
                    "duplicate_receipt_sha256": d["cells"][0]["evidence"][
                        "applied_receipt_sha256"
                    ]
                }
            ),
            "approval reuses mutual proof": lambda d: d["activation"].update(
                {"approval_receipt_sha256": d["mutual_proofs"]["a_to_b_receipt_sha256"]}
            ),
        }
        for name, mutator in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, "shared-evidence")

    def test_restore_rollback_and_evidence_are_required(self) -> None:
        cases = {
            "missing restore receipt": lambda d: d["cells"][0]["backup_restore"].update(
                {"restore_receipt_sha256": "REDACTED"}
            ),
            "wrong restore commit": lambda d: d["cells"][0]["backup_restore"].update(
                {"restore_source_commit": _digest("drifted-cell-commit")[:40]}
            ),
            "missing rollback proof": lambda d: d["cells"][0]["evidence"].update(
                {"rollback_receipt_sha256": "REDACTED"}
            ),
        }
        expected = {
            "missing restore receipt": "missing-evidence",
            "wrong restore commit": "restore-release-mismatch",
            "missing rollback proof": "missing-evidence",
        }
        for name, mutator in cases.items():
            with self.subTest(name=name):
                self.assert_rejected(mutator, expected[name])
        self.assert_rejected(
            lambda d: d["cells"][0]["operations"].update(
                {"rollback_deadline": "2030-01-02T01:30:00Z"}
            ),
            "invalid-rollback-window",
        )

    def test_independent_verification_cannot_be_self_asserted(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0]["verification"].update(
                {"verified_by_operator_id": "operator-a"}
            ),
            "self-verification",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["verification"].update({"channel": "email"}),
            "verification-channel",
        )

    def test_private_or_secret_material_is_rejected_anywhere(self) -> None:
        self.assert_rejected(
            lambda d: d["cells"][0]["identity"].update(
                {"private_key": "must-never-appear"}
            ),
            "secret-material",
        )
        self.assert_rejected(
            lambda d: d["cells"][0]["operator"].update(
                {"accountable_party": "-----BEGIN PRIVATE KEY-----\nforbidden"}
            ),
            "secret-material",
        )

    def test_example_must_keep_all_evidence_redacted(self) -> None:
        document = copy.deepcopy(self.example)
        document["mutual_proofs"]["a_to_b_receipt_sha256"] = "1" * 64
        with self.assertRaisesRegex(
            validator.PilotContractError, r"^example-evidence:"
        ):
            validator.validate_document(document, "example")

    def test_cli_output_is_deterministic_and_activation_attempt_fails(self) -> None:
        command = [
            sys.executable,
            str(VALIDATOR_PATH),
            "--mode",
            "example",
            str(EXAMPLE_PATH),
        ]
        first = subprocess.run(
            command, cwd=ROOT, check=True, capture_output=True, text=True
        )
        second = subprocess.run(
            command, cwd=ROOT, check=True, capture_output=True, text=True
        )
        self.assertEqual(first.stdout, second.stdout)
        self.assertFalse(json.loads(first.stdout)["activatable"])

        rejected = subprocess.run(
            [
                sys.executable,
                str(VALIDATOR_PATH),
                "--mode",
                "activation",
                str(EXAMPLE_PATH),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("invalid-example-file", rejected.stderr)


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import ipaddress
import json
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "platform/cell-pilot/two-operator-pilot.contract.json"
PROFILE_PATH = ROOT / "platform/cell-profile.contract.json"
EXAMPLE_PATH = ROOT / "platform/cell-pilot/two-operator-pilot.example.invalid.json"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,62}[a-z0-9]$")
KEY_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
EMAIL_LOCAL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+$")
BACKUP_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")
UTC_TIMESTAMP = re.compile(
    r"^[0-9]{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])"
    r"T(?:[01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$"
)
RESERVED_SUFFIXES = (".invalid", ".example", ".test", ".localhost")
FORBIDDEN_KEY_MARKERS = (
    "private_key",
    "signing_key",
    "password",
    "secret_value",
    "access_token",
    "bearer_token",
    "credential",
)
FORBIDDEN_VALUE_MARKERS = (
    "-----begin private key-----",
    "-----begin encrypted private key-----",
    "-----begin openssh private key-----",
    "federation_signing_key_b64=",
    "aws_secret_access_key=",
)

ROOT_KEYS = {
    "schema_version",
    "contract_id",
    "document_mode",
    "activation",
    "cells",
    "mutual_proofs",
    "nonclaims",
}
ACTIVATION_KEYS = {
    "approved",
    "approved_by",
    "approval_receipt_sha256",
    "contract_sha256",
    "source_commit",
    "generated_at",
}
CELL_KEYS = {
    "cell_id",
    "public_base_url",
    "operator",
    "identity",
    "peer",
    "egress",
    "deployment",
    "dns_tls",
    "backup_restore",
    "operations",
    "verification",
    "evidence",
}
OPERATOR_KEYS = {
    "operator_id",
    "accountable_party",
    "primary_contact",
    "control_domain",
    "independence_receipt_sha256",
}
IDENTITY_KEYS = {"active_key_id", "active_public_key", "public_key_sha256"}
PEER_KEYS = {
    "cell_id",
    "delivery_base_url",
    "expected_key_id",
    "expected_public_key",
    "state",
    "allow_neighbourhood",
    "allowed_event_types",
}
EGRESS_KEYS = {
    "policy_kind",
    "fqdn",
    "port",
    "protocol",
    "to_entities",
    "to_cidrs",
    "wildcards",
}
DEPLOYMENT_KEYS = {"source_commit", "api_image_digest", "web_image_digest"}
DNS_TLS_KEYS = {
    "dns_owner",
    "tls_owner",
    "dns_receipt_sha256",
    "tls_receipt_sha256",
}
BACKUP_KEYS = {
    "target_uri",
    "owner",
    "backup_receipt_sha256",
    "restore_receipt_sha256",
    "restore_source_commit",
    "restored_at",
    "measured_rpo_seconds",
    "measured_rto_seconds",
}
OPERATIONS_KEYS = {
    "slo_availability_percent",
    "alert_owner",
    "alert_route_id",
    "delivery_lag_slo_seconds",
    "delivery_lag_alarm_seconds",
    "availability_burn_alarm",
    "on_call_receipt_sha256",
    "upgrade_window",
    "rollback_deadline",
    "upgrade_receipt_sha256",
    "rollback_receipt_sha256",
}
WINDOW_KEYS = {"start", "end"}
VERIFICATION_KEYS = {
    "verified_by_operator_id",
    "channel",
    "identity_receipt_sha256",
    "peer_receipt_sha256",
}
MUTUAL_PROOF_KEYS = {
    "a_to_b_receipt_sha256",
    "b_to_a_receipt_sha256",
    "out_of_band_pairing_receipt_sha256",
}


class PilotContractError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def _fail(code: str, message: str) -> None:
    raise PilotContractError(code, message)


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            _fail("duplicate-key", f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    _fail("invalid-json", f"non-finite JSON number {value!r} is forbidden")


def _loads_strict(source: str | bytes, path: str) -> Any:
    try:
        return json.loads(
            source,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as error:
        _fail("invalid-json", f"{path}: {error}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail("invalid-type", f"{path} must be an object")
    return value


def _exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    obj = _object(value, path)
    observed = set(obj)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        _fail("invalid-keys", f"{path} missing={missing} extra={extra}")
    return obj


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        _fail("invalid-string", f"{path} must be a non-empty trimmed string")
    return value


def _scan_forbidden_keys(value: Any, path: str = "document") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = str(key).lower()
            if any(marker in lowered for marker in FORBIDDEN_KEY_MARKERS):
                _fail("secret-material", f"{path}.{key} is forbidden")
            _scan_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _scan_forbidden_keys(child, f"{path}[{index}]")
    elif isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in FORBIDDEN_VALUE_MARKERS):
            _fail("secret-material", f"{path} contains forbidden private material")


def _timestamp(value: Any, path: str) -> datetime:
    source = _string(value, path)
    if not UTC_TIMESTAMP.fullmatch(source):
        _fail("invalid-timestamp", f"{path} must use RFC3339 seconds in UTC Z form")
    try:
        parsed = datetime.fromisoformat(source[:-1] + "+00:00")
    except ValueError as error:
        _fail("invalid-timestamp", f"{path}: {error}")
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail("invalid-timestamp", f"{path} must be UTC")
    return parsed


def _key_id(value: Any, path: str) -> str:
    source = _string(value, path)
    if not KEY_ID.fullmatch(source):
        _fail(
            "invalid-key-id",
            f"{path} must be 1..64 characters from [A-Za-z0-9._-]",
        )
    return source


def _hostname(value: Any, path: str, *, activation: bool) -> str:
    host = _string(value, path)
    if host != host.lower() or host.endswith(".") or "*" in host:
        _fail("invalid-host", f"{path} must be a lowercase exact DNS name")
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        try:
            socket.inet_aton(host)
        except OSError:
            pass
        else:
            _fail("ip-literal", f"{path} must not use a legacy IPv4 literal")
    else:
        _fail("ip-literal", f"{path} must not be an IP literal")
    if not host.isascii():
        _fail("invalid-host", f"{path} must use ASCII DNS labels")
    if len(host.encode("ascii")) > 253:
        _fail("invalid-host", f"{path} exceeds the DNS name length limit")
    labels = host.split(".")
    if len(labels) < 2 or any(not DNS_LABEL.fullmatch(label) for label in labels):
        _fail("invalid-host", f"{path} is not a valid DNS name")
    if activation and host.endswith(RESERVED_SUFFIXES):
        _fail("reserved-host", f"{path} uses a reserved non-production suffix")
    if not activation and not host.endswith(".invalid"):
        _fail("example-host", f"{path} must use the reserved .invalid suffix")
    return host


def _cell_id(value: Any, path: str, *, activation: bool) -> str:
    cell_id = _hostname(value, path, activation=activation)
    if len(cell_id) > 64:
        _fail("invalid-cell-id", f"{path} exceeds the 64-character limit")
    return cell_id


def _https_base_url(value: Any, path: str, *, activation: bool) -> tuple[str, str]:
    source = _string(value, path)
    try:
        parsed = urlsplit(source)
        port = parsed.port
    except ValueError:
        _fail("invalid-url", f"{path} is invalid")
    if parsed.scheme != "https" or parsed.username or parsed.password:
        _fail("invalid-url", f"{path} must be credential-free HTTPS")
    if parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        _fail("invalid-url", f"{path} must not contain path, query or fragment")
    if port not in (None, 443):
        _fail("invalid-port", f"{path} must use TCP 443")
    if not parsed.hostname:
        _fail("invalid-url", f"{path} lacks a host")
    host = _hostname(parsed.hostname, f"{path}.host", activation=activation)
    canonical = f"https://{host}"
    if source != canonical:
        _fail("noncanonical-url", f"{path} must equal {canonical}")
    return canonical, host


def _reject_placeholder_hex(source: str, path: str) -> None:
    if len(set(source)) == 1:
        _fail(
            "placeholder-digest", f"{path} is an obvious repeated-character placeholder"
        )


def _commit(value: Any, path: str, *, activation: bool) -> str:
    source = _string(value, path)
    if not activation and source == "REDACTED":
        return source
    if not HEX40.fullmatch(source):
        _fail("invalid-commit", f"{path} must be a lowercase 40-hex Git commit")
    _reject_placeholder_hex(source, path)
    return source


def _image_digest(value: Any, path: str, *, activation: bool) -> str:
    source = _string(value, path)
    if not activation and source == "REDACTED":
        return source
    if not IMAGE_DIGEST.fullmatch(source):
        _fail("invalid-image-digest", f"{path} must be sha256:<64 lowercase hex>")
    _reject_placeholder_hex(source.removeprefix("sha256:"), path)
    return source


def _receipt(value: Any, path: str, *, activation: bool) -> str:
    source = _string(value, path)
    if activation:
        if not HEX64.fullmatch(source):
            _fail("missing-evidence", f"{path} must be a concrete SHA-256 receipt")
        _reject_placeholder_hex(source, path)
    elif source != "REDACTED":
        _fail("example-evidence", f"{path} must stay REDACTED in the example")
    return source


def _public_key(value: Any, digest: Any, path: str) -> str:
    source = _string(value, path)
    if "=" in source or not re.fullmatch(r"[A-Za-z0-9_-]{43}", source):
        _fail("invalid-public-key", f"{path} must be unpadded base64url Ed25519")
    try:
        raw = base64.urlsafe_b64decode(source + "=")
    except (ValueError, binascii.Error) as error:
        _fail("invalid-public-key", f"{path}: {error}")
    if len(raw) != 32:
        _fail("invalid-public-key", f"{path} must decode to 32 bytes")
    observed = hashlib.sha256(raw).hexdigest()
    if digest != observed:
        _fail("public-key-digest-mismatch", f"{path} digest does not match")
    return source


def _backup_target(value: Any, path: str, *, activation: bool) -> tuple[str, str]:
    source = _string(value, path)
    try:
        parsed = urlsplit(source)
        port = parsed.port
    except ValueError:
        _fail("invalid-backup-target", f"{path} is invalid")
    if parsed.scheme not in {"s3", "gs", "az", "https"}:
        _fail("invalid-backup-target", f"{path} must use s3, gs, az or https")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        _fail(
            "invalid-backup-target", f"{path} must not embed credentials or parameters"
        )
    if port is not None:
        _fail("invalid-backup-target", f"{path} must not use a custom port")
    if not parsed.hostname or parsed.path in ("", "/"):
        _fail("invalid-backup-target", f"{path} must bind a host/bucket and prefix")
    host = _hostname(parsed.hostname, f"{path}.host", activation=activation)
    if parsed.netloc != host:
        _fail("invalid-backup-target", f"{path} must use a canonical DNS authority")
    segments = parsed.path.split("/")[1:]
    if (
        not segments
        or any(
            not BACKUP_SEGMENT.fullmatch(segment) or segment in {".", ".."}
            for segment in segments
        )
        or parsed.path.endswith("/")
        or "\\" in parsed.path
        or "%" in parsed.path
    ):
        _fail(
            "invalid-backup-target",
            f"{path} must use a canonical non-empty prefix without escapes",
        )
    canonical_prefix = f"{parsed.scheme}://{host}/"
    if not source.startswith(canonical_prefix):
        _fail("invalid-backup-target", f"{path} is not canonical")
    return source, host


def _contract() -> tuple[dict[str, Any], str]:
    raw = CONTRACT_PATH.read_bytes()
    profile_raw = PROFILE_PATH.read_bytes()
    contract = _loads_strict(raw, str(CONTRACT_PATH))
    expected_keys = {
        "schema_version",
        "contract_id",
        "profile_contract",
        "profile_contract_sha256",
        "required_cell_count",
        "document_modes",
        "release_binding",
        "identity_contract",
        "allowed_event_types",
        "verification_channels",
        "network_contract",
        "backup_contract",
        "operational_limits",
        "timestamp_contract",
        "operational_safety",
        "required_evidence_fields",
        "required_nonclaims",
    }
    _exact_keys(contract, expected_keys, "contract")
    if type(contract["schema_version"]) is not int:
        _fail("contract-version", "contract.schema_version must be integer 1")
    expected_values = {
        "schema_version": 1,
        "contract_id": "gewebezelle-two-operator-pilot-v1",
        "profile_contract": "platform/cell-profile.contract.json",
        "profile_contract_sha256": hashlib.sha256(profile_raw).hexdigest(),
        "required_cell_count": 2,
        "document_modes": {
            "example": {
                "structurally_validatable": True,
                "activatable_by_static_validator": False,
                "requires_reserved_invalid_domains": True,
                "requires_redacted_evidence": True,
            },
            "activation": {
                "structurally_validatable": True,
                "activatable_by_static_validator": False,
                "requires_joint_approval": True,
                "requires_real_dns_names": True,
                "requires_complete_evidence_digests": True,
                "requires_external_receipt_verification": True,
                "requires_authoritative_replay_ledger": True,
            },
        },
        "release_binding": {
            "same_source_commit_for_both_cells": True,
            "same_api_image_digest_for_both_cells": True,
            "same_web_image_digest_for_both_cells": True,
        },
        "identity_contract": {
            "algorithm": "Ed25519",
            "public_key_encoding": "base64url-unpadded",
            "public_key_bytes": 32,
            "private_material_forbidden": True,
        },
        "allowed_event_types": ["object.deleted", "object.upserted"],
        "verification_channels": [
            "independent-auditor",
            "in-person",
            "postal",
            "telephone",
        ],
        "network_contract": {
            "scheme": "https",
            "port": 443,
            "protocol": "TCP",
            "policy_kind": "CiliumNetworkPolicy",
            "exact_fqdn_only": True,
            "forbid_ip_literals": True,
            "forbid_wildcards": True,
            "forbid_world_entities": True,
            "forbid_cidrs": True,
        },
        "backup_contract": {
            "allowed_schemes": ["az", "gs", "https", "s3"],
            "canonical_dns_authority_only": True,
            "custom_ports_forbidden": True,
            "safe_prefix_segments_only": True,
            "separate_authorities": True,
            "authority_must_differ_from_cell_and_control_hosts": True,
        },
        "operational_limits": {
            "minimum_availability_percent": 95.0,
            "maximum_measured_rpo_seconds": 86400,
            "maximum_measured_rto_seconds": 86400,
            "maximum_delivery_lag_slo_seconds": 86400,
            "maximum_delivery_lag_alarm_seconds": 86400,
        },
        "timestamp_contract": {
            "format": "RFC3339-seconds-UTC-Z",
            "restore_not_after_activation": True,
            "activation_before_upgrade_windows": True,
        },
        "operational_safety": {
            "staggered_change_windows": True,
            "separate_alert_routes": True,
            "delivery_lag_alarm_precedes_slo": True,
            "availability_burn_alarm_required": True,
            "separate_recovery_receipts": True,
            "duplicate_json_keys_forbidden": True,
            "invalid_example_filename_blocks_activation": True,
            "separate_backup_authorities": True,
            "restore_precedes_activation_document": True,
            "activation_precedes_change_windows": True,
            "document_unique_receipts": True,
            "external_receipt_verification_required": True,
            "authoritative_replay_ledger_required": True,
        },
        "required_evidence_fields": [
            "applied_receipt_sha256",
            "duplicate_receipt_sha256",
            "retry_receipt_sha256",
            "concurrency_receipt_sha256",
            "egress_receipt_sha256",
            "backup_restore_receipt_sha256",
            "rollback_receipt_sha256",
        ],
        "required_nonclaims": [
            "production Kubernetes cutover",
            "self-service cell provisioning",
            "automatic peer discovery or trust",
            "multi-region high availability",
            "identity migration between cells",
            "public quarantine administration",
            "completed two-operator WAN pilot",
            "GewebeZelle operator or CRD",
            "static validator establishes activation readiness",
            "static receipt digests establish operator or failure-domain independence",
        ],
    }
    for field, expected in expected_values.items():
        if contract[field] != expected:
            _fail(
                "contract-drift",
                f"contract.{field} changed without a schema version bump",
            )
    return contract, hashlib.sha256(raw).hexdigest()


def _validate_cell(
    value: Any,
    index: int,
    *,
    activation: bool,
    contract: dict[str, Any],
) -> dict[str, Any]:
    path = f"cells[{index}]"
    cell = _exact_keys(value, CELL_KEYS, path)
    cell_id = _cell_id(cell["cell_id"], f"{path}.cell_id", activation=activation)
    public_url, public_host = _https_base_url(
        cell["public_base_url"], f"{path}.public_base_url", activation=activation
    )
    if cell_id != public_host:
        _fail("cell-url-mismatch", f"{path}.cell_id must equal the public URL host")

    operator = _exact_keys(cell["operator"], OPERATOR_KEYS, f"{path}.operator")
    operator_id = _string(operator["operator_id"], f"{path}.operator.operator_id")
    if not IDENTIFIER.fullmatch(operator_id):
        _fail("invalid-operator-id", f"{path}.operator.operator_id is invalid")
    accountable_party = _string(
        operator["accountable_party"], f"{path}.operator.accountable_party"
    )
    control_domain = _hostname(
        operator["control_domain"],
        f"{path}.operator.control_domain",
        activation=activation,
    )
    contact = _string(operator["primary_contact"], f"{path}.operator.primary_contact")
    if contact.count("@") != 1:
        _fail("invalid-contact", f"{path} contact must be a single email address")
    local_part, contact_domain = contact.rsplit("@", 1)
    if (
        not EMAIL_LOCAL.fullmatch(local_part)
        or local_part.startswith(".")
        or local_part.endswith(".")
        or ".." in local_part
        or contact_domain != contact_domain.lower()
        or contact_domain != control_domain
    ):
        _fail(
            "contact-control-mismatch",
            f"{path} contact must use a canonical address on control_domain",
        )
    if public_host != control_domain and not public_host.endswith(f".{control_domain}"):
        _fail(
            "control-domain-mismatch",
            f"{path}.public_base_url must be inside operator.control_domain",
        )
    _receipt(
        operator["independence_receipt_sha256"],
        f"{path}.operator.independence_receipt_sha256",
        activation=activation,
    )

    identity = _exact_keys(cell["identity"], IDENTITY_KEYS, f"{path}.identity")
    key_id = _key_id(
        identity["active_key_id"], f"{path}.identity.active_key_id"
    )
    key = _public_key(
        identity["active_public_key"],
        identity["public_key_sha256"],
        f"{path}.identity.active_public_key",
    )

    peer = _exact_keys(cell["peer"], PEER_KEYS, f"{path}.peer")
    peer_cell_id = _cell_id(
        peer["cell_id"], f"{path}.peer.cell_id", activation=activation
    )
    peer_url, peer_host = _https_base_url(
        peer["delivery_base_url"],
        f"{path}.peer.delivery_base_url",
        activation=activation,
    )
    expected_key_id = _string(peer["expected_key_id"], f"{path}.peer.expected_key_id")
    expected_public_key = _string(
        peer["expected_public_key"], f"{path}.peer.expected_public_key"
    )
    if peer["state"] != "trusted" or peer["allow_neighbourhood"] is not True:
        _fail(
            "peer-not-active",
            f"{path}.peer must be explicitly trusted and neighbourhood-enabled",
        )
    if peer["allowed_event_types"] != contract["allowed_event_types"]:
        _fail(
            "event-allowlist",
            f"{path}.peer allowed_event_types must equal the contract",
        )

    egress = _exact_keys(cell["egress"], EGRESS_KEYS, f"{path}.egress")
    egress_host = _hostname(
        egress["fqdn"], f"{path}.egress.fqdn", activation=activation
    )
    if (
        egress["policy_kind"] != "CiliumNetworkPolicy"
        or egress["port"] != 443
        or egress["protocol"] != "TCP"
    ):
        _fail("egress-contract", f"{path}.egress must be exact Cilium TCP/443")
    for field in ("to_entities", "to_cidrs", "wildcards"):
        if egress[field] != []:
            _fail("broad-egress", f"{path}.egress.{field} must be empty")
    if egress_host != peer_host:
        _fail(
            "egress-peer-mismatch",
            f"{path}.egress fqdn must equal delivery_base_url host",
        )

    deployment = _exact_keys(cell["deployment"], DEPLOYMENT_KEYS, f"{path}.deployment")
    source_commit = _commit(
        deployment["source_commit"],
        f"{path}.deployment.source_commit",
        activation=activation,
    )
    api_digest = _image_digest(
        deployment["api_image_digest"],
        f"{path}.deployment.api_image_digest",
        activation=activation,
    )
    web_digest = _image_digest(
        deployment["web_image_digest"],
        f"{path}.deployment.web_image_digest",
        activation=activation,
    )

    dns_tls = _exact_keys(cell["dns_tls"], DNS_TLS_KEYS, f"{path}.dns_tls")
    if dns_tls["dns_owner"] != operator_id or dns_tls["tls_owner"] != operator_id:
        _fail("ownership-mismatch", f"{path}.dns_tls owners must equal operator_id")
    for field in ("dns_receipt_sha256", "tls_receipt_sha256"):
        _receipt(dns_tls[field], f"{path}.dns_tls.{field}", activation=activation)

    backup = _exact_keys(cell["backup_restore"], BACKUP_KEYS, f"{path}.backup_restore")
    backup_target, backup_authority = _backup_target(
        backup["target_uri"], f"{path}.backup_restore.target_uri", activation=activation
    )
    if backup["owner"] != operator_id:
        _fail(
            "ownership-mismatch", f"{path}.backup_restore.owner must equal operator_id"
        )
    for field in ("backup_receipt_sha256", "restore_receipt_sha256"):
        _receipt(backup[field], f"{path}.backup_restore.{field}", activation=activation)
    restore_commit = _commit(
        backup["restore_source_commit"],
        f"{path}.backup_restore.restore_source_commit",
        activation=activation,
    )
    restored_at = _timestamp(
        backup["restored_at"], f"{path}.backup_restore.restored_at"
    )
    for field in ("measured_rpo_seconds", "measured_rto_seconds"):
        number = backup[field]
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or not 0 <= number <= 86400
        ):
            _fail(
                "invalid-recovery-measurement",
                f"{path}.backup_restore.{field} must be 0..86400",
            )
    if restore_commit != source_commit:
        _fail(
            "restore-release-mismatch",
            f"{path} restore commit must equal deployment commit",
        )

    operations = _exact_keys(cell["operations"], OPERATIONS_KEYS, f"{path}.operations")
    slo = operations["slo_availability_percent"]
    if (
        isinstance(slo, bool)
        or not isinstance(slo, (int, float))
        or not 95 <= slo <= 100
    ):
        _fail(
            "invalid-slo", f"{path}.operations.slo_availability_percent must be 95..100"
        )
    if operations["alert_owner"] != operator_id:
        _fail(
            "ownership-mismatch",
            f"{path}.operations.alert_owner must equal operator_id",
        )
    alert_route_id = _string(
        operations["alert_route_id"], f"{path}.operations.alert_route_id"
    )
    if not IDENTIFIER.fullmatch(alert_route_id):
        _fail("invalid-alert-route", f"{path}.operations.alert_route_id is invalid")
    lag_slo = operations["delivery_lag_slo_seconds"]
    lag_alarm = operations["delivery_lag_alarm_seconds"]
    for field, number in (
        ("delivery_lag_slo_seconds", lag_slo),
        ("delivery_lag_alarm_seconds", lag_alarm),
    ):
        if (
            isinstance(number, bool)
            or not isinstance(number, int)
            or not 1 <= number <= 86400
        ):
            _fail(
                "invalid-alert-threshold", f"{path}.operations.{field} must be 1..86400"
            )
    if lag_alarm >= lag_slo:
        _fail("late-alert", f"{path} delivery lag alarm must precede the SLO threshold")
    if operations["availability_burn_alarm"] is not True:
        _fail(
            "missing-burn-alarm",
            f"{path}.operations.availability_burn_alarm must be true",
        )
    for field in (
        "on_call_receipt_sha256",
        "upgrade_receipt_sha256",
        "rollback_receipt_sha256",
    ):
        _receipt(operations[field], f"{path}.operations.{field}", activation=activation)
    window = _exact_keys(
        operations["upgrade_window"], WINDOW_KEYS, f"{path}.operations.upgrade_window"
    )
    start = _timestamp(window["start"], f"{path}.operations.upgrade_window.start")
    end = _timestamp(window["end"], f"{path}.operations.upgrade_window.end")
    rollback_deadline = _timestamp(
        operations["rollback_deadline"], f"{path}.operations.rollback_deadline"
    )
    if not start < end < rollback_deadline:
        _fail(
            "invalid-rollback-window",
            f"{path} requires start < end < rollback_deadline",
        )

    verification = _exact_keys(
        cell["verification"], VERIFICATION_KEYS, f"{path}.verification"
    )
    verified_by = _string(
        verification["verified_by_operator_id"],
        f"{path}.verification.verified_by_operator_id",
    )
    if verification["channel"] not in contract["verification_channels"]:
        _fail("verification-channel", f"{path}.verification.channel is not independent")
    for field in ("identity_receipt_sha256", "peer_receipt_sha256"):
        _receipt(
            verification[field], f"{path}.verification.{field}", activation=activation
        )

    evidence = _exact_keys(
        cell["evidence"], set(contract["required_evidence_fields"]), f"{path}.evidence"
    )
    for field in contract["required_evidence_fields"]:
        _receipt(evidence[field], f"{path}.evidence.{field}", activation=activation)

    receipts = {
        "operator.independence": operator["independence_receipt_sha256"],
        "dns_tls.dns": dns_tls["dns_receipt_sha256"],
        "dns_tls.tls": dns_tls["tls_receipt_sha256"],
        "backup_restore.backup": backup["backup_receipt_sha256"],
        "backup_restore.restore": backup["restore_receipt_sha256"],
        "operations.on_call": operations["on_call_receipt_sha256"],
        "operations.upgrade": operations["upgrade_receipt_sha256"],
        "operations.rollback": operations["rollback_receipt_sha256"],
        "verification.identity": verification["identity_receipt_sha256"],
        "verification.peer": verification["peer_receipt_sha256"],
    }
    receipts.update(
        {
            f"evidence.{field}": evidence[field]
            for field in contract["required_evidence_fields"]
        }
    )

    return {
        "cell_id": cell_id,
        "public_url": public_url,
        "public_host": public_host,
        "operator_id": operator_id,
        "accountable_party": accountable_party,
        "contact": contact,
        "control_domain": control_domain,
        "key_id": key_id,
        "public_key": key,
        "peer_cell_id": peer_cell_id,
        "peer_url": peer_url,
        "peer_expected_key_id": expected_key_id,
        "peer_expected_public_key": expected_public_key,
        "verified_by": verified_by,
        "backup_target": backup_target,
        "backup_authority": backup_authority,
        "receipts": receipts,
        "restored_at": restored_at,
        "alert_route_id": alert_route_id,
        "upgrade_start": start,
        "upgrade_end": end,
        "rollback_deadline": rollback_deadline,
        "source_commit": source_commit,
        "api_digest": api_digest,
        "web_digest": web_digest,
    }


def validate_document(document: dict[str, Any], expected_mode: str) -> dict[str, Any]:
    if expected_mode not in {"example", "activation"}:
        _fail("mode", "expected_mode must be example or activation")
    activation_mode = expected_mode == "activation"
    contract, contract_sha256 = _contract()
    _scan_forbidden_keys(document)
    root = _exact_keys(document, ROOT_KEYS, "document")
    if (
        type(root["schema_version"]) is not int
        or root["schema_version"] != 1
        or root["contract_id"] != contract["contract_id"]
    ):
        _fail("document-version", "document version or contract id mismatch")
    if root["document_mode"] != expected_mode:
        _fail("mode-mismatch", f"document_mode must be {expected_mode}")
    if root["nonclaims"] != contract["required_nonclaims"]:
        _fail(
            "nonclaims",
            "document must preserve every required nonclaim in canonical order",
        )

    activation = _exact_keys(root["activation"], ACTIVATION_KEYS, "activation")
    generated_at = _timestamp(activation["generated_at"], "activation.generated_at")
    source_commit = _commit(
        activation["source_commit"],
        "activation.source_commit",
        activation=activation_mode,
    )
    if activation_mode:
        if activation["approved"] is not True:
            _fail("not-approved", "activation.approved must be true")
        approval_receipt = _receipt(
            activation["approval_receipt_sha256"],
            "activation.approval_receipt_sha256",
            activation=True,
        )
        if activation["contract_sha256"] != contract_sha256:
            _fail("contract-digest-mismatch", "activation.contract_sha256 is stale")
    else:
        approval_receipt = "REDACTED"
        if activation["approved"] is not False or activation["approved_by"] != []:
            _fail("example-approved", "example must never be approved")
        for field in ("approval_receipt_sha256", "contract_sha256"):
            if activation[field] != "REDACTED":
                _fail("example-evidence", f"activation.{field} must stay REDACTED")

    cells = root["cells"]
    if not isinstance(cells, list) or len(cells) != contract["required_cell_count"]:
        _fail("cell-count", "document must contain exactly two cells")
    observed = [
        _validate_cell(cell, index, activation=activation_mode, contract=contract)
        for index, cell in enumerate(cells)
    ]

    unique_fields = (
        "cell_id",
        "public_url",
        "operator_id",
        "accountable_party",
        "contact",
        "control_domain",
        "key_id",
        "public_key",
        "backup_target",
        "backup_authority",
        "alert_route_id",
    )
    for field in unique_fields:
        values = [str(item[field]).casefold() for item in observed]
        if len(set(values)) != 2:
            _fail("operator-independence", f"cells must have different {field}")

    cell_and_control_hosts = {item["public_host"] for item in observed} | {
        item["control_domain"] for item in observed
    }
    for index, item in enumerate(observed):
        backup_host = item["backup_authority"]
        if backup_host in cell_and_control_hosts:
            _fail(
                "backup-authority-collision",
                f"cells[{index}] backup authority must differ from all cell and control hosts",
            )

    first, second = sorted(observed, key=lambda item: item["upgrade_start"])
    if activation_mode:
        for index, item in enumerate(observed):
            if item["restored_at"] >= generated_at:
                _fail(
                    "restore-after-activation",
                    f"cells[{index}] restore evidence must predate activation.generated_at",
                )
        if generated_at >= first["upgrade_start"]:
            _fail(
                "activation-after-change-window",
                "activation.generated_at must predate both upgrade windows",
            )
    if first["rollback_deadline"] >= second["upgrade_start"]:
        _fail(
            "overlapping-change-windows",
            "the first cell rollback window must close before the second cell upgrade starts",
        )

    for index, item in enumerate(observed):
        other = observed[1 - index]
        if (
            item["peer_cell_id"] != other["cell_id"]
            or item["peer_url"] != other["public_url"]
            or item["peer_expected_key_id"] != other["key_id"]
            or item["peer_expected_public_key"] != other["public_key"]
        ):
            _fail(
                "asymmetric-peer",
                f"cells[{index}] is not exactly bound to the other cell",
            )
        if item["verified_by"] != other["operator_id"]:
            _fail(
                "self-verification",
                f"cells[{index}] must be verified by the other operator",
            )

    for field in ("source_commit", "api_digest", "web_digest"):
        if observed[0][field] != observed[1][field]:
            _fail("release-drift", f"both cells must use the same {field}")
    if observed[0]["source_commit"] != source_commit:
        _fail(
            "activation-release-mismatch",
            "activation source_commit must bind both cells",
        )

    operator_ids = sorted(item["operator_id"] for item in observed)
    if activation_mode:
        if activation["approved_by"] != operator_ids:
            _fail(
                "joint-approval",
                "approved_by must contain both operator ids in sorted order",
            )
    elif activation["approved_by"] != []:
        _fail("example-approved", "example approved_by must be empty")

    mutual = _exact_keys(root["mutual_proofs"], MUTUAL_PROOF_KEYS, "mutual_proofs")
    mutual_receipts = {
        f"mutual_proofs.{field}": _receipt(
            mutual[field], f"mutual_proofs.{field}", activation=activation_mode
        )
        for field in sorted(MUTUAL_PROOF_KEYS)
    }

    if activation_mode:
        named_receipts = {"activation.approval": approval_receipt}
        for index, item in enumerate(observed):
            for name, receipt in item["receipts"].items():
                named_receipts[f"cells[{index}].{name}"] = receipt
        named_receipts.update(mutual_receipts)
        receipt_owners: dict[str, str] = {}
        for name, receipt in named_receipts.items():
            previous = receipt_owners.get(receipt)
            if previous is not None:
                _fail(
                    "shared-evidence",
                    f"{name} reuses the receipt already bound by {previous}",
                )
            receipt_owners[receipt] = name

    return {
        "status": "pass",
        "contract_id": contract["contract_id"],
        "contract_sha256": contract_sha256,
        "document_mode": expected_mode,
        "structurally_valid": True,
        "activatable": False,
        "external_receipt_verification_required": activation_mode,
        "authoritative_replay_ledger_required": activation_mode,
        "cell_ids": [item["cell_id"] for item in observed],
        "operator_ids": operator_ids,
    }


def validate_path(path: Path, expected_mode: str) -> dict[str, Any]:
    if expected_mode == "activation" and path.name.endswith(".invalid.json"):
        _fail("invalid-example-file", "an .invalid.json example can never be activated")
    document = _loads_strict(path.read_text(encoding="utf-8"), str(path))
    if not isinstance(document, dict):
        _fail("invalid-type", "document root must be an object")
    return validate_document(document, expected_mode)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("document", nargs="?", type=Path, default=EXAMPLE_PATH)
    parser.add_argument("--mode", choices=("example", "activation"), default="example")
    args = parser.parse_args()
    try:
        result = validate_path(args.document, args.mode)
    except (OSError, PilotContractError) as error:
        print(f"two-operator pilot contract failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

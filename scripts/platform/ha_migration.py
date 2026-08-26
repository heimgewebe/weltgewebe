from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

import kind_reference as ref
from ha_common import ROOT, _load_yaml_documents, psql, sha256_text, wait_until



def migration_history_digest(kubectl: str, *, cluster: str) -> str:
    history = psql(
        kubectl,
        "SELECT COALESCE(string_agg(version::text || ':' || success::text || ':' || encode(checksum,'hex'), ',' ORDER BY version), '') FROM _sqlx_migrations",
        cluster=cluster,
    )
    return sha256_text(history)

def migration_failed_attempts(kubectl: str) -> int:
    document = json.loads(
        ref.output(
            [
                kubectl,
                "-n",
                "weltgewebe",
                "get",
                "job/weltgewebe-migration",
                "-o",
                "json",
            ]
        )
    )
    return int(document.get("status", {}).get("failed", 0) or 0)

def migration_job_document(
    kustomize: str, *, node_selector: dict[str, str] | None = None
) -> dict[str, Any]:
    rendered = ref.output(
        [kustomize, "build", "platform/apps/weltgewebe/migration/ha"]
    )
    jobs = [
        document
        for document in _load_yaml_documents(rendered, "HA migration kustomization")
        if isinstance(document, dict) and document.get("kind") == "Job"
    ]
    if len(jobs) != 1:
        raise ref.ProofError(
            f"HA migration kustomization rendered {len(jobs)} Jobs, expected one"
        )
    job = jobs[0]
    if job.get("metadata", {}).get("namespace") != "weltgewebe":
        raise ref.ProofError("HA migration Job is not bound to the weltgewebe namespace")
    if node_selector:
        pod_spec = job.setdefault("spec", {}).setdefault("template", {}).setdefault(
            "spec", {}
        )
        existing = pod_spec.get("nodeSelector")
        if existing not in (None, {}):
            raise ref.ProofError(
                f"HA migration Job already has an unexpected nodeSelector: {existing}"
            )
        pod_spec["nodeSelector"] = dict(node_selector)
    return job

def rerun_migration_job(
    kubectl: str,
    kustomize: str,
    *,
    node_selector: dict[str, str] | None = None,
) -> None:
    ref.run(
        [
            kubectl,
            "-n",
            "weltgewebe",
            "delete",
            "job/weltgewebe-migration",
            "--ignore-not-found=true",
            "--wait=true",
        ],
        timeout=120,
    )
    ref.apply_yaml(
        kubectl,
        migration_job_document(kustomize, node_selector=node_selector),
    )

def migration_network_partition_document() -> dict[str, Any]:
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "t016-migration-egress-partition",
            "namespace": "weltgewebe",
        },
        "spec": {
            "podSelector": {
                "matchLabels": {
                    "app.kubernetes.io/name": "weltgewebe-migration",
                    "app.kubernetes.io/component": "database-migration",
                }
            },
            "policyTypes": ["Egress"],
            "egress": [],
        },
    }

def remove_migration_network_partition(kubectl: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            kubectl,
            "-n",
            "weltgewebe",
            "delete",
            "networkpolicy/t016-migration-egress-partition",
            "--ignore-not-found=true",
            "--wait=true",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stderr": (result.stderr or "").strip()[:500],
    }

def prove_migration_retry_and_idempotency(
    kubectl: str,
    kustomize: str,
    *,
    postgres_cluster: str,
) -> dict[str, Any]:
    baseline = migration_history_digest(kubectl, cluster=postgres_cluster)
    try:
        ref.apply_yaml(kubectl, migration_network_partition_document())
        rerun_migration_job(kubectl, kustomize)
        failed_attempts = int(
            wait_until(
                "migration failure under transient network interruption",
                lambda: migration_failed_attempts(kubectl) or False,
                timeout_seconds=180,
                interval=1,
            )
        )
    except Exception:
        cleanup = remove_migration_network_partition(kubectl)
        if cleanup["returncode"] != 0:
            print(
                "migration network-partition cleanup failed while preserving original failure: "
                + json.dumps(cleanup, sort_keys=True),
                file=sys.stderr,
            )
        raise
    cleanup = remove_migration_network_partition(kubectl)
    if cleanup["returncode"] != 0:
        raise ref.ProofError(
            "migration network-partition cleanup failed: "
            + json.dumps(cleanup, sort_keys=True)
        )
    ref.wait_condition(
        kubectl, "weltgewebe", "job/weltgewebe-migration", "Complete", "10m"
    )
    after_retry = migration_history_digest(kubectl, cluster=postgres_cluster)
    if after_retry != baseline:
        raise ref.ProofError(
            "migration history changed across transient-network retry"
        )

    rerun_migration_job(kubectl, kustomize)
    ref.wait_condition(
        kubectl, "weltgewebe", "job/weltgewebe-migration", "Complete", "10m"
    )
    after_repeat = migration_history_digest(kubectl, cluster=postgres_cluster)
    if after_repeat != baseline:
        raise ref.ProofError("migration history changed across repeated execution")
    return {
        "status": "pass",
        "transient_network_interruption": "temporary pod egress deny NetworkPolicy",
        "failed_attempts_before_network_recovery": failed_attempts,
        "job_retry_observed": failed_attempts >= 1,
        "retry_completed": True,
        "repeated_execution_completed": True,
        "duplicate_migration_history_prevented": True,
        "network_partition_cleanup": cleanup,
        "baseline_history_sha256": baseline,
        "post_retry_history_sha256": after_retry,
        "post_repeat_history_sha256": after_repeat,
    }

def migration_data_egress_document() -> dict[str, Any]:
    return {
        "apiVersion": "networking.k8s.io/v1",
        "kind": "NetworkPolicy",
        "metadata": {
            "name": "t016-migration-postgres-egress",
            "namespace": "weltgewebe",
        },
        "spec": {
            "podSelector": {
                "matchLabels": {
                    "app.kubernetes.io/name": "weltgewebe-migration",
                    "app.kubernetes.io/component": "database-migration",
                }
            },
            "policyTypes": ["Egress"],
            "egress": [
                {
                    "to": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {
                                    "kubernetes.io/metadata.name": "weltgewebe-data"
                                }
                            }
                        }
                    ],
                    "ports": [{"port": 5432, "protocol": "TCP"}],
                }
            ],
        },
    }

def remove_migration_data_egress(kubectl: str) -> dict[str, Any]:
    result = subprocess.run(
        [
            kubectl,
            "-n",
            "weltgewebe",
            "delete",
            "networkpolicy/t016-migration-postgres-egress",
            "--ignore-not-found=true",
            "--wait=true",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    return {
        "returncode": result.returncode,
        "stderr": (result.stderr or "").strip()[:500],
    }

def start_migration_election_probe(
    kubectl: str,
    kustomize: str,
    *,
    healthy_zone: str,
    baseline_history_sha256: str,
) -> None:
    if len(baseline_history_sha256) != 64 or any(
        character not in "0123456789abcdef"
        for character in baseline_history_sha256
    ):
        raise ref.ProofError("migration election baseline must be a pre-failure SHA-256 digest")
    # The normal HA app overlay is already active here and default-denies egress.
    # Give only the proof migration pods the same narrow PostgreSQL port/namespace
    # reachability they need, while DNS remains covered by the normal allow-dns policy.
    ref.apply_yaml(kubectl, migration_data_egress_document())
    try:
        rerun_migration_job(
            kubectl,
            kustomize,
            node_selector={"topology.kubernetes.io/zone": healthy_zone},
        )
    except Exception:
        cleanup = remove_migration_data_egress(kubectl)
        if cleanup["returncode"] != 0:
            print(
                "migration election egress cleanup failed while preserving original failure: "
                + json.dumps(cleanup, sort_keys=True),
                file=sys.stderr,
            )
        raise

def finish_migration_election_probe(
    kubectl: str,
    *,
    postgres_cluster: str,
    baseline_history_sha256: str,
    healthy_zone: str,
) -> dict[str, Any]:
    try:
        ref.wait_condition(
            kubectl, "weltgewebe", "job/weltgewebe-migration", "Complete", "10m"
        )
        failed_attempts = migration_failed_attempts(kubectl)
        after = migration_history_digest(kubectl, cluster=postgres_cluster)
        if after != baseline_history_sha256:
            raise ref.ProofError("migration history changed across PostgreSQL election retry")
    except Exception:
        cleanup = remove_migration_data_egress(kubectl)
        if cleanup["returncode"] != 0:
            print(
                "migration election egress cleanup failed while preserving original failure: "
                + json.dumps(cleanup, sort_keys=True),
                file=sys.stderr,
            )
        raise
    cleanup = remove_migration_data_egress(kubectl)
    if cleanup["returncode"] != 0:
        raise ref.ProofError(
            "migration election egress cleanup failed: "
            + json.dumps(cleanup, sort_keys=True)
        )
    return {
        "status": "pass",
        "interruption": "real zone failure during PostgreSQL primary election",
        "scheduled_healthy_zone": healthy_zone,
        "failed_attempts_before_election_recovery": failed_attempts,
        "job_retry_observed": failed_attempts >= 1,
        "retry_required_for_election_safety": False,
        "election_completion_observed": True,
        "job_completed": True,
        "retry_completed": failed_attempts >= 1,
        "duplicate_migration_history_prevented": True,
        "proof_postgres_egress": {
            "namespace": "weltgewebe-data",
            "port": 5432,
            "cleanup": cleanup,
        },
        "baseline_history_sha256": baseline_history_sha256,
        "post_election_history_sha256": after,
    }

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[2]
PLATFORM = ROOT / "platform"
PROMOTION_SENTINEL = "promotion-required"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
OVERLAYS = ("local", "ci", "staging", "production")
NONLOCAL_OVERLAY_TARGETS = frozenset(
    f"platform/apps/weltgewebe/overlays/{name}"
    for name in ("ci", "staging", "production")
)
LOCAL_FIXTURE_SENTINELS = (
    "weltgewebe-local-fixture",
    "local-test-only-weltgewebe",
)
LOCAL_FIXTURE_ROOTS = (
    PLATFORM / "apps/weltgewebe/migration/local",
    PLATFORM / "apps/weltgewebe/overlays/local",
    PLATFORM / "infrastructure/local-data",
    PLATFORM / "clusters/local",
)


class ContractError(RuntimeError):
    pass


def _documents(path: Path) -> Iterable[dict[str, Any]]:
    for document in yaml.safe_load_all(path.read_text(encoding="utf-8")):
        if isinstance(document, dict):
            yield document


def _all_yaml() -> Iterable[tuple[Path, dict[str, Any]]]:
    for path in sorted(PLATFORM.rglob("*.yaml")):
        for document in _documents(path):
            yield path, document


def _container_specs(deployment: dict[str, Any]) -> list[dict[str, Any]]:
    template = deployment.get("spec", {}).get("template", {})
    pod_spec = template.get("spec", {}) if isinstance(template, dict) else {}
    containers = pod_spec.get("containers", []) if isinstance(pod_spec, dict) else []
    return containers if isinstance(containers, list) else []


def _assert_first_party_deployments() -> None:
    base = PLATFORM / "apps/weltgewebe/base"
    deployments = [
        document
        for path in base.glob("*.yaml")
        for document in _documents(path)
        if document.get("kind") == "Deployment"
    ]
    names = {item["metadata"]["name"] for item in deployments}
    if names != {"weltgewebe-api", "weltgewebe-web"}:
        raise ContractError(f"unexpected first-party deployments: {sorted(names)}")
    for deployment in deployments:
        pod = deployment["spec"]["template"]["spec"]
        pod_security = pod.get("securityContext", {})
        if pod.get("automountServiceAccountToken") is not False:
            raise ContractError(f"{deployment['metadata']['name']} mounts service account token")
        if pod_security.get("runAsNonRoot") is not True:
            raise ContractError(f"{deployment['metadata']['name']} lacks runAsNonRoot")
        if pod_security.get("seccompProfile", {}).get("type") != "RuntimeDefault":
            raise ContractError(f"{deployment['metadata']['name']} lacks RuntimeDefault seccomp")
        if deployment["spec"].get("strategy", {}).get("rollingUpdate", {}).get("maxUnavailable") != 0:
            raise ContractError(f"{deployment['metadata']['name']} permits unavailable rollout pods")
        for container in _container_specs(deployment):
            missing = [key for key in ("startupProbe", "readinessProbe", "livenessProbe", "resources") if key not in container]
            if missing:
                raise ContractError(f"{deployment['metadata']['name']} missing {missing}")
            security = container.get("securityContext", {})
            expected = {
                "allowPrivilegeEscalation": False,
                "privileged": False,
                "readOnlyRootFilesystem": True,
            }
            for key, value in expected.items():
                if security.get(key) is not value:
                    raise ContractError(f"{deployment['metadata']['name']} invalid {key}")
            if security.get("capabilities", {}).get("drop") != ["ALL"]:
                raise ContractError(f"{deployment['metadata']['name']} does not drop all capabilities")


def _assert_no_secrets() -> None:
    for path, document in _all_yaml():
        if document.get("kind") == "Secret":
            raise ContractError(f"Secret object committed at {path.relative_to(ROOT)}")
    contract = json.loads((PLATFORM / "apps/weltgewebe/secret-contract.json").read_text())
    if contract.get("required_keys") != ["database-url"]:
        raise ContractError("secret contract changed without matching validator update")


def _assert_images() -> None:
    lock = json.loads((PLATFORM / "toolchain.lock.json").read_text())
    for section in (lock["tools"], lock["artifacts"]):
        for name, entry in section.items():
            if not HEX64.fullmatch(entry["sha256"]):
                raise ContractError(f"{name} lacks sha256 pin")
    node = lock["kubernetes"]["kind_node_image"]
    if "@sha256:" not in node or not HEX64.fullmatch(node.rsplit("@sha256:", 1)[1]):
        raise ContractError("kind node image is not digest-bound")
    promotion = json.loads((PLATFORM / "image-promotion.contract.json").read_text())
    if promotion.get("status") != "blocked" or promotion.get("production_activation") is not False:
        raise ContractError("image promotion contract must remain blocked in T003")
    for overlay in ("staging", "production"):
        data = yaml.safe_load(
            (PLATFORM / f"apps/weltgewebe/overlays/{overlay}/kustomization.yaml").read_text()
        )
        for image in data.get("images", []):
            if image.get("newTag") != PROMOTION_SENTINEL:
                raise ContractError(f"{overlay} bypasses the image promotion gate: {image}")
    for path, document in _all_yaml():
        if document.get("kind") != "Deployment":
            continue
        for container in _container_specs(document):
            image = str(container.get("image", ""))
            if image.endswith(":latest") or ":latest@" in image:
                raise ContractError(f"unbounded latest image in {path.relative_to(ROOT)}")


def _assert_local_fixture_scope() -> None:
    """Keep public disposable fixture credentials and names local."""
    for path in sorted(PLATFORM.rglob("*")):
        if not path.is_file() or path.suffix not in {".json", ".yaml", ".yml"}:
            continue
        source = path.read_text(encoding="utf-8")
        observed = [item for item in LOCAL_FIXTURE_SENTINELS if item in source]
        if not observed:
            continue
        if any(path.is_relative_to(root) for root in LOCAL_FIXTURE_ROOTS):
            continue
        raise ContractError(
            f"local-only fixture marker(s) {observed} escaped into "
            f"{path.relative_to(ROOT)}"
        )


def _assert_nonlocal_overlay_fixture_boundary(target: str, rendered: str) -> None:
    if target not in NONLOCAL_OVERLAY_TARGETS:
        return
    observed = [item for item in LOCAL_FIXTURE_SENTINELS if item in rendered]
    if observed:
        raise ContractError(
            f"{target} renders local-only fixture marker(s): {observed}"
        )


def _assert_migration_job() -> None:
    job = next(
        _documents(PLATFORM / "apps/weltgewebe/migration/local/job.yaml")
    )
    if job.get("apiVersion") != "batch/v1" or job.get("kind") != "Job":
        raise ContractError("local migration workload must be a batch/v1 Job")
    spec = job.get("spec", {})
    if spec.get("backoffLimit") != 0 or spec.get("activeDeadlineSeconds") != 480:
        raise ContractError("local migration Job must fail once and have a bounded deadline")
    pod = spec.get("template", {}).get("spec", {})
    if pod.get("restartPolicy") != "Never" or pod.get("automountServiceAccountToken") is not False:
        raise ContractError("local migration Job has an unsafe pod lifecycle")
    if pod.get("securityContext", {}).get("runAsNonRoot") is not True:
        raise ContractError("local migration Job must run as non-root")
    containers = pod.get("containers", [])
    if len(containers) != 1:
        raise ContractError("local migration Job must contain exactly one container")
    container = containers[0]
    security = container.get("securityContext", {})
    if security.get("readOnlyRootFilesystem") is not True:
        raise ContractError("local migration Job requires a read-only root filesystem")
    if security.get("capabilities", {}).get("drop") != ["ALL"]:
        raise ContractError("local migration Job must drop all capabilities")
    environment = {item.get("name"): item for item in container.get("env", [])}
    if environment.get("WELTGEWEBE_API_MIGRATION_ONLY", {}).get("value") != "1":
        raise ContractError("local migration Job does not enable migration-only mode")
    if environment.get("WELTGEWEBE_API_STARTUP_MIGRATIONS", {}).get("value") != "run":
        raise ContractError("local migration Job does not run migrations")
    database = environment.get("DATABASE_URL", {}).get("valueFrom", {})
    if database.get("configMapKeyRef") != {
        "name": "weltgewebe-local-fixture",
        "key": "database-url",
    }:
        raise ContractError("local migration Job must use the public ConfigMap fixture")

def _assert_flux_chain() -> None:
    cluster = PLATFORM / "clusters/local"
    source = next(_documents(cluster / "source.yaml"))
    if source.get("kind") != "GitRepository" or source["spec"].get("url") != "https://github.com/heimgewebe/weltgewebe":
        raise ContractError("local Flux source is not the canonical repository")
    expected = {
        "local-data.yaml": [],
        "migration.yaml": ["weltgewebe-local-data"],
        "app.yaml": ["weltgewebe-migration"],
        "gateway.yaml": ["weltgewebe-app"],
    }
    for filename, dependencies in expected.items():
        document = next(_documents(cluster / filename))
        spec = document["spec"]
        if spec.get("prune") is not True or spec.get("wait") is not True:
            raise ContractError(f"{filename} must prune and wait")
        observed = [item["name"] for item in spec.get("dependsOn", [])]
        if observed != dependencies:
            raise ContractError(f"{filename} dependencies {observed} != {dependencies}")


def _assert_compose_parity() -> None:
    config = next(_documents(PLATFORM / "apps/weltgewebe/base/config-map.yaml"))["data"]
    required = {
        "WELTGEWEBE_DOMAIN_READ_SOURCE",
        "WELTGEWEBE_DOMAIN_ACCOUNT_WRITE_SOURCE",
        "WELTGEWEBE_DOMAIN_NODE_WRITE_SOURCE",
        "WELTGEWEBE_DOMAIN_EDGE_WRITE_SOURCE",
        "WELTGEWEBE_PASSKEY_CREDENTIAL_SOURCE",
        "WELTGEWEBE_API_STARTUP_MIGRATIONS",
        "NATS_URL",
        "API_BIND",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ContractError(f"Kubernetes config misses Compose invariants: {missing}")
    compose = (ROOT / "infra/compose/compose.prod.yml").read_text(encoding="utf-8")
    for key in required:
        if key not in compose:
            raise ContractError(f"Compose parity source lacks {key}")


def _run(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        input=input_text,
        text=True,
        check=True,
        capture_output=True,
    )


def _render_and_validate() -> dict[str, int]:
    receipt = json.loads(
        _run([sys.executable, "scripts/platform/bootstrap_tools.py", "--json"]).stdout
    )
    kustomize = receipt["tools"]["kustomize"]
    kubeconform = receipt["tools"]["kubeconform"]
    targets = [
        *(f"platform/apps/weltgewebe/overlays/{name}" for name in OVERLAYS),
        "platform/infrastructure/local-data",
        "platform/apps/weltgewebe/migration/local",
        "platform/infrastructure/gateway",
        "platform/clusters/local",
    ]
    counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        for target in targets:
            rendered = _run([kustomize, "build", target]).stdout
            _assert_nonlocal_overlay_fixture_boundary(target, rendered)
            docs = [item for item in yaml.safe_load_all(rendered) if isinstance(item, dict)]
            if not docs:
                raise ContractError(f"empty Kustomize output for {target}")
            counts[target] = len(docs)
            output = temp / (target.replace("/", "_") + ".yaml")
            output.write_text(rendered, encoding="utf-8")
            _run(
                [
                    kubeconform,
                    "-strict",
                    "-summary",
                    "-ignore-missing-schemas",
                    "-kubernetes-version",
                    "1.36.1",
                    str(output),
                ]
            )
    return counts


def validate(render: bool) -> dict[str, Any]:
    required_paths = [
        PLATFORM / "apps/weltgewebe/base/kustomization.yaml",
        PLATFORM / "apps/weltgewebe/overlays/local/kustomization.yaml",
        PLATFORM / "apps/weltgewebe/overlays/ci/kustomization.yaml",
        PLATFORM / "apps/weltgewebe/overlays/staging/kustomization.yaml",
        PLATFORM / "apps/weltgewebe/overlays/production/kustomization.yaml",
        PLATFORM / "clusters/local/kind.yaml",
        PLATFORM / "clusters/local/kustomization.yaml",
        PLATFORM / "clusters/local/migration.yaml",
        PLATFORM / "apps/weltgewebe/migration/local/kustomization.yaml",
        PLATFORM / "apps/weltgewebe/migration/local/job.yaml",
        PLATFORM / "infrastructure/gateway/kustomization.yaml",
        PLATFORM / "infrastructure/local-data/kustomization.yaml",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required_paths if not path.is_file()]
    if missing:
        raise ContractError(f"missing platform paths: {missing}")
    _assert_no_secrets()
    _assert_first_party_deployments()
    _assert_images()
    _assert_local_fixture_scope()
    _assert_migration_job()
    _assert_flux_chain()
    _assert_compose_parity()
    rendered = _render_and_validate() if render else {}
    return {"status": "pass", "rendered_documents": rendered}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--render", action="store_true")
    args = parser.parse_args()
    try:
        result = validate(args.render)
    except (ContractError, subprocess.CalledProcessError, yaml.YAMLError) as error:
        print(f"platform contract failed: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout, file=sys.stderr)
            print(error.stderr, file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

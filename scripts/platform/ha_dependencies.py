from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

import kind_reference as ref

ROOT = Path(__file__).resolve().parents[2]
NATS_BOX_IMAGE = "natsio/nats-box@sha256:9d5f35d286c3dcfca18bb2339b51345f9f89b580b237ab16ddfe609bdca9c72d"

def ha_nats_runtime_image() -> str:
    nats = next(
        document
        for document in yaml.safe_load_all(
            (ROOT / "platform/infrastructure/ha-data/nats.yaml").read_text(
                encoding="utf-8"
            )
        )
        if isinstance(document, dict) and document.get("kind") == "StatefulSet"
    )
    image = next(
        (
            str(container.get("image", ""))
            for container in nats["spec"]["template"]["spec"]["containers"]
            if container.get("name") == "nats"
        ),
        "",
    )
    name, separator, digest = image.rpartition("@sha256:")
    if (
        not separator
        or not name
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ref.ProofError("HA NATS runtime image is not digest-bound")
    return image

def _digest_bound_local_runtime_tag(role: str, image: str) -> str:
    name, separator, digest = image.rpartition("@sha256:")
    if (
        not separator
        or not name
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise ref.ProofError(f"HA dependency image is not digest-bound: {image}")
    if role not in {"nats", "nats-box"}:
        raise ref.ProofError(f"unsupported HA dependency role: {role}")
    return f"weltgewebe-ha-{role}:sha256-{digest}"

def preload_local_nats_dependencies(kind: str, cluster: str) -> dict[str, Any]:
    if ref.controlled_oci_strict():
        return {"mode": "controlled-oci", "images": {}}

    sources = {"nats": ha_nats_runtime_image(), "nats-box": NATS_BOX_IMAGE}
    images: dict[str, dict[str, str]] = {}
    for role, source_image in sources.items():
        last_error: BaseException | None = None
        for delay_seconds in (0, 5, 10):
            if delay_seconds:
                time.sleep(delay_seconds)
            try:
                ref.run(["docker", "pull", source_image], timeout=600)
                last_error = None
                break
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                last_error = error
        if last_error is not None:
            raise ref.ProofError(
                f"failed to preload digest-bound HA dependency image: {source_image}"
            ) from last_error

        source_image_id = ref.output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", source_image]
        )
        runtime_image = _digest_bound_local_runtime_tag(role, source_image)
        ref.run(["docker", "tag", source_image, runtime_image])
        runtime_image_id = ref.output(
            ["docker", "image", "inspect", "--format", "{{.Id}}", runtime_image]
        )
        if runtime_image_id != source_image_id:
            raise ref.ProofError(
                f"local HA dependency tag changed image identity: {role}"
            )
        ref.run(
            [kind, "load", "docker-image", "--name", cluster, runtime_image],
            timeout=600,
        )
        images[role] = {
            "source_image": source_image,
            "runtime_image": runtime_image,
            "image_id": source_image_id,
        }
    return {"mode": "direct-digest-preload", "images": images}

def apply_ha_data(
    kubectl: str,
    kustomize: str,
    dependency_supply: dict[str, Any] | None,
) -> None:
    if not dependency_supply or dependency_supply.get("mode") != "direct-digest-preload":
        ref.apply_direct(kubectl, kustomize, "platform/infrastructure/ha-data")
        return

    nats_supply = dependency_supply.get("images", {}).get("nats")
    if not isinstance(nats_supply, dict):
        raise ref.ProofError("local NATS dependency supply is missing")
    source_image = nats_supply.get("source_image")
    runtime_image = nats_supply.get("runtime_image")
    if source_image != ha_nats_runtime_image() or not isinstance(runtime_image, str):
        raise ref.ProofError("local NATS dependency supply identity drift")

    rendered = ref.output([kustomize, "build", "platform/infrastructure/ha-data"])
    documents = [
        item for item in yaml.safe_load_all(rendered) if isinstance(item, dict)
    ]
    nats_statefulsets = [
        document
        for document in documents
        if document.get("kind") == "StatefulSet"
        and document.get("metadata", {}).get("name") == "nats"
        and document.get("metadata", {}).get("namespace") == "weltgewebe-data"
    ]
    if len(nats_statefulsets) != 1:
        raise ref.ProofError("rendered HA data must contain exactly one NATS StatefulSet")
    containers = nats_statefulsets[0]["spec"]["template"]["spec"]["containers"]
    nats_containers = [
        container
        for container in containers
        if isinstance(container, dict) and container.get("name") == "nats"
    ]
    if len(nats_containers) != 1 or nats_containers[0].get("image") != source_image:
        raise ref.ProofError("rendered HA NATS image drift")
    nats_containers[0]["image"] = runtime_image
    nats_containers[0]["imagePullPolicy"] = "Never"
    ref.apply_yaml(kubectl, documents)

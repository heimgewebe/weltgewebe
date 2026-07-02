#!/usr/bin/env python3
"""Validate and execute the minimal generated-artifact control manifest."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from scripts.docmeta.docmeta import REPO_ROOT

MANIFEST_REL = ".wgx/generated-artifacts.yml"
REQUIRED_CURATED_ARTIFACTS = {"docs/tasks/index.json"}
GENERATED_DIR_REL = "docs/_generated"
REPO_META_REL = "repo.meta.yaml"
ALLOWED_KINDS = {"generated", "curated_index"}
ROLE_BY_KIND = {"generated": "diagnostic", "curated_index": "task_control"}
ALLOWED_CANONICALITY = {"derived", "canonical"}
ROOT_KEYS = {"schema_version", "artifacts"}
ARTIFACT_KEYS = {
    "path", "kind", "role", "canonicality", "generator", "checks",
    "sources", "commit_required", "blocking",
}
EXPECTED_CONTROLS: dict[str, dict[str, object]] = {
    "docs/_generated/agent-readiness.md": {
        "generator": ["python3", "-m", "scripts.docmeta.generate_agent_readiness"],
        "checks": [["python3", "-m", "scripts.docmeta.generate_agent_readiness", "--check"]],
    },
    "docs/_generated/claim-evidence-map.md": {
        "generator": ["python3", "-m", "scripts.docmeta.generate_claim_evidence_map"],
        "checks": [["python3", "-m", "scripts.docmeta.generate_claim_evidence_map", "--check"]],
    },
    "docs/tasks/index.json": {
        "generator": None,
        "checks": [
            ["python3", "-m", "scripts.docmeta.validate_task_index", "docs/tasks/index.json"],
            ["python3", "-m", "scripts.docmeta.generate_task_index", "--check"],
        ],
    },
}

Finding = dict[str, str]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class DuplicateKeyError(ValueError):
    pass


def _finding(code: str, path: str, detail: str) -> Finding:
    return {"code": code, "path": path, "detail": detail}


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")


def _has_symlink_component(root: Path, relative_path: str) -> bool:
    current = root
    for part in PurePosixPath(relative_path).parts:
        current /= part
        if current.is_symlink():
            return True
    return False


def _safe_repo_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or value != candidate.as_posix():
        return None
    return value


def _actual_generated_artifacts(root: Path) -> tuple[set[str], list[Finding]]:
    generated_dir = root / GENERATED_DIR_REL
    if not generated_dir.is_dir() or _has_symlink_component(root, GENERATED_DIR_REL):
        return set(), [_finding("GENERATED_DIR_MISSING", GENERATED_DIR_REL, "generated diagnostics directory missing or symlinked")]
    return {
        f"{GENERATED_DIR_REL}/{path.name}"
        for path in generated_dir.iterdir()
        if path.is_file() and path.suffix == ".md" and not _has_symlink_component(root, f"{GENERATED_DIR_REL}/{path.name}")
    }, []


def _repo_meta_generated_artifacts(root: Path) -> tuple[set[str] | None, list[Finding]]:
    path = root / REPO_META_REL
    if not path.is_file() or _has_symlink_component(root, REPO_META_REL):
        return None, [_finding("REPO_META_MISSING", REPO_META_REL, "repo metadata file missing or symlinked")]
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        return None, [_finding("REPO_META_UNREADABLE", REPO_META_REL, str(exc))]

    in_section = False
    values: set[str] = set()
    for line in lines:
        if not in_section:
            if line.strip() == "generated_artifacts:":
                in_section = True
            continue
        if line and not line.startswith(" "):
            break
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- "):
            continue
        value = stripped[2:].strip().strip('"').strip("'")
        safe = _safe_repo_path(value)
        if safe is None:
            return None, [_finding("REPO_META_GENERATED_PATH_INVALID", REPO_META_REL, f"invalid generated_artifacts entry: {value!r}")]
        values.add(safe)
    if not in_section:
        return None, [_finding("REPO_META_GENERATED_SECTION_MISSING", REPO_META_REL, "generated_artifacts section missing")]
    return values, []


def _load_manifest(path: Path) -> tuple[Any | None, list[Finding]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return None, [_finding("MANIFEST_UNREADABLE", MANIFEST_REL, str(exc))]
    if not raw.startswith("---\n"):
        return None, [_finding("MANIFEST_FORMAT_INVALID", MANIFEST_REL, "missing YAML document marker")]
    try:
        return json.loads(
            raw[4:],
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_constant,
        ), []
    except (json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        return None, [_finding("MANIFEST_JSON_INVALID", MANIFEST_REL, str(exc))]


def _validate_command(command: Any, *, root: Path, path: str, field: str) -> list[Finding]:
    if not isinstance(command, list) or not command or any(
        not isinstance(item, str) or not item for item in command
    ):
        return [_finding("COMMAND_INVALID", path, f"{field} must be a non-empty argv array")]

    if len(command) >= 3 and command[:2] == ["python3", "-m"]:
        module = command[2]
        if not module.startswith("scripts.docmeta."):
            return [_finding("COMMAND_NOT_ALLOWED", path, f"module outside scripts.docmeta: {module}")]
        module_rel = module.replace(".", "/") + ".py"
        if not (root / module_rel).is_file() or _has_symlink_component(root, module_rel):
            return [_finding("COMMAND_MODULE_MISSING", path, f"module not found: {module}")]
        return []

    if command[0] == "bash" and len(command) in {2, 3}:
        script = _safe_repo_path(command[1])
        if len(command) == 3 and command[2] != "--check":
            return [_finding("COMMAND_NOT_ALLOWED", path, f"unsupported bash argument for {field}: {command[2]!r}")]
        if (
            script is not None
            and script.startswith("scripts/docmeta/generate-")
            and script.endswith(".sh")
            and (root / script).is_file()
            and not _has_symlink_component(root, script)
        ):
            return []
        return [_finding("COMMAND_NOT_ALLOWED", path, f"unsupported bash script for {field}: {command[1]!r}")]

    return [_finding("COMMAND_NOT_ALLOWED", path, f"{field} must use python3 -m or a reviewed scripts/docmeta/generate-*.sh script")]


def _execute_check(
    root: Path,
    artifact_path: str,
    command: list[str],
    runner: CommandRunner,
) -> list[Finding]:
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"PYTHONHOME", "PYTHONPATH", "PYTHONSTARTUP", "PYTHONUSERBASE"}
    }
    env.update({"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"})
    effective_command = [sys.executable, *command[1:]] if command[:1] == ["python3"] else command
    try:
        completed = runner(
            effective_command,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired as exc:
        return [_finding("ARTIFACT_CHECK_EXECUTION_FAILED", artifact_path, f"timeout after {exc.timeout}s")]
    except OSError as exc:
        return [_finding("ARTIFACT_CHECK_EXECUTION_FAILED", artifact_path, str(exc))]
    if completed.returncode == 0:
        return []
    detail = (completed.stderr or completed.stdout or "exit non-zero").strip()[-500:]
    return [_finding("ARTIFACT_CHECK_FAILED", artifact_path, detail)]


def validate_manifest(
    repo_root: str | Path | None = None,
    *,
    run_checks: bool = False,
    runner: CommandRunner = subprocess.run,
) -> list[Finding]:
    root = (Path(repo_root) if repo_root is not None else Path(REPO_ROOT)).resolve()
    if _has_symlink_component(root, MANIFEST_REL):
        return [_finding("MANIFEST_SYMLINK_FORBIDDEN", MANIFEST_REL, "symlink component")]
    data, findings = _load_manifest(root / MANIFEST_REL)
    if findings:
        return findings
    if not isinstance(data, dict):
        return [_finding("MANIFEST_ROOT_INVALID", MANIFEST_REL, "root must be an object")]

    unknown_root = sorted(set(data) - ROOT_KEYS)
    if unknown_root:
        findings.append(_finding("MANIFEST_ROOT_UNKNOWN_FIELDS", MANIFEST_REL, ", ".join(unknown_root)))
    version = data.get("schema_version")
    if type(version) is not int or version != 1:
        findings.append(_finding("MANIFEST_VERSION_INVALID", MANIFEST_REL, "schema_version must be integer 1"))
    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        findings.append(_finding("ARTIFACTS_INVALID", MANIFEST_REL, "artifacts must be an array"))
        return findings

    actual_generated, generated_findings = _actual_generated_artifacts(root)
    findings.extend(generated_findings)
    repo_meta_generated, repo_meta_findings = _repo_meta_generated_artifacts(root)
    findings.extend(repo_meta_findings)
    required_artifacts = set(actual_generated) | REQUIRED_CURATED_ARTIFACTS

    seen: set[str] = set()
    generated_seen: set[str] = set()
    parsed: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        label = f"{MANIFEST_REL}#artifacts[{index}]"
        if not isinstance(artifact, dict):
            findings.append(_finding("ARTIFACT_INVALID", label, "entry must be an object"))
            continue
        unknown = sorted(set(artifact) - ARTIFACT_KEYS)
        if unknown:
            findings.append(_finding("ARTIFACT_UNKNOWN_FIELDS", label, ", ".join(unknown)))
        path = _safe_repo_path(artifact.get("path"))
        if path is None:
            findings.append(_finding("ARTIFACT_PATH_INVALID", label, "path must be repository-relative"))
            continue
        if path in seen:
            findings.append(_finding("ARTIFACT_DUPLICATE", path, "path declared more than once"))
            continue
        seen.add(path)
        parsed.append(artifact)

        kind = artifact.get("kind")
        if kind == "generated":
            generated_seen.add(path)
        role = artifact.get("role")
        canonicality = artifact.get("canonicality")
        if kind not in ALLOWED_KINDS:
            findings.append(_finding("ARTIFACT_KIND_INVALID", path, str(kind)))
        expected_role = ROLE_BY_KIND.get(kind)
        if expected_role is not None and role != expected_role:
            findings.append(_finding(
                "ARTIFACT_ROLE_INVALID",
                path,
                f"{kind} artifacts must use role {expected_role}; observed {role!r}",
            ))
        if canonicality not in ALLOWED_CANONICALITY:
            findings.append(_finding("ARTIFACT_CANONICALITY_INVALID", path, str(canonicality)))
        if kind == "generated" and canonicality != "derived":
            findings.append(_finding("GENERATED_CANONICALITY_INVALID", path, "generated artifacts must be derived"))
        if kind == "curated_index" and canonicality != "canonical":
            findings.append(_finding("CURATED_CANONICALITY_INVALID", path, "curated indexes must be canonical"))

        artifact_file = root / path
        if not artifact_file.is_file() or _has_symlink_component(root, path):
            findings.append(_finding("ARTIFACT_FILE_MISSING", path, "declared artifact must be a regular file"))
        elif kind == "generated":
            try:
                content = artifact_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                findings.append(_finding("ARTIFACT_UNREADABLE", path, str(exc)))
            else:
                if "Generated automatically." not in content:
                    findings.append(_finding("GENERATED_MARKER_MISSING", path, "generated marker missing"))

        sources = artifact.get("sources")
        if not isinstance(sources, list) or not sources:
            findings.append(_finding("SOURCES_INVALID", path, "sources must be a non-empty array"))
        else:
            for source in sources:
                source_path = _safe_repo_path(source)
                if source_path is None:
                    findings.append(_finding("SOURCE_PATH_INVALID", path, f"invalid source: {source!r}"))
                    continue
                if kind == "generated" and source_path.startswith("docs/_generated/"):
                    findings.append(_finding("GENERATED_SOURCE_INVALID", path, f"generated output cannot be a source: {source_path}"))
                if not (root / source_path).exists() or _has_symlink_component(root, source_path):
                    findings.append(_finding("SOURCE_MISSING", path, f"source missing or symlinked: {source_path}"))

        generator = artifact.get("generator")
        if kind == "generated":
            findings.extend(_validate_command(generator, root=root, path=path, field="generator"))
        elif generator is not None:
            findings.append(_finding("CURATED_GENERATOR_FORBIDDEN", path, "curated indexes must not declare a generator"))
        checks = artifact.get("checks")
        if not isinstance(checks, list) or not checks:
            findings.append(_finding("CHECKS_INVALID", path, "checks must be a non-empty array"))
        else:
            for check_index, command in enumerate(checks):
                findings.extend(_validate_command(command, root=root, path=path, field=f"checks[{check_index}]"))

        expected = EXPECTED_CONTROLS.get(path)
        if expected is not None:
            if generator != expected["generator"]:
                findings.append(_finding("GENERATOR_COMMAND_MISMATCH", path, "generator argv differs from reviewed contract"))
            if checks != expected["checks"]:
                findings.append(_finding("CHECK_COMMAND_MISMATCH", path, "check argv differs from reviewed contract"))
        for flag in ("commit_required", "blocking"):
            if artifact.get(flag) is not True:
                findings.append(_finding("CONTROL_FLAG_INVALID", path, f"{flag} must be true"))

    for path in sorted(required_artifacts - seen):
        findings.append(_finding("REQUIRED_ARTIFACT_MISSING", path, "artifact absent from manifest"))
    extras = sorted(seen - required_artifacts)
    if extras:
        findings.append(_finding("UNEXPECTED_ARTIFACT_DECLARED", MANIFEST_REL, ", ".join(extras)))

    if repo_meta_generated is not None:
        meta_missing = sorted(actual_generated - repo_meta_generated)
        meta_extra = sorted(repo_meta_generated - actual_generated)
        if meta_missing or meta_extra:
            details = []
            if meta_missing:
                details.append("missing in repo.meta.yaml: " + ", ".join(meta_missing))
            if meta_extra:
                details.append("not present in docs/_generated: " + ", ".join(meta_extra))
            findings.append(_finding("REPO_META_GENERATED_DRIFT", REPO_META_REL, "; ".join(details)))
        manifest_mismatch = sorted(repo_meta_generated ^ generated_seen)
        if manifest_mismatch:
            findings.append(_finding("REPO_META_MANIFEST_MISMATCH", REPO_META_REL, ", ".join(manifest_mismatch)))

    if run_checks and not findings:
        for artifact in parsed:
            for command in artifact["checks"]:
                findings.extend(_execute_check(root, artifact["path"], command, runner))
    return sorted(findings, key=lambda item: (item["path"], item["code"], item["detail"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="execute blocking checks")
    args = parser.parse_args(argv)
    try:
        findings = validate_manifest(run_checks=args.check)
    except Exception as exc:
        findings = [_finding("VALIDATOR_INTERNAL_ERROR", MANIFEST_REL, str(exc))]
    print(json.dumps({
        "manifest": MANIFEST_REL,
        "mode": "check" if args.check else "validate",
        "findings_count": len(findings),
        "findings": findings,
    }, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

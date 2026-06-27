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
REQUIRED_ARTIFACTS = {
    "docs/_generated/agent-readiness.md",
    "docs/_generated/claim-evidence-map.md",
    "docs/tasks/index.json",
}
ALLOWED_KINDS = {"generated", "curated_index"}
ALLOWED_ROLES = {"diagnostic", "navigation", "task_control"}
ALLOWED_CANONICALITY = {"derived", "canonical"}
ROOT_KEYS = {"schema_version", "artifacts"}
ARTIFACT_KEYS = {
    "path",
    "kind",
    "role",
    "canonicality",
    "generator",
    "checks",
    "sources",
    "commit_required",
    "blocking",
}
EXPECTED_CONTROLS: dict[str, dict[str, object]] = {
    "docs/_generated/agent-readiness.md": {
        "generator": ["python3", "-m", "scripts.docmeta.generate_agent_readiness"],
        "checks": [
            [
                "python3",
                "-m",
                "scripts.docmeta.generate_agent_readiness",
                "--check",
            ]
        ],
    },
    "docs/_generated/claim-evidence-map.md": {
        "generator": [
            "python3",
            "-m",
            "scripts.docmeta.generate_claim_evidence_map",
        ],
        "checks": [
            [
                "python3",
                "-m",
                "scripts.docmeta.generate_claim_evidence_map",
                "--check",
            ]
        ],
    },
    "docs/tasks/index.json": {
        "generator": None,
        "checks": [
            [
                "python3",
                "-m",
                "scripts.docmeta.validate_task_index",
                "docs/tasks/index.json",
            ],
            [
                "python3",
                "-m",
                "scripts.docmeta.generate_task_index",
                "--check",
            ],
        ],
    },
}

Finding = dict[str, str]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class DuplicateKeyError(ValueError):
    pass


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
        current = current / part
        if current.is_symlink():
            return True
    return False


def _finding(code: str, path: str, detail: str) -> Finding:
    return {"code": code, "path": path, "detail": detail}


def _load_manifest(path: Path) -> tuple[Any | None, list[Finding]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [_finding("MANIFEST_UNREADABLE", str(path), str(exc))]
    if not raw.startswith("---\n"):
        return None, [
            _finding(
                "MANIFEST_FORMAT_INVALID",
                str(path),
                "manifest must start with a YAML document marker followed by JSON",
            )
        ]
    try:
        return (
            json.loads(
                raw[4:],
                object_pairs_hook=_reject_duplicate_keys,
                parse_constant=_reject_constant,
            ),
            [],
        )
    except (json.JSONDecodeError, DuplicateKeyError, ValueError) as exc:
        return None, [_finding("MANIFEST_JSON_INVALID", str(path), str(exc))]


def _safe_repo_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or ".." in candidate.parts or value != candidate.as_posix():
        return None
    return value


def _validate_command(
    command: Any,
    *,
    root: Path,
    artifact_path: str,
    field: str,
) -> list[Finding]:
    findings: list[Finding] = []
    if not isinstance(command, list) or not command:
        return [
            _finding(
                "COMMAND_INVALID",
                artifact_path,
                f"{field} must be a non-empty argv array",
            )
        ]
    if any(not isinstance(item, str) or not item for item in command):
        return [
            _finding(
                "COMMAND_INVALID",
                artifact_path,
                f"{field} must contain only non-empty strings",
            )
        ]
    if len(command) < 3 or command[:2] != ["python3", "-m"]:
        return [
            _finding(
                "COMMAND_NOT_ALLOWED",
                artifact_path,
                f"{field} must use python3 -m with a repository-owned docmeta module",
            )
        ]
    module = command[2]
    if not module.startswith("scripts.docmeta."):
        findings.append(
            _finding(
                "COMMAND_NOT_ALLOWED",
                artifact_path,
                f"{field} module is outside scripts.docmeta: {module}",
            )
        )
        return findings
    module_rel = module.replace(".", "/") + ".py"
    module_path = root / module_rel
    if not module_path.is_file() or _has_symlink_component(root, module_rel):
        findings.append(
            _finding(
                "COMMAND_MODULE_MISSING",
                artifact_path,
                f"{field} module does not resolve to a regular repository file: {module}",
            )
        )
    return findings


def validate_manifest(
    repo_root: str | Path | None = None,
    *,
    run_checks: bool = False,
    runner: CommandRunner = subprocess.run,
) -> list[Finding]:
    root = Path(repo_root) if repo_root is not None else Path(REPO_ROOT)
    root = root.resolve()
    manifest_path = root / MANIFEST_REL
    if _has_symlink_component(root, MANIFEST_REL):
        return [
            _finding(
                "MANIFEST_SYMLINK_FORBIDDEN",
                MANIFEST_REL,
                "manifest path must not contain symlink components",
            )
        ]
    data, findings = _load_manifest(manifest_path)
    if findings:
        return findings
    if not isinstance(data, dict):
        return [_finding("MANIFEST_ROOT_INVALID", MANIFEST_REL, "root must be an object")]

    unknown_root = sorted(set(data) - ROOT_KEYS)
    if unknown_root:
        findings.append(
            _finding(
                "MANIFEST_ROOT_UNKNOWN_FIELDS",
                MANIFEST_REL,
                ", ".join(unknown_root),
            )
        )
    if data.get("schema_version") != 1:
        findings.append(
            _finding(
                "MANIFEST_VERSION_INVALID",
                MANIFEST_REL,
                "schema_version must equal 1",
            )
        )

    artifacts = data.get("artifacts")
    if not isinstance(artifacts, list):
        findings.append(
            _finding("ARTIFACTS_INVALID", MANIFEST_REL, "artifacts must be an array")
        )
        return sorted(findings, key=lambda item: (item["path"], item["code"]))

    seen_paths: set[str] = set()
    parsed_artifacts: list[dict[str, Any]] = []
    for index, artifact in enumerate(artifacts):
        label = f"{MANIFEST_REL}#artifacts[{index}]"
        if not isinstance(artifact, dict):
            findings.append(_finding("ARTIFACT_INVALID", label, "entry must be an object"))
            continue
        unknown_fields = sorted(set(artifact) - ARTIFACT_KEYS)
        if unknown_fields:
            findings.append(
                _finding(
                    "ARTIFACT_UNKNOWN_FIELDS",
                    label,
                    ", ".join(unknown_fields),
                )
            )

        path_value = _safe_repo_path(artifact.get("path"))
        if path_value is None:
            findings.append(
                _finding("ARTIFACT_PATH_INVALID", label, "path must be repository-relative")
            )
            continue
        if path_value in seen_paths:
            findings.append(
                _finding("ARTIFACT_DUPLICATE", path_value, "path is declared more than once")
            )
            continue
        seen_paths.add(path_value)
        parsed_artifacts.append(artifact)

        kind = artifact.get("kind")
        role = artifact.get("role")
        canonicality = artifact.get("canonicality")
        if kind not in ALLOWED_KINDS:
            findings.append(_finding("ARTIFACT_KIND_INVALID", path_value, str(kind)))
        if role not in ALLOWED_ROLES:
            findings.append(_finding("ARTIFACT_ROLE_INVALID", path_value, str(role)))
        if canonicality not in ALLOWED_CANONICALITY:
            findings.append(
                _finding("ARTIFACT_CANONICALITY_INVALID", path_value, str(canonicality))
            )
        if kind == "generated" and canonicality != "derived":
            findings.append(
                _finding(
                    "GENERATED_CANONICALITY_INVALID",
                    path_value,
                    "generated artifacts must be derived",
                )
            )
        if kind == "curated_index" and canonicality != "canonical":
            findings.append(
                _finding(
                    "CURATED_CANONICALITY_INVALID",
                    path_value,
                    "curated indexes must be canonical",
                )
            )

        artifact_file = root / path_value
        if not artifact_file.is_file() or _has_symlink_component(root, path_value):
            findings.append(
                _finding(
                    "ARTIFACT_FILE_MISSING",
                    path_value,
                    "declared artifact must be a regular file",
                )
            )
        elif kind == "generated":
            try:
                content = artifact_file.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                findings.append(_finding("ARTIFACT_UNREADABLE", path_value, str(exc)))
            else:
                if "Generated automatically." not in content:
                    findings.append(
                        _finding(
                            "GENERATED_MARKER_MISSING",
                            path_value,
                            "generated artifact lacks the generated marker",
                        )
                    )

        sources = artifact.get("sources")
        if not isinstance(sources, list) or not sources:
            findings.append(
                _finding("SOURCES_INVALID", path_value, "sources must be a non-empty array")
            )
        else:
            for source in sources:
                source_path = _safe_repo_path(source)
                if source_path is None:
                    findings.append(
                        _finding("SOURCE_PATH_INVALID", path_value, f"invalid source: {source!r}")
                    )
                    continue
                if kind == "generated" and source_path.startswith("docs/_generated/"):
                    findings.append(
                        _finding(
                            "GENERATED_SOURCE_INVALID",
                            path_value,
                            f"generated output cannot be a source: {source_path}",
                        )
                    )
                resolved_source = root / source_path
                if not resolved_source.exists() or _has_symlink_component(
                    root, source_path
                ):
                    findings.append(
                        _finding(
                            "SOURCE_MISSING",
                            path_value,
                            f"source does not exist as a non-symlink path: {source_path}",
                        )
                    )

        generator = artifact.get("generator")
        if kind == "generated":
            findings.extend(
                _validate_command(
                    generator,
                    root=root,
                    artifact_path=path_value,
                    field="generator",
                )
            )
        elif generator is not None:
            findings.append(
                _finding(
                    "CURATED_GENERATOR_FORBIDDEN",
                    path_value,
                    "curated indexes must declare checks, not a generator",
                )
            )

        checks = artifact.get("checks")
        if not isinstance(checks, list) or not checks:
            findings.append(
                _finding("CHECKS_INVALID", path_value, "checks must be a non-empty array")
            )
        else:
            for check_index, command in enumerate(checks):
                findings.extend(
                    _validate_command(
                        command,
                        root=root,
                        artifact_path=path_value,
                        field=f"checks[{check_index}]",
                    )
                )

        expected_control = EXPECTED_CONTROLS.get(path_value)
        if expected_control is not None:
            if generator != expected_control["generator"]:
                findings.append(
                    _finding(
                        "GENERATOR_COMMAND_MISMATCH",
                        path_value,
                        "generator argv differs from the reviewed minimal contract",
                    )
                )
            if checks != expected_control["checks"]:
                findings.append(
                    _finding(
                        "CHECK_COMMAND_MISMATCH",
                        path_value,
                        "check argv differs from the reviewed minimal contract",
                    )
                )

        for flag in ("commit_required", "blocking"):
            if artifact.get(flag) is not True:
                findings.append(
                    _finding(
                        "CONTROL_FLAG_INVALID",
                        path_value,
                        f"{flag} must be true in the minimal blocking scope",
                    )
                )

    missing_required = sorted(REQUIRED_ARTIFACTS - seen_paths)
    extra_required = sorted(seen_paths - REQUIRED_ARTIFACTS)
    for path_value in missing_required:
        findings.append(
            _finding(
                "REQUIRED_ARTIFACT_MISSING",
                path_value,
                "critical artifact is absent from the minimal manifest",
            )
        )
    if extra_required:
        findings.append(
            _finding(
                "SCOPE_EXPANSION_UNREVIEWED",
                MANIFEST_REL,
                "minimal manifest contains undeclared scope: " + ", ".join(extra_required),
            )
        )

    if run_checks and not findings:
        environment = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "PYTHONHOME",
                "PYTHONPATH",
                "PYTHONSTARTUP",
                "PYTHONUSERBASE",
            }
        }
        environment.update(
            {
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONNOUSERSITE": "1",
            }
        )
        for artifact in parsed_artifacts:
            path_value = artifact["path"]
            for command in artifact["checks"]:
                execution_command = [sys.executable, *command[1:]]
                completed = runner(
                    execution_command,
                    cwd=root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                    timeout=120,
                )
                if completed.returncode != 0:
                    diagnostic = (completed.stderr or completed.stdout or "").strip()
                    if len(diagnostic) > 500:
                        diagnostic = diagnostic[-500:]
                    findings.append(
                        _finding(
                            "ARTIFACT_CHECK_FAILED",
                            path_value,
                            f"{' '.join(command)}: {diagnostic or 'exit non-zero'}",
                        )
                    )

    return sorted(findings, key=lambda item: (item["path"], item["code"], item["detail"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="also execute every blocking artifact check",
    )
    args = parser.parse_args(argv)
    findings = validate_manifest(run_checks=args.check)
    payload = {
        "manifest": MANIFEST_REL,
        "mode": "check" if args.check else "validate",
        "findings_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())

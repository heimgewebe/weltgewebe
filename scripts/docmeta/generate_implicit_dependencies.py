#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.docmeta.generated_check import write_or_check

OUT_FILE = os.path.join(REPO_ROOT, "docs", "_generated", "implicit-dependencies.md")
HISTORICAL_SOURCE_COMMIT = "b043a86dbf4e0e0868feb5177745a0f32a3264c0"
HISTORICAL_SOURCE_PATH = "docs/_generated/implicit-dependencies.md"
HISTORICAL_SOURCE_SHA256 = "565bac2acc11b53528a2e0de755cccc9fd20c569206bbbc9c4896291a22f5327"
HISTORICAL_FINDING_COUNT = 51
ALLOWED_DECISIONS = {"explicit", "accepted-coupling", "remove", "not-relevant"}

_RECIPE_ENV_PREFIX = re.compile(
    r"^(?:(?:env|\$\([A-Za-z0-9_.-]+\)|[A-Za-z_][A-Za-z0-9_]*=\S+)\s+)+"
)
_PYTHON_MODULE = re.compile(r"^(?:python3|python)\s+-m\s+([^\s]+)")
_PYTHON_SCRIPT = re.compile(r"^(?:python3|python)\s+([^\s]+\.py)(?:\s|$)")
_BASH_SCRIPT = re.compile(r"^bash\s+([^\s]+)(?:\s|$)")
_HISTORICAL_ROW = re.compile(
    r"^\| Makefile \((?P<target>[^)]+)\) \| (?P<dependency>[^|]+?) "
    r"\| `(?P<evidence>.+)` \| (?P<documented>[^|]+?) \|$"
)


class DependencyDecisionError(ValueError):
    pass


def _historical_audit_path() -> Path:
    return Path(REPO_ROOT) / "scripts" / "docmeta" / "data" / "implicit-dependencies-b043a86.md"


def _strip_recipe_environment_prefix(command: str) -> str:
    return _RECIPE_ENV_PREFIX.sub("", command)


def _normalize_recipe_command(command: str) -> str:
    command = command.strip()
    while command.startswith(("@", "-")):
        command = command[1:].lstrip()
    return _strip_recipe_environment_prefix(command)


def _extract_dependency(command: str) -> tuple[str, str] | None:
    normalized = _normalize_recipe_command(command)
    module_match = _PYTHON_MODULE.match(normalized)
    if module_match:
        return "python-module", module_match.group(1)
    script_match = _PYTHON_SCRIPT.match(normalized)
    if script_match:
        return "python-script", script_match.group(1)
    bash_match = _BASH_SCRIPT.match(normalized)
    if bash_match:
        return "bash-script", bash_match.group(1)
    return None


def collect_deps() -> list[dict[str, Any]]:
    makefile_path = Path(REPO_ROOT) / "Makefile"
    deps: list[dict[str, Any]] = []
    if not makefile_path.exists():
        return deps

    current_target: str | None = None
    for line_number, line in enumerate(makefile_path.read_text(encoding="utf-8").splitlines(), 1):
        line_stripped = line.strip()
        if not line_stripped or line_stripped.startswith("#"):
            continue
        target_match = re.match(r"^([a-zA-Z0-9_.-]+):", line)
        if target_match:
            current_target = target_match.group(1).strip()
            continue
        if current_target is None or not line.startswith("\t"):
            continue
        extracted = _extract_dependency(line_stripped)
        if extracted is None:
            continue
        kind, dependency = extracted
        deps.append(
            {
                "source": "Makefile",
                "target": current_target,
                "dependency": dependency,
                "evidence": line_stripped,
                "kind": kind,
                "line": line_number,
            }
        )
    return deps


def _module_candidate(module: str) -> Path:
    return Path(REPO_ROOT) / (module.replace(".", "/") + ".py")


def _classify_dependency(dep: dict[str, Any], *, historical: bool) -> dict[str, str]:
    dependency = str(dep["dependency"])
    kind = str(dep.get("kind") or (_extract_dependency(str(dep["evidence"])) or ("unknown", ""))[0])

    if kind in {"python-script", "bash-script"}:
        candidate = Path(REPO_ROOT) / dependency
        if candidate.is_file():
            return {
                "decision": "explicit",
                "decision_evidence": f"current repository file `{dependency}` exists and is invoked directly",
            }
    elif kind == "python-module":
        if dependency == "unittest":
            return {
                "decision": "accepted-coupling",
                "decision_evidence": "Python standard-library test runner, invoked explicitly by the Makefile",
            }
        if dependency == "pytest":
            lock_path = Path(REPO_ROOT) / "tools" / "py" / "uv.lock"
            if lock_path.is_file():
                return {
                    "decision": "accepted-coupling",
                    "decision_evidence": "repository tooling dependency locked by `tools/py/uv.lock`",
                }
        module_path = _module_candidate(dependency)
        package_path = Path(REPO_ROOT) / dependency.replace(".", "/") / "__init__.py"
        if module_path.is_file() or package_path.is_file():
            resolved = module_path if module_path.is_file() else package_path
            resolved_rel = resolved.relative_to(REPO_ROOT).as_posix()
            return {
                "decision": "explicit",
                "decision_evidence": f"current repository module resolves to `{resolved_rel}` and is invoked directly",
            }

    if historical:
        return {
            "decision": "remove",
            "decision_evidence": "historical dependency no longer resolves in the current repository",
        }
    raise DependencyDecisionError(
        f"unclassified current dependency: target={dep['target']!r} dependency={dependency!r} evidence={dep['evidence']!r}"
    )


def _finding_id(dep: dict[str, Any]) -> str:
    canonical = json.dumps(
        [dep["source"], dep["target"], dep["dependency"], dep["evidence"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def _decide(deps: list[dict[str, Any]], *, historical: bool) -> list[dict[str, Any]]:
    decided: list[dict[str, Any]] = []
    for dep in deps:
        decision = _classify_dependency(dep, historical=historical)
        if decision["decision"] not in ALLOWED_DECISIONS:
            raise DependencyDecisionError(f"unsupported decision: {decision['decision']}")
        decided.append({**dep, "finding_id": _finding_id(dep), **decision})
    return decided


def load_historical_audit() -> dict[str, Any]:
    path = _historical_audit_path()
    source_bytes = path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    if source_sha256 != HISTORICAL_SOURCE_SHA256:
        raise DependencyDecisionError(
            "historical audit source digest mismatch: "
            f"expected={HISTORICAL_SOURCE_SHA256} observed={source_sha256}"
        )

    findings: list[dict[str, str]] = []
    for line in source_bytes.decode("utf-8").splitlines():
        match = _HISTORICAL_ROW.fullmatch(line)
        if match is None:
            continue
        findings.append(
            {
                "source": "Makefile",
                "target": match.group("target").strip(),
                "dependency": match.group("dependency").strip(),
                "evidence": match.group("evidence"),
            }
        )

    if len(findings) != HISTORICAL_FINDING_COUNT:
        raise DependencyDecisionError(
            f"historical audit must contain exactly {HISTORICAL_FINDING_COUNT} findings"
        )
    finding_ids = [_finding_id(finding) for finding in findings]
    if len(set(finding_ids)) != len(finding_ids):
        raise DependencyDecisionError("historical audit contains duplicate findings")

    return {
        "schema_version": 1,
        "source_commit": HISTORICAL_SOURCE_COMMIT,
        "source_path": HISTORICAL_SOURCE_PATH,
        "source_sha256": source_sha256,
        "finding_count": len(findings),
        "findings": findings,
    }


def _escape_table(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_table(decisions: list[dict[str, Any]], *, include_line: bool) -> list[str]:
    columns = ["ID", "Target", "Dependency", "Evidence", "Decision", "Decision evidence"]
    if include_line:
        columns.insert(2, "Line")
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for item in decisions:
        row = [
            f"`{item['finding_id']}`",
            _escape_table(item["target"]),
        ]
        if include_line:
            row.append(str(item["line"]))
        row.extend(
            [
                f"`{_escape_table(item['dependency'])}`",
                f"`{_escape_table(item['evidence'])}`",
                item["decision"],
                _escape_table(item["decision_evidence"]),
            ]
        )
        lines.append("| " + " | ".join(row) + " |")
    return lines


def render() -> str:
    historical_payload = load_historical_audit()
    historical_deps = []
    for finding in historical_payload["findings"]:
        extracted = _extract_dependency(str(finding["evidence"]))
        historical_deps.append(
            {
                **finding,
                "kind": extracted[0] if extracted else "unknown",
            }
        )
    historical_decisions = _decide(historical_deps, historical=True)
    current_decisions = _decide(collect_deps(), historical=False)

    historical_counts = {
        decision: sum(item["decision"] == decision for item in historical_decisions)
        for decision in sorted(ALLOWED_DECISIONS)
    }
    current_counts = {
        decision: sum(item["decision"] == decision for item in current_decisions)
        for decision in sorted(ALLOWED_DECISIONS)
    }
    makefile_sha256 = hashlib.sha256((Path(REPO_ROOT) / "Makefile").read_bytes()).hexdigest()

    lines = [
        "---",
        "id: docs.generated.implicit-dependencies",
        "title: Implicit Dependency Decisions",
        "doc_type: generated",
        "status: active",
        "summary: Reproduzierbare Einzelentscheidungen zu Makefile-Ausführungskanten.",
        "---",
        "",
        "## Weltgewebe Dependency Decisions",
        "",
        "Generated automatically. Do not edit.",
        "",
        "> **Contract:** This report classifies direct Makefile execution edges. It is diagnostic evidence, not an overall architecture pass, runtime-health proof, deployment proof, or permission to mutate.",
        "",
        "## Historical audit closure",
        "",
        f"- Source commit: `{historical_payload['source_commit']}`",
        f"- Source path: `{historical_payload['source_path']}`",
        f"- Source SHA-256: `{historical_payload['source_sha256']}`",
        f"- Findings decided: **{len(historical_decisions)} / {HISTORICAL_FINDING_COUNT}**",
        "- Allowed decisions: `explicit`, `accepted-coupling`, `remove`, `not-relevant`.",
        "- Classification counts: " + ", ".join(
            f"`{key}`={value}" for key, value in historical_counts.items()
        ),
        "",
        "Each historical row remains individually addressable by a stable finding ID. A direct Makefile invocation is classified as `explicit`; standard or lock-bound tooling is an `accepted-coupling`; a historical edge absent from the current repository is `remove`.",
        "",
        *_render_table(historical_decisions, include_line=False),
        "",
        "## Current Makefile snapshot",
        "",
        f"- Makefile SHA-256: `{makefile_sha256}`",
        f"- Current execution edges decided: **{len(current_decisions)} / {len(current_decisions)}**",
        "- Classification counts: " + ", ".join(
            f"`{key}`={value}" for key, value in current_counts.items()
        ),
        "- New Python-module, Python-script, or Bash-script edges without a resolvable decision make generation and `--check` fail closed.",
        "",
        *_render_table(current_decisions, include_line=True),
        "",
        "## Interpretation boundary",
        "",
        "`explicit` means only that the Makefile names a current repository script or module directly. `accepted-coupling` means the invoked test/tooling runtime is standard-library or repository-lock bound. Neither decision proves semantic correctness, complete architecture coverage, successful execution, current production state, or safe deployment.",
        "",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="compare output without rewriting it")
    args = parser.parse_args(argv)
    try:
        content = render()
    except (DependencyDecisionError, OSError, UnicodeDecodeError) as exc:
        print(f"implicit dependency decision error: {exc}", file=sys.stderr)
        return 1
    return write_or_check(OUT_FILE, content, check=args.check, label=os.path.relpath(OUT_FILE, REPO_ROOT))


if __name__ == "__main__":
    sys.exit(main())

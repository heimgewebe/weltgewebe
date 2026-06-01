"""
check_agent_preflight.py — Safety-Preflight Guard (AGENT-SAFE-001, report-only).

Prüft agentische Änderungen deterministisch auf bekannte Fehlermuster, bevor
spätere Mechaniken (Claim-Spine, Agent-Contracts, Write-Mode) existieren.

Modus: report-only (Stufe 1 gemäß Blueprint-Ratchet).
Der Guard meldet Befunde als maschinenlesbares JSON und gibt Exit-Code 0 zurück,
solange keine blockierenden Checks aktiviert sind.

Fehlercodes (vollständige Liste in docs/security/agent-write-scope-baseline.md):
  MISSING_TASK_ID
  MISSING_TASK_TYPE
  MISSING_ALLOWED_PATHS
  MISSING_VALIDATION
  MISSING_EXPECTED_EVIDENCE
  GENERATED_DIRECT_EDIT
  ROADMAP_DONE_WITHOUT_CLAIM
  STATUS_DONE_WITHOUT_PROOF
  PATH_OUT_OF_SCOPE
  WORKFLOW_CHANGE_WITHOUT_TASK_TYPE
  INFRA_CHANGE_WITHOUT_PROOF
  DELETE_WITHOUT_PERMISSION

CLI-Schnittstelle:
    python3 -m scripts.agent.check_agent_preflight \\
        --task-file path/to/task.yaml \\
        [--changed-paths path1 path2 ...] \\
        [--deleted-paths path1 path2 ...] \\
        [--mode report-only|warn]

Exit-Codes:
    0  keine Befunde oder report-only-Modus
    1  Befunde gefunden (im warn-Modus)
    2  Aufruffehler (z. B. fehlende Pflichtargumente)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Konstanten
# ---------------------------------------------------------------------------

GENERATED_PREFIX = "docs/_generated/"

# Pfade, die einen passenden task_type erfordern
WORKFLOW_PREFIX = ".github/workflows/"
INFRA_PREFIXES = ("infra/", "deployment/")

# Indikatoren, die einen Done-Status in Roadmaps/Status-Matrizen ohne Proof anzeigen
_DONE_CHECKBOX_RE = re.compile(r"^\s*-\s*\[x\]", re.IGNORECASE)
_DONE_STATUS_RE = re.compile(r'"?status"?\s*:\s*"?done"?', re.IGNORECASE)
_DONE_CLAIM_HINT_RE = re.compile(
    r"\bproof_ref\b|\bclaim\b|\bclaim_ref\b|\bevidence\b", re.IGNORECASE
)

# Gültige task_id nach docs/tasks/schema.json
TASK_ID_RE = re.compile(r"^[A-Z]+(-[A-Z]+)*-[0-9]{3}$")


class _PreflightArgumentParser(argparse.ArgumentParser):
    """ArgumentParser, der bei Aufruffehlern ValueError statt SystemExit wirft."""

    def error(self, message: str) -> None:
        raise ValueError(message)

# ---------------------------------------------------------------------------
# YAML-Minimalparser für Task-Dateien
# (kein PyYAML, um externe Abhängigkeiten zu vermeiden)
# ---------------------------------------------------------------------------


def _parse_simple_yaml(path: str) -> dict[str, Any]:
    """
    Liest eine flache YAML-Datei mit optionalem `---`-Frontmatter-Rahmen.
    Unterstützt Skalare, einfache Inline-Listen (`[a, b]`) und Block-Listen
    auf erster Einrückungsebene.
    Keine verschachtelten Objekte, kein vollständiger YAML-Parser.
    """
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()

    lines = raw.splitlines()

    # Frontmatter-Rahmen entfernen (---…---) oder ganzes Dokument verwenden
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        lines = lines[1:end]

    data: dict[str, Any] = {}
    current_key: str | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if line.startswith(" ") or line.startswith("\t"):
            # Block-Listenelement
            if current_key and stripped.startswith("- "):
                val = stripped[2:].strip().strip("\"'")
                if isinstance(data.get(current_key), list):
                    data[current_key].append(val)
            continue

        if ":" in stripped:
            key, _, rest = stripped.partition(":")
            key = key.strip()
            val_str = rest.strip()

            if val_str.startswith("[") and val_str.endswith("]"):
                items = [
                    v.strip().strip("\"'")
                    for v in val_str[1:-1].split(",")
                    if v.strip()
                ]
                data[key] = items
                current_key = None
            elif val_str == "":
                data[key] = []
                current_key = key
            else:
                data[key] = val_str.strip("\"'")
                current_key = None

    return data


# ---------------------------------------------------------------------------
# Einzelne Checks
# ---------------------------------------------------------------------------


def check_task_metadata(task: dict[str, Any]) -> list[dict[str, str]]:
    """Prüft Pflichtfelder der Task-Metadaten."""
    findings: list[dict[str, str]] = []

    task_id = task.get("task_id", "")
    if not task_id or not isinstance(task_id, str) or not task_id.strip():
        findings.append({
            "code": "MISSING_TASK_ID",
            "message": "task_id fehlt oder ist leer",
        })
    elif not TASK_ID_RE.match(task_id.strip()):
        findings.append({
            "code": "MISSING_TASK_ID",
            "message": (
                f"task_id '{task_id}' entspricht nicht dem erlaubten Format "
                "([A-Z]+(-[A-Z]+)*-[0-9]{3})"
            ),
        })

    if not task.get("task_type", ""):
        findings.append({
            "code": "MISSING_TASK_TYPE",
            "message": "task_type fehlt oder ist leer",
        })

    allowed = task.get("allowed_paths", [])
    if not allowed or (isinstance(allowed, list) and len(allowed) == 0):
        findings.append({
            "code": "MISSING_ALLOWED_PATHS",
            "message": "allowed_paths fehlt oder ist leer",
        })

    has_validation = bool(task.get("validation") or task.get("validation_commands"))
    if not has_validation:
        findings.append({
            "code": "MISSING_VALIDATION",
            "message": "Weder 'validation' noch 'validation_commands' vorhanden",
        })

    has_evidence = bool(task.get("expected_evidence") or task.get("evidence"))
    if not has_evidence:
        findings.append({
            "code": "MISSING_EXPECTED_EVIDENCE",
            "message": "Weder 'expected_evidence' noch 'evidence' vorhanden",
        })

    return findings


def _is_under_allowed_path(path: str, allowed: str) -> bool:
    """Prüft exakt, ob path unter dem allowed-Präfix liegt.

    'docs/' erlaubt 'docs/foo.md' und 'docs/', aber nicht 'docs_bad/foo.md'.
    """
    norm = path.replace("\\", "/").strip("/")
    prefix = allowed.replace("\\", "/").strip("/")
    if not prefix:
        return False
    return norm == prefix or norm.startswith(prefix + "/")


def check_path_scope(
    changed_paths: list[str], allowed_paths: list[str]
) -> list[dict[str, str]]:
    """Prüft, ob geänderte Pfade innerhalb von allowed_paths liegen."""
    findings: list[dict[str, str]] = []
    if not allowed_paths:
        return findings

    for path in changed_paths:
        if not any(_is_under_allowed_path(path, ap) for ap in allowed_paths):
            findings.append({
                "code": "PATH_OUT_OF_SCOPE",
                "message": f"Pfad '{path}' liegt außerhalb von allowed_paths",
                "path": path,
            })

    return findings


def check_generated_direct_edit(changed_paths: list[str]) -> list[dict[str, str]]:
    """Erkennt direkte Änderungen an docs/_generated/*."""
    findings: list[dict[str, str]] = []
    for path in changed_paths:
        norm = path.replace("\\", "/")
        if norm.startswith(GENERATED_PREFIX):
            findings.append({
                "code": "GENERATED_DIRECT_EDIT",
                "message": (
                    f"Direkte Änderung an generiertem Artefakt '{path}' erkannt. "
                    "docs/_generated/* darf nicht direkt editiert werden."
                ),
                "path": path,
            })
    return findings


def check_roadmap_done_without_claim(
    changed_paths: list[str],
) -> list[dict[str, str]]:
    """
    Erkennt neue oder geänderte Roadmap-Haken ([x]) ohne Claim-/Proof-Bezug
    in geänderten Dateien unter docs/.
    """
    findings: list[dict[str, str]] = []
    for path in changed_paths:
        norm = path.replace("\\", "/")
        if not (norm.startswith("docs/") and norm.endswith(".md")):
            continue
        if not os.path.isfile(path):
            # Pfad existiert nicht lokal — nur melden wenn nicht gelöscht
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if _DONE_CHECKBOX_RE.search(line):
                if not _DONE_CLAIM_HINT_RE.search(line):
                    findings.append({
                        "code": "ROADMAP_DONE_WITHOUT_CLAIM",
                        "message": (
                            f"Roadmap-Haken '[x]' in '{path}':{lineno} "
                            "ohne Claim-/Proof-Bezug"
                        ),
                        "path": path,
                        "line": str(lineno),
                    })
    return findings


def check_status_done_without_proof(
    changed_paths: list[str],
) -> list[dict[str, str]]:
    """
    Erkennt 'status: done' in YAML-/JSON-Dateien unter docs/tasks/ und docs/reports/
    ohne proof_ref oder Claim-Bezug in derselben Zeile oder der nächsten Zeile.
    """
    findings: list[dict[str, str]] = []
    for path in changed_paths:
        norm = path.replace("\\", "/")
        in_scope = any(
            _is_under_allowed_path(norm, scope_prefix)
            for scope_prefix in ("docs/tasks/", "docs/reports/")
        )
        if not in_scope:
            continue
        if not norm.endswith((".yaml", ".yml", ".json")):
            continue
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError:
            continue
        for lineno, line in enumerate(lines, 1):
            if _DONE_STATUS_RE.search(line):
                # Prüfe die aktuelle und die nächste Zeile auf Proof-Hinweise
                context = line
                if lineno < len(lines):
                    context += lines[lineno]
                if not _DONE_CLAIM_HINT_RE.search(context):
                    findings.append({
                        "code": "STATUS_DONE_WITHOUT_PROOF",
                        "message": (
                            f"'status: done' in '{path}':{lineno} "
                            "ohne proof_ref / Claim-Bezug"
                        ),
                        "path": path,
                        "line": str(lineno),
                    })
    return findings


def check_workflow_change_task_type(
    changed_paths: list[str], task_type: str
) -> list[dict[str, str]]:
    """Prüft, ob Workflow-Änderungen task_type: ci_change deklarieren."""
    findings: list[dict[str, str]] = []
    has_workflow_change = any(
        p.replace("\\", "/").startswith(WORKFLOW_PREFIX) for p in changed_paths
    )
    if has_workflow_change and task_type != "ci_change":
        findings.append({
            "code": "WORKFLOW_CHANGE_WITHOUT_TASK_TYPE",
            "message": (
                "Änderungen an .github/workflows/ erfordern task_type: ci_change, "
                f"gefunden: '{task_type}'"
            ),
        })
    return findings


def check_infra_change_without_proof(
    changed_paths: list[str], task: dict[str, Any]
) -> list[dict[str, str]]:
    """Prüft, ob Infra-/Deploy-Änderungen task_type und Proof-Erwartung aufweisen."""
    findings: list[dict[str, str]] = []
    infra_paths = [
        p
        for p in changed_paths
        if any(p.replace("\\", "/").startswith(prefix) for prefix in INFRA_PREFIXES)
    ]
    if not infra_paths:
        return findings

    task_type = task.get("task_type", "")
    has_proof = bool(
        task.get("proof_ref")
        or task.get("expected_evidence")
        or task.get("evidence")
    )

    if task_type not in ("infra_change", "deploy_change") or not has_proof:
        for path in infra_paths:
            findings.append({
                "code": "INFRA_CHANGE_WITHOUT_PROOF",
                "message": (
                    f"Infra-/Deploy-Pfad '{path}' geändert, aber task_type "
                    f"('{task_type}') ist nicht 'infra_change'/'deploy_change' "
                    "oder proof/evidence fehlt"
                ),
                "path": path,
            })
    return findings


def check_delete_without_permission(
    deleted_paths: list[str], task: dict[str, Any]
) -> list[dict[str, str]]:
    """Prüft, ob Löschungen explizit erlaubt sind."""
    findings: list[dict[str, str]] = []
    if not deleted_paths:
        return findings

    delete_allowed_raw = task.get("delete_allowed", "false")
    delete_allowed = str(delete_allowed_raw).lower() in ("true", "yes", "1")

    if not delete_allowed:
        for path in deleted_paths:
            findings.append({
                "code": "DELETE_WITHOUT_PERMISSION",
                "message": (
                    f"Löschung von '{path}' erkannt, aber delete_allowed ist nicht 'true'"
                ),
                "path": path,
            })
    return findings


# ---------------------------------------------------------------------------
# Haupt-Preflight
# ---------------------------------------------------------------------------


def run_preflight(
    task: dict[str, Any],
    changed_paths: list[str] | None = None,
    deleted_paths: list[str] | None = None,
) -> list[dict[str, str]]:
    """
    Führt alle Preflight-Checks aus und gibt eine Liste von Befunden zurück.
    Leere Liste = keine Befunde.
    """
    changed = changed_paths or []
    deleted = deleted_paths or []
    all_changed = changed + deleted

    findings: list[dict[str, str]] = []

    findings.extend(check_task_metadata(task))

    allowed_paths: list[str] = task.get("allowed_paths", [])
    if isinstance(allowed_paths, str):
        allowed_paths = [allowed_paths]

    task_type: str = task.get("task_type", "") or ""

    findings.extend(check_path_scope(all_changed, allowed_paths))
    findings.extend(check_generated_direct_edit(all_changed))
    findings.extend(check_roadmap_done_without_claim(changed))
    findings.extend(check_status_done_without_proof(changed))
    findings.extend(check_workflow_change_task_type(all_changed, task_type))
    findings.extend(check_infra_change_without_proof(all_changed, task))
    findings.extend(check_delete_without_permission(deleted, task))

    return findings


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = _PreflightArgumentParser(
        description=(
            "Safety-Preflight Guard (AGENT-SAFE-001, report-only). "
            "Prüft agentische Änderungen deterministisch auf bekannte Fehlermuster."
        )
    )
    parser.add_argument(
        "--task-file",
        required=True,
        metavar="PATH",
        help="Pfad zur Task-YAML-Datei mit Pflichtfeldern",
    )
    parser.add_argument(
        "--changed-paths",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Liste geänderter Dateipfade",
    )
    parser.add_argument(
        "--deleted-paths",
        nargs="*",
        default=[],
        metavar="PATH",
        help="Liste gelöschter Dateipfade",
    )
    parser.add_argument(
        "--mode",
        choices=["report-only", "warn"],
        default="report-only",
        help=(
            "report-only: Befunde ausgeben, immer exit 0. "
            "warn: Befunde ausgeben, exit 1 wenn Befunde vorhanden."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except ValueError as exc:
        print(
            json.dumps({"error": f"Ungültiger Aufruf: {exc}"}, ensure_ascii=False),
            file=sys.stderr,
        )
        return 2
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 2
        return code if code == 0 else 2

    if not os.path.isfile(args.task_file):
        print(
            json.dumps(
                {"error": f"Task-Datei nicht gefunden: {args.task_file}"},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 2

    task = _parse_simple_yaml(args.task_file)

    findings = run_preflight(
        task=task,
        changed_paths=args.changed_paths,
        deleted_paths=args.deleted_paths,
    )

    result = {
        "mode": args.mode,
        "task_file": args.task_file,
        "findings_count": len(findings),
        "findings": findings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if findings:
        print(
            f"\n[preflight] {len(findings)} Befund(e) gefunden. "
            f"Modus: {args.mode}.",
            file=sys.stderr,
        )

    if args.mode == "warn" and findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

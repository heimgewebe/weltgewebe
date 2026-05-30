"""
agent_entrypoint_smoke.py — Agent-entrypoint / roadmap-sync smoke check (no writes).

Companion to scripts/docmeta/generate_task_index.py. While that script checks
*task-control* drift (board.md <-> index.json <-> optimierungsstatus.json), this
one checks that the *agent entrypoints* and the Task-Control / roadmap status do
not obviously diverge.

It deliberately verifies only a few hard, deterministic invariants — robust text
markers, not semantic full-text analysis — so that legitimate doc rewrites are
not punished:

  1. README.md spells out the binding reading order (repo.meta.yaml, AGENTS.md,
     agent-policy.yaml, docs/policies/agent-reading-protocol.md, docs/index.md).
  2. AGENTS.md references the Agent Reading Protocol and carries the reading
     order (repo.meta.yaml before agent-policy.yaml).
  3. docs/policies/agent-reading-protocol.md carries the same start order
     (repo.meta.yaml, AGENTS.md, agent-policy.yaml).
  4. docs/index.md marks itself as navigation, not a truth layer.
  5. docs/tasks/README.md frames docs/tasks/ as work control (not a second truth
     layer) and describes `generate_task_index.py --check` as a write-free drift
     mechanism.
  6. README.md must not still claim that the Task-Index generator AND the CI
     guard are both open follow-up work once the check script and workflow exist.
  7. docs/roadmap.md must not still carry "Statusbeleg ausstehend" for the
     "Dokumentationsstruktur & Task-Steuerung" row once the task-control README
     and CI workflow exist.
  8. README.md and the reading protocol must keep describing docs/_generated/* as
     diagnostic (never a manual target / truth layer).

Usage:
    python3 -m scripts.docmeta.agent_entrypoint_smoke

Exit codes:
    0  all invariants hold
    1  drift found

No files are written in any mode. Drift is printed to stderr.
"""
import argparse
import os
import re
import sys

from scripts.docmeta.docmeta import REPO_ROOT

README = "README.md"
AGENTS = "AGENTS.md"
PROTOCOL = "docs/policies/agent-reading-protocol.md"
INDEX = "docs/index.md"
ROADMAP = "docs/roadmap.md"
TASKS_README = "docs/tasks/README.md"
TASK_INDEX_SCRIPT = "scripts/docmeta/generate_task_index.py"
TASK_INDEX_WORKFLOW = ".github/workflows/task-index.yml"

# Reading-order entries that README.md must reference explicitly.
READING_ORDER_TOKENS = (
    "repo.meta.yaml",
    "agents.md",
    "agent-policy.yaml",
    "docs/policies/agent-reading-protocol.md",
    "docs/index.md",
)

# Words that frame a thing as not-yet-done. Used only in combination with very
# specific subject tokens, so broad markers here stay safe from false positives.
OPENNESS_MARKERS = (
    "offen",
    "ausstehend",
    "noch nicht",
    "nächste priorität",
    "naechste prioritaet",
    "geplant",
    "fehlt",
    "fehlen",
)


def _read_text(repo_root, rel_path):
    """Return (text, error). error is None on success."""
    path = os.path.join(repo_root, rel_path)
    if not os.path.isfile(path):
        return None, f"{rel_path}: file not found, required for agent-entrypoint sync"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read(), None
    except OSError as e:
        return None, f"{rel_path}: cannot read file: {e}"


def _norm(text):
    """Lowercase and collapse all whitespace to single spaces."""
    return re.sub(r"\s+", " ", text).strip().lower()


def _exists(repo_root, rel_path):
    return os.path.isfile(os.path.join(repo_root, rel_path))


def _has_openness_marker(norm_line):
    # Word boundary for 'offen' so 'offene', 'betroffen' or 'offensichtlich'
    # do not count; the other markers are distinctive enough as substrings.
    if re.search(r"\boffen\b", norm_line):
        return True
    return any(marker in norm_line for marker in OPENNESS_MARKERS if marker != "offen")


def _first_index(norm_text, token):
    return norm_text.find(token)


def _strip_frontmatter(text):
    """Drop a leading YAML frontmatter block so body-order checks ignore it."""
    if text.startswith("---"):
        parts = text.split("\n---", 2)
        if len(parts) >= 2:
            # Everything after the closing fence of the first block.
            return parts[1].split("\n", 1)[1] if "\n" in parts[1] else ""
    return text


def _extract_reading_order_block(text):
    """
    Return the README reading-order block, not the whole README.
    The guard must prove the binding list itself, because the same paths may
    appear elsewhere in README quick links or status paragraphs.

    Looks for a section marker containing "leseordnung" or "reading order" and
    returns everything from that marker to the next Markdown heading or EOF.
    """
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        n = _norm(line)
        if "leseordnung" in n or "reading order" in n:
            start = i
            break
    if start is None:
        return ""
    block = []
    for line in lines[start:]:
        # Stop at the next Markdown heading after the block has started.
        if block and re.match(r"^#{1,6}\s+", line):
            break
        block.append(line)
    return "\n".join(block)


def check_readme_reading_order(repo_root):
    text, err = _read_text(repo_root, README)
    if err:
        return [err]
    block = _extract_reading_order_block(text)
    norm = _norm(block)
    errors = []
    if not block:
        errors.append("README.md: missing reading-order block")
        return errors
    positions = []
    for token in READING_ORDER_TOKENS:
        idx = norm.find(token)
        if idx == -1:
            errors.append(f"README.md: missing reading-order entry: {token}")
        else:
            positions.append((token, idx))
    if not errors:
        ordered = [idx for _token, idx in positions]
        if ordered != sorted(ordered):
            errors.append("README.md: reading order is out of sequence")
    return errors


def check_agents_reading_protocol(repo_root):
    text, err = _read_text(repo_root, AGENTS)
    if err:
        return [err]
    norm = _norm(text)
    errors = []
    if "agent-reading-protocol" not in norm and "agent reading protocol" not in norm:
        errors.append("AGENTS.md: missing reference to the Agent Reading Protocol")
    if "reading order" not in norm and "lesereihenfolge" not in norm:
        errors.append("AGENTS.md: missing 'Reading Order' section marker")
    for token in ("repo.meta.yaml", "agent-policy.yaml", "agent-reading-protocol.md"):
        if token not in norm:
            errors.append(f"AGENTS.md: reading order does not mention {token}")
    body = _norm(_strip_frontmatter(text))
    meta_idx = _first_index(body, "repo.meta.yaml")
    policy_idx = _first_index(body, "agent-policy.yaml")
    if meta_idx != -1 and policy_idx != -1 and meta_idx > policy_idx:
        errors.append(
            "AGENTS.md: reading order is out of sequence "
            "(repo.meta.yaml must precede agent-policy.yaml)"
        )
    return errors


def check_protocol_reading_order(repo_root):
    text, err = _read_text(repo_root, PROTOCOL)
    if err:
        return [err]
    norm = _norm(text)
    errors = []
    if "reading order" not in norm and "lesereihenfolge" not in norm:
        errors.append("docs/policies/agent-reading-protocol.md: missing reading-order section marker")
    for token in ("repo.meta.yaml", "agents.md", "agent-policy.yaml"):
        if token not in norm:
            errors.append(
                f"docs/policies/agent-reading-protocol.md: start order does not mention {token}"
            )
    body = _norm(_strip_frontmatter(text))
    meta_idx = _first_index(body, "repo.meta.yaml")
    policy_idx = _first_index(body, "agent-policy.yaml")
    if meta_idx != -1 and policy_idx != -1 and meta_idx > policy_idx:
        errors.append(
            "docs/policies/agent-reading-protocol.md: start order is out of sequence "
            "(repo.meta.yaml must precede agent-policy.yaml)"
        )
    return errors


def check_index_navigation_marker(repo_root):
    text, err = _read_text(repo_root, INDEX)
    if err:
        return [err]
    norm = _norm(text)
    # "navigation ... (keine|nicht) ... wahrheit" in either order.
    forward = re.search(r"navigation[^.\n]{0,160}(keine?|nicht)[^.\n]{0,80}wahrheit", norm)
    backward = re.search(r"(keine?|nicht)[^.\n]{0,80}wahrheit[^.\n]{0,160}navigation", norm)
    if not (forward or backward):
        return ["docs/index.md: missing navigation-not-truth marker"]
    return []


def check_tasks_readme_markers(repo_root):
    text, err = _read_text(repo_root, TASKS_README)
    if err:
        return [err]
    norm = _norm(text)
    errors = []
    work_control = "arbeitssteuerung" in norm
    not_truth = bool(re.search(r"kein[a-zäöü ]*wahrheitsschicht", norm))
    if not (work_control and not_truth):
        errors.append(
            "docs/tasks/README.md: missing 'work-control, not a second truth layer' marker"
        )
    has_check = "generate_task_index" in norm and "--check" in norm and "drift" in norm
    write_free = (
        "ohne schreibzugriff" in norm
        or "keine dateien geschrieben" in norm
        or "kein schreiben" in norm
        or "schreibt keine dateien" in norm
    )
    if not (has_check and write_free):
        errors.append(
            "docs/tasks/README.md: missing write-free '--check' drift-mechanism description"
        )
    return errors


def check_readme_task_control_status(repo_root):
    # Only enforce once the machinery actually exists.
    if not (_exists(repo_root, TASK_INDEX_SCRIPT) and _exists(repo_root, TASK_INDEX_WORKFLOW)):
        return []
    text, err = _read_text(repo_root, README)
    if err:
        return [err]
    errors = []
    for raw in text.splitlines():
        line = _norm(raw)
        if "task-index-generator" in line and "ci-guard" in line and _has_openness_marker(line):
            errors.append(
                "README.md: stale Task-Control statement: Task-Index-Generator und CI-Guard "
                "werden als offen geführt, obwohl scripts/docmeta/generate_task_index.py (--check) "
                f"und .github/workflows/task-index.yml existieren: '{raw.strip()}'"
            )
    return errors


def check_roadmap_task_control_status(repo_root):
    if not (_exists(repo_root, TASKS_README) and _exists(repo_root, TASK_INDEX_WORKFLOW)):
        return []
    text, err = _read_text(repo_root, ROADMAP)
    if err:
        return [err]
    errors = []
    for raw in text.splitlines():
        line = _norm(raw)
        if "task-steuerung" in line and "statusbeleg" in line and "ausstehend" in line:
            errors.append(
                "docs/roadmap.md: stale Task-Control status proof statement: die Zeile "
                "'Dokumentationsstruktur & Task-Steuerung' führt noch 'Statusbeleg ausstehend', "
                "obwohl docs/tasks/README.md und .github/workflows/task-index.yml existieren: "
                f"'{raw.strip()}'"
            )
    return errors


def check_generated_diagnostic_marker(repo_root):
    errors = []
    for rel_path in (README, PROTOCOL):
        text, err = _read_text(repo_root, rel_path)
        if err:
            errors.append(err)
            continue
        norm = _norm(text)
        if "_generated" not in norm:
            errors.append(
                f"{rel_path}: docs/_generated/* is not mentioned; "
                "must describe it as diagnostic / not a truth layer"
            )
            continue
        marker = re.search(
            r"_generated[^.\n]{0,120}"
            r"("
            r"diagnose|diagnostic"
            r"|nicht ursprung|nicht kanonisch|niemals kanonisch|never canonical"
            r"|keine?[^.\n]{0,40}wahrheitsschicht"
            r"|not[^.\n]{0,40}truth[^.\n]{0,20}layer"
            r")",
            norm,
        )
        if not marker:
            errors.append(
                f"{rel_path}: docs/_generated/* is mentioned without a diagnostic / "
                "not-a-truth-layer marker"
            )
    return errors


CHECKS = (
    check_readme_reading_order,
    check_agents_reading_protocol,
    check_protocol_reading_order,
    check_index_navigation_marker,
    check_tasks_readme_markers,
    check_readme_task_control_status,
    check_roadmap_task_control_status,
    check_generated_diagnostic_marker,
)


def run_checks(repo_root):
    """Run all invariants and return a sorted list of drift messages."""
    errors = []
    for check in CHECKS:
        errors.extend(check(repo_root))
    return sorted(errors)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="agent_entrypoint_smoke",
        description=(
            "Check that agent entrypoints (README, AGENTS, Agent Reading Protocol, "
            "docs/index.md) and the Task-Control / roadmap status stay in sync. "
            "No files are written."
        ),
    )
    parser.parse_args(argv)

    errors = run_checks(REPO_ROOT)

    if errors:
        print(f"\n--- Agent-Entrypoint Drift ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"  DRIFT: {error}", file=sys.stderr)
        print(f"\nAgent-entrypoint smoke check failed: {len(errors)} issue(s).", file=sys.stderr)
        return 1

    print("Agent-entrypoint smoke check passed (0 issues).")
    return 0


if __name__ == "__main__":
    sys.exit(main())

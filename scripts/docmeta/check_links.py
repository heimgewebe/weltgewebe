import json
import os
import re
import subprocess
import sys
from pathlib import Path

from scripts.docmeta.docmeta import (
    REPO_ROOT,
    parse_frontmatter,
    parse_repo_index,
    parse_review_policy,
)

RETIRED_STATUSES = {"archived", "deprecated", "obsolete", "retired", "superseded"}
RETIRED_LIFECYCLE_STATES = {"archived", "deprecated", "obsolete", "retired", "superseded"}
CURRENT_STATUSES = {"active", "canonical"}
CURRENT_LIFECYCLE_STATES = {"active", "deferred"}
EXTERNAL_COMMIT_BINDING_RE = re.compile(
    r"\b[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+@[0-9a-f]{40}\b"
)
EXTERNAL_REPO_CONTEXT_RE = re.compile(
    r"\b(?:public|external|extern(?:e|en|er|es)?)\b.{0,100}\b(?:repository|repo|repositorys)\b",
    re.IGNORECASE,
)
SCOPE_POLICY_CONTEXT_RE = re.compile(
    r"\b(?:forbidden|guarded|policy-scope|human review required|menschliches review|pfadgruppe|target-proof erforderlich|never generator targets)\b",
    re.IGNORECASE,
)
HOSTNAME_PATH_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*\.)[A-Za-z]{2,}/")
INLINE_CODE_RE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
PATH_FILE_RE = re.compile(r"(?:^|/)[^/]+\.[A-Za-z0-9]{1,12}$")
NONLIVE_CONTEXT_RE = re.compile(
    r"\b(?:zielbild|geplant|planung|später|zukünftig|verboten|beispiel|optional|laufzeitrelativ|historisch|superseded|gegenhypothese)\b"
    r"|\bz\.?\s*[.\u202f ]?b\.?\b"
    r"|\bbevor\b.{0,120}\bimplementiert\b"
    r"|\bnicht\b.{0,80}\b(?:reale|existierende|vorhanden(?:e)?)\b"
    r"|(?:^|\n)\s*-\s*\[\s\]",
    re.IGNORECASE,
)
HISTORICAL_DOC_TYPES = {"changelog"}


def _tracked_markdown_files(root: str) -> list[str]:
    # Mandatory discovery is fail-closed: a broken/missing Git checkout must
    # never be converted into an apparently successful empty scan.
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md"],
        cwd=root,
        capture_output=True,
        check=True,
    )
    return sorted(
        item.decode("utf-8")
        for item in completed.stdout.split(b"\0")
        if item
    )


def _is_current_document(frontmatter: dict | None) -> bool:
    if not frontmatter:
        return False
    status = str(frontmatter.get("status", "")).strip().lower()
    lifecycle_state = str(frontmatter.get("lifecycle_state", "")).strip().lower()
    doc_type = str(frontmatter.get("doc_type", "")).strip().lower()
    if doc_type in HISTORICAL_DOC_TYPES:
        return False
    if status in RETIRED_STATUSES or lifecycle_state in RETIRED_LIFECYCLE_STATES:
        return False
    return status in CURRENT_STATUSES or lifecycle_state in CURRENT_LIFECYCLE_STATES


def _paragraph_for_offset(content: str, offset: int) -> str:
    start = content.rfind("\n\n", 0, offset)
    end = content.find("\n\n", offset)
    return content[(start + 2 if start >= 0 else 0) : (end if end >= 0 else len(content))]


def _explicitly_nonlive_context(paragraph: str) -> bool:
    return bool(
        EXTERNAL_COMMIT_BINDING_RE.search(paragraph)
        or EXTERNAL_REPO_CONTEXT_RE.search(paragraph)
        or NONLIVE_CONTEXT_RE.search(paragraph)
        or SCOPE_POLICY_CONTEXT_RE.search(paragraph)
    )


def _normalize_inline_path(value: str) -> str | None:
    token = value.strip().strip(",;:()[]{}<>'\"")
    if not token or any(ch.isspace() for ch in token):
        return None
    if token.startswith(("http://", "https://", "mailto:", "tel:", "doc:")):
        return None
    if "://" in token or "=" in token or HOSTNAME_PATH_RE.match(token):
        return None
    if token.startswith(("$", "-", "~", "/")):
        # Absolute/runtime paths are not repository-internal path claims.
        return None
    if any(ch in token for ch in ("*", "{", "}", "|", "<", ">")):
        return None
    if EXTERNAL_COMMIT_BINDING_RE.search(token) or ("@" in token and ":" in token):
        return None
    if "/" not in token:
        return None
    # Treat path-shaped relative inline code independently of whether its first
    # component already exists. Otherwise a typo such as `apss/api/x.rs` or a
    # package-relative claim such as `src/lib.rs` would evade the truth gate.
    if not (token.endswith("/") or PATH_FILE_RE.search(token)):
        return None
    return token.split("#", 1)[0]


def _path_within_repository(root: str, path: str) -> bool:
    root_abs = os.path.abspath(root)
    path_abs = os.path.abspath(path)
    try:
        return os.path.commonpath((root_abs, path_abs)) == root_abs
    except ValueError:
        return False


def _path_exists_within_repository(root: str, path: str) -> bool:
    return _path_within_repository(root, path) and os.path.exists(os.path.abspath(path))


def _path_is_git_ignored(root: str, path: str) -> bool:
    if not _path_within_repository(root, path):
        return False
    root_abs = os.path.abspath(root)
    relative = os.path.relpath(os.path.abspath(path), root_abs)
    for probe in (relative, f"{relative.rstrip('/')}/.wgx-ignore-probe"):
        completed = subprocess.run(
            ["git", "check-ignore", "-q", "--", probe],
            cwd=root_abs,
            capture_output=True,
        )
        if completed.returncode == 0:
            return True
        if completed.returncode not in {0, 1}:
            raise subprocess.CalledProcessError(
                completed.returncode,
                completed.args,
                output=completed.stdout,
                stderr=completed.stderr,
            )
    return False


def _inline_path_findings(
    root: str,
    rel_file_path: str,
    content: str,
    *,
    ignored_path_predicate=None,
) -> tuple[int, list[str]]:
    if os.path.basename(rel_file_path).casefold() == "changelog.md":
        return 0, []
    frontmatter = parse_frontmatter(os.path.join(root, rel_file_path))
    if not _is_current_document(frontmatter):
        return 0, []

    total = 0
    broken: list[str] = []
    doc_dir = os.path.dirname(os.path.join(root, rel_file_path))

    for match in INLINE_CODE_RE.finditer(content):
        candidate = _normalize_inline_path(match.group(1))
        if not candidate:
            continue
        paragraph = _paragraph_for_offset(content, match.start())
        if _explicitly_nonlive_context(paragraph):
            continue

        total += 1
        doc_relative = os.path.abspath(os.path.join(doc_dir, candidate))
        repo_relative = os.path.abspath(os.path.join(root, candidate))
        ignored = ignored_path_predicate or (lambda _path: False)
        if not (
            _path_exists_within_repository(root, doc_relative)
            or _path_exists_within_repository(root, repo_relative)
            or ignored(doc_relative)
            or ignored(repo_relative)
        ):
            broken.append(candidate)

    return total, sorted(set(broken))


def _extract_markdown_url(link_content: str) -> tuple[str | None, str | None]:
    link_content = link_content.strip()
    if link_content.startswith("<"):
        end_idx = link_content.find(">")
        if end_idx == -1:
            return None, "missing '>'"
        return link_content[1:end_idx], None
    if not link_content:
        return None, "empty link"
    return link_content.split()[0], None


def main() -> None:
    try:
        policy = parse_review_policy()
        strict_mode = policy.get("strict_manifest", False)
        mode = policy.get("mode", "warn")
        repo_index = parse_repo_index(strict_manifest=strict_mode)
    except ValueError as exc:
        print(f"Error parsing manifest/policy: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    errors: list[str] = []
    warnings: list[str] = []
    link_report: dict = {}

    def report_issue(msg: str) -> None:
        if mode in {"strict", "fail-closed"}:
            errors.append(msg)
        else:
            warnings.append(msg)

    docs_index_path = os.path.join(REPO_ROOT, "artifacts", "docmeta", "docs.index.json")
    valid_doc_ids: set[str] = set()
    docs_index_exists = os.path.exists(docs_index_path)
    if docs_index_exists:
        with open(docs_index_path, "r", encoding="utf-8") as f:
            docs_data = json.load(f)
        valid_doc_ids.update(
            str(doc.get("id"))
            for doc in docs_data.get("docs", [])
            if doc.get("id")
        )

    doc_links_found = False

    # Preserve the established canonical Markdown-link contract and its
    # document-relative resolution semantics.
    for zone_data in repo_index.get("zones", {}).values():
        rel_zone_path = zone_data.get("path", "")
        zone_path = os.path.join(REPO_ROOT, rel_zone_path)
        for doc_file in zone_data.get("canonical_docs", []):
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            file_path = os.path.join(zone_path, doc_file)
            if not os.path.exists(file_path):
                continue
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            info = link_report.setdefault(
                rel_file_path,
                {
                    "total_links": 0,
                    "broken_links": [],
                    "inline_paths_total": 0,
                    "broken_inline_paths": [],
                },
            )
            links = re.findall(r"(?<!\!)\[.*?\]\((.*?)\)", content)
            for link_content in links:
                url, malformed = _extract_markdown_url(link_content)
                if malformed:
                    errors.append(
                        f"Malformed link in '{rel_file_path}': {malformed} in '{link_content}'"
                    )
                    continue
                assert url is not None
                if url.startswith(("http://", "https://", "mailto:", "tel:")):
                    continue
                if url.startswith("#"):
                    continue
                raw_url = url
                file_url = raw_url.split("#", 1)[0]
                if not file_url:
                    continue
                info["total_links"] += 1

                if raw_url.startswith("doc:"):
                    doc_links_found = True
                    target_id = raw_url[4:].split("#", 1)[0]
                    if not target_id:
                        report_issue(
                            f"Malformed doc: link in '{rel_file_path}': missing canonical ID in '{raw_url}'."
                        )
                        info["broken_links"].append(raw_url)
                    elif docs_index_exists and target_id not in valid_doc_ids:
                        report_issue(
                            f"Broken link in '{rel_file_path}': Canonical ID '{target_id}' does not exist."
                        )
                        info["broken_links"].append(raw_url)
                else:
                    target_path = os.path.abspath(
                        os.path.join(os.path.dirname(file_path), file_url)
                    )
                    if not os.path.exists(target_path):
                        report_issue(
                            f"Broken link in '{rel_file_path}': Target '{file_url}' does not exist."
                        )
                        info["broken_links"].append(raw_url)

    if doc_links_found and not docs_index_exists:
        report_issue(
            f"Docs index missing ('{docs_index_path}'); cannot validate doc: links; "
            "run export_docs_index first."
        )

    # T036 extension: validate inline repository-path claims in every tracked,
    # machine-marked current document. Historical/draft/external/future targets
    # are not silently turned into present repository claims.
    for rel_file_path in _tracked_markdown_files(REPO_ROOT):
        file_path = os.path.join(REPO_ROOT, rel_file_path)
        try:
            content = Path(file_path).read_text(encoding="utf-8")
        except OSError:
            continue
        total, broken = _inline_path_findings(
            REPO_ROOT,
            rel_file_path,
            content,
            ignored_path_predicate=lambda path: _path_is_git_ignored(REPO_ROOT, path),
        )
        if not total and not broken:
            continue
        info = link_report.setdefault(
            rel_file_path,
            {
                "total_links": 0,
                "broken_links": [],
                "inline_paths_total": 0,
                "broken_inline_paths": [],
            },
        )
        info["inline_paths_total"] = total
        info["broken_inline_paths"] = broken
        for candidate in broken:
            report_issue(
                f"Broken repository path in '{rel_file_path}': '{candidate}' resolves neither "
                "document-relative nor repository-relative."
            )

    artifacts_dir = os.path.join(REPO_ROOT, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)
    with open(os.path.join(artifacts_dir, "link_report.json"), "w", encoding="utf-8") as f:
        json.dump(link_report, f, indent=2, sort_keys=True)

    with open(os.path.join(artifacts_dir, "link_report.md"), "w", encoding="utf-8") as f:
        f.write("# Internal Link and Repository Path Report\n\n")
        f.write(
            "| Document | Internal Links | Broken Links | Inline Paths | Broken Inline Paths |\n"
        )
        f.write("|---|---:|---|---:|---|\n")
        for doc_path in sorted(link_report):
            info = link_report[doc_path]
            broken_links = "<br>".join(
                f"`{item}` 🔴" for item in info.get("broken_links", [])
            ) or "_None_"
            broken_paths = "<br>".join(
                f"`{item}` 🔴" for item in info.get("broken_inline_paths", [])
            ) or "_None_"
            f.write(
                f"| `{doc_path}` | {info.get('total_links', 0)} | {broken_links} | "
                f"{info.get('inline_paths_total', 0)} | {broken_paths} |\n"
            )

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)
        print(
            f"\nMode is {mode}. Documentation link/path check generated warnings "
            "but will not fail the build.",
            file=sys.stderr,
        )

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print(f"\nMode is {mode}. Failing build.", file=sys.stderr)
        raise SystemExit(1)

    if not warnings:
        print("Documentation link/path check passed (0 errors, 0 warnings).")


if __name__ == "__main__":
    main()

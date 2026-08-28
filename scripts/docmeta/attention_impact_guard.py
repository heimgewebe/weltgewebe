from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import yaml

from scripts.docmeta.docmeta import REPO_ROOT
from scripts.quality.attention_impact_contract import (
    attention_impact_decision,
    product_logic_changes,
    validate_attention_impact_markers,
)


def canonical_product_docs(repo_root: str | Path = REPO_ROOT) -> set[str]:
    root = Path(repo_root)
    manifest_path = root / "manifest" / "repo-index.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    zones = manifest.get("zones", {}) if isinstance(manifest, dict) else {}
    product = zones.get("product") if isinstance(zones, dict) else None
    if not isinstance(product, dict):
        raise ValueError("manifest must define zone 'product'")
    rel_path = product.get("path")
    docs = product.get("canonical_docs")
    if not isinstance(rel_path, str) or not rel_path.strip():
        raise ValueError("product zone must define a non-empty path")
    if not isinstance(docs, list) or not docs:
        raise ValueError("product zone must define canonical_docs")
    return {
        (Path(rel_path) / doc).as_posix()
        for doc in docs
        if isinstance(doc, str) and doc.strip()
    }


def evaluate_attention_impact(
    *,
    pr_body: str,
    changed_files: list[str],
    product_docs: set[str],
) -> list[str]:
    errors = validate_attention_impact_markers(
        pr_body=pr_body, changed_files=changed_files
    )
    if errors or not product_logic_changes(changed_files):
        return errors

    if attention_impact_decision(pr_body) == "contract":
        changed_product_docs = sorted(set(changed_files) & product_docs)
        if not changed_product_docs:
            errors.append(
                "Attention impact=contract requires at least one changed canonical "
                "product contract from manifest zone product"
            )
    return errors


def changed_files_between(
    base_sha: str,
    head_sha: str,
    repo_root: str | Path = REPO_ROOT,
) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_sha}...{head_sha}"],
        cwd=repo_root,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def pull_request_context_from_environment() -> tuple[str, str, str] | None:
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return None
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if not event_path:
        raise ValueError("GITHUB_EVENT_PATH is required for pull_request validation")
    event = json.loads(Path(event_path).read_text(encoding="utf-8"))
    pull_request = event.get("pull_request")
    if not isinstance(pull_request, dict):
        raise ValueError("GitHub event is missing pull_request")
    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("GitHub pull_request event is missing base/head")
    base_sha = base.get("sha")
    head_sha = head.get("sha")
    body = pull_request.get("body") or ""
    if not isinstance(base_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", base_sha):
        raise ValueError("GitHub pull_request base SHA is invalid")
    if not isinstance(head_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", head_sha):
        raise ValueError("GitHub pull_request head SHA is invalid")
    if not isinstance(body, str):
        raise ValueError("GitHub pull_request body must be text")
    return base_sha, head_sha, body


def main() -> int:
    try:
        context = pull_request_context_from_environment()
        if context is None:
            print("Attention impact guard skipped (not a pull_request context).")
            return 0
        base_sha, head_sha, pr_body = context
        changed_files = changed_files_between(base_sha, head_sha)
        product_docs = canonical_product_docs()
        errors = evaluate_attention_impact(
            pr_body=pr_body,
            changed_files=changed_files,
            product_docs=product_docs,
        )
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"Attention impact guard failed closed: {exc}", file=sys.stderr)
        return 1

    if errors:
        print("Attention impact guard failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        relevant = product_logic_changes(changed_files)
        if relevant:
            print("Product-logic changes:", file=sys.stderr)
            for path in relevant[:20]:
                print(f"  - {path}", file=sys.stderr)
            if len(relevant) > 20:
                print(f"  - ... and {len(relevant) - 20} more", file=sys.stderr)
        return 1

    print("Attention impact guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

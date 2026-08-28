from __future__ import annotations

from pathlib import PurePosixPath
import re
from typing import Iterable

PRODUCT_LOGIC_PREFIXES = ("apps/", "contracts/domain/")
IMPACT_RE = re.compile(
    r"<!--\s*weltgewebe-attention-impact:\s*(contract|none)\s*-->",
    re.IGNORECASE,
)
RATIONALE_RE = re.compile(
    r"<!--\s*weltgewebe-attention-rationale:\s*([^\r\n<>]+?)\s*-->",
    re.IGNORECASE,
)
SAFE_MANIFEST_SCALAR_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
MIN_RATIONALE_BYTES = 20
MAX_RATIONALE_BYTES = 500


def product_logic_changes(changed_files: Iterable[str]) -> list[str]:
    return sorted(
        path
        for path in changed_files
        if any(path.startswith(prefix) for prefix in PRODUCT_LOGIC_PREFIXES)
    )


def attention_impact_decision(pr_body: str) -> str | None:
    matches = IMPACT_RE.findall(pr_body or "")
    if len(matches) != 1:
        return None
    return matches[0].lower()


def _manifest_scalar(raw: str, *, field: str) -> str:
    value = raw.strip()
    if not value or not SAFE_MANIFEST_SCALAR_RE.fullmatch(value):
        raise ValueError(f"unsupported {field} scalar in trusted manifest")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe {field} path in trusted manifest")
    return value


def canonical_product_docs_from_manifest_text(text: str) -> set[str]:
    """Extract the trusted main product-zone doc set without a YAML dependency.

    The privileged review-evidence workflow intentionally executes only standard-
    library code from literal main. This parser accepts the repository's narrow
    manifest shape and fails closed when that shape becomes ambiguous.
    """

    lines = text.splitlines()
    product_markers = [index for index, line in enumerate(lines) if line == "  product:"]
    if len(product_markers) != 1:
        raise ValueError("trusted manifest must define exactly one product zone")

    start = product_markers[0] + 1
    end = len(lines)
    for index in range(start, len(lines)):
        line = lines[index]
        if line and line.startswith("  ") and not line.startswith("    "):
            end = index
            break

    product_path: str | None = None
    canonical_docs: list[str] = []
    in_canonical_docs = False
    saw_canonical_docs = False

    for line in lines[start:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith("    path:"):
            if product_path is not None:
                raise ValueError("trusted product zone defines path more than once")
            product_path = _manifest_scalar(
                line.split(":", 1)[1], field="product.path"
            )
            in_canonical_docs = False
            continue
        if line == "    canonical_docs:":
            if saw_canonical_docs:
                raise ValueError(
                    "trusted product zone defines canonical_docs more than once"
                )
            saw_canonical_docs = True
            in_canonical_docs = True
            continue
        if in_canonical_docs and line.startswith("      - "):
            canonical_docs.append(
                _manifest_scalar(line[8:], field="product.canonical_docs")
            )
            continue
        if line.startswith("    "):
            in_canonical_docs = False
            continue
        raise ValueError("unsupported indentation in trusted product zone")

    if product_path is None:
        raise ValueError("trusted product zone must define path")
    if not saw_canonical_docs or not canonical_docs:
        raise ValueError("trusted product zone must define canonical_docs")
    if len(set(canonical_docs)) != len(canonical_docs):
        raise ValueError("trusted product canonical_docs contains duplicates")

    prefix = product_path.rstrip("/")
    return {f"{prefix}/{doc}" for doc in canonical_docs}


def validate_attention_impact_markers(
    *, pr_body: str, changed_files: Iterable[str]
) -> list[str]:
    relevant = product_logic_changes(changed_files)
    if not relevant:
        return []

    impact_matches = IMPACT_RE.findall(pr_body or "")
    if len(impact_matches) != 1:
        return [
            "product logic changed but the PR body must contain exactly one "
            "Attention impact marker: "
            "<!-- weltgewebe-attention-impact: contract --> or "
            "<!-- weltgewebe-attention-impact: none -->"
        ]

    if impact_matches[0].lower() == "contract":
        return []

    rationale_matches = RATIONALE_RE.findall(pr_body or "")
    if len(rationale_matches) != 1:
        return [
            "Attention impact=none requires exactly one rationale marker: "
            "<!-- weltgewebe-attention-rationale: concrete reason -->"
        ]

    rationale = rationale_matches[0].strip()
    errors: list[str] = []
    rationale_bytes = len(rationale.encode("utf-8"))
    if not MIN_RATIONALE_BYTES <= rationale_bytes <= MAX_RATIONALE_BYTES:
        errors.append(
            "Attention impact rationale must be between "
            f"{MIN_RATIONALE_BYTES} and {MAX_RATIONALE_BYTES} UTF-8 bytes"
        )
    if any(ord(char) < 32 and char != "\t" for char in rationale):
        errors.append("Attention impact rationale contains control characters")
    return errors


def validate_attention_impact_contract_binding(
    *,
    pr_body: str,
    changed_files: Iterable[str],
    canonical_product_docs: Iterable[str],
) -> list[str]:
    changed = tuple(changed_files)
    errors = validate_attention_impact_markers(
        pr_body=pr_body, changed_files=changed
    )
    if errors or not product_logic_changes(changed):
        return errors

    if attention_impact_decision(pr_body) == "contract":
        changed_product_docs = sorted(set(changed) & set(canonical_product_docs))
        if not changed_product_docs:
            errors.append(
                "Attention impact=contract requires at least one changed canonical "
                "product contract from the canonical product zone"
            )
    return errors

from __future__ import annotations

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

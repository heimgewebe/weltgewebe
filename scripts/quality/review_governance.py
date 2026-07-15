#!/usr/bin/env python3
"""Generate and verify hash-bound Weltgewebe review evidence.

The module is intentionally standard-library only.  It is executed from the
trusted default branch by the review-evidence workflow; pull-request code is
never imported or executed by that workflow.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 1
MAX_ARTIFACT_BYTES = 100 * 1024 * 1024
MIN_REVIEW_REPORT_BYTES = 120
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
REPORT_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
RISK_ORDER = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
REQUIRED_REVIEWS = {"R0": 0, "R1": 1, "R2": 2, "R3": 2}
AUTHORIZED_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
HIGH_RISK_AXES = {
    "security",
    "privacy",
    "data-integrity",
    "concurrency",
    "migration",
    "operations",
}
ALLOWED_AXES = HIGH_RISK_AXES | {
    "correctness",
    "regression",
    "architecture",
    "maintainability",
    "accessibility",
    "user-experience",
    "testing",
}
RISK_RE = re.compile(r"<!--\s*weltgewebe-risk:\s*(R[0-3])\s*-->", re.IGNORECASE)
EVIDENCE_RE = re.compile(
    r"<!--\s*weltgewebe-review-evidence\s*(\{.*?\})\s*-->",
    re.IGNORECASE | re.DOTALL,
)


class GovernanceError(RuntimeError):
    """A fail-closed governance error."""


def load_allowed_attesters(path: Path) -> frozenset[str]:
    raw = _load_json(path)
    required = {"schema_version", "allowed_attesters"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise GovernanceError(
            "attester authority file must contain exactly schema_version and allowed_attesters"
        )
    if raw["schema_version"] != SCHEMA_VERSION:
        raise GovernanceError("unsupported attester authority schema")
    values = raw["allowed_attesters"]
    if not isinstance(values, list) or not values:
        raise GovernanceError("allowed_attesters must be a non-empty list")
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str) or value != value.strip():
            raise GovernanceError("allowed_attesters contains an invalid login")
        if not GITHUB_LOGIN_RE.fullmatch(value):
            raise GovernanceError("allowed_attesters contains an invalid GitHub login")
        normalized.append(value.casefold())
    if len(set(normalized)) != len(normalized):
        raise GovernanceError("allowed_attesters must not contain duplicates")
    return frozenset(normalized)


@dataclass(frozen=True)
class DiffStats:
    changed_files: tuple[str, ...]
    additions: int
    deletions: int
    binary_files: tuple[str, ...]
    opaque_files: tuple[str, ...] = ()

    @property
    def changed_lines(self) -> int:
        return self.additions + self.deletions


@dataclass(frozen=True)
class Bundle:
    pr_number: int
    base_sha: str
    head_sha: str
    merge_base_sha: str
    diff_sha256: str
    patch_sha256: str
    manifest_path: Path
    diff_path: Path
    patch_path: Path
    request_path: Path
    stats: DiffStats


def _git(repo: Path, args: Sequence[str], *, text: bool = False) -> bytes | str:
    command = [
        "git",
        "-c",
        "core.pager=cat",
        "-c",
        "pager.diff=false",
        "-c",
        "diff.external=",
        "-c",
        "diff.trustExitCode=false",
        "-c",
        "core.fsmonitor=false",
        "-C",
        str(repo),
        *args,
    ]
    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=text,
    )
    if completed.returncode != 0:
        stderr = (
            completed.stderr if text else completed.stderr.decode("utf-8", "replace")
        )
        raise GovernanceError(
            f"git command failed ({completed.returncode}): {stderr.strip()}"
        )
    return completed.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _resolve_sha(repo: Path, revision: str) -> str:
    output = _git(repo, ["rev-parse", "--verify", f"{revision}^{{commit}}"], text=True)
    return str(output).strip()


def _diff_stats(repo: Path, base_sha: str, head_sha: str) -> DiffStats:
    range_spec = f"{base_sha}...{head_sha}"
    names_raw = _git(repo, ["diff", "--name-only", "-z", "--find-renames", range_spec])
    assert isinstance(names_raw, bytes)
    names = tuple(
        part.decode("utf-8", "surrogateescape")
        for part in names_raw.split(b"\0")
        if part
    )

    numstat_raw = _git(
        repo, ["diff", "--numstat", "--find-renames", range_spec], text=True
    )
    additions = 0
    deletions = 0
    binary: list[str] = []
    for line in str(numstat_raw).splitlines():
        fields = line.split("\t", 2)
        if len(fields) != 3:
            continue
        added, deleted, path = fields
        if added == "-" or deleted == "-":
            binary.append(path)
            continue
        additions += int(added)
        deletions += int(deleted)
    binary_files = tuple(binary)
    return DiffStats(
        names,
        additions,
        deletions,
        binary_files,
        binary_files,
    )


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "unknown"


def _canonical_json(data: Any) -> bytes:
    return (
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def parse_risk_class(pr_body: str) -> str | None:
    matches = [match.upper() for match in RISK_RE.findall(pr_body or "")]
    if len(matches) != 1:
        return None
    return matches[0]


def minimum_risk_for_paths(paths: Iterable[str]) -> str:
    minimum = "R0"
    for raw_path in paths:
        path = raw_path.lower()
        if (
            path.startswith(".github/workflows/")
            or path
            in {
                ".github/grabowski-required-checks.json",
                ".github/review-evidence-authorities.json",
                "scripts/quality/review_governance.py",
            }
            or path.startswith("infra/")
            or path.startswith("scripts/ops/")
            or "/migrations/" in f"/{path}"
            or any(
                token in path
                for token in ("auth", "security", "privacy", "session", "passkey")
            )
            or path.startswith("docs/deploy/")
            or path.startswith("docs/runbooks/")
        ):
            return "R3"
        if (
            path.startswith("apps/api/")
            or path.startswith("apps/web/")
            or path.startswith("src/")
            or path.startswith("scripts/")
            or path.startswith("tests/")
            or path.endswith(("cargo.lock", "pnpm-lock.yaml", "package-lock.json"))
            or path.endswith(
                (".rs", ".py", ".ts", ".tsx", ".js", ".mjs", ".svelte", ".sql", ".sh")
            )
        ):
            minimum = "R2"
        elif not path.endswith(".md"):
            minimum = max((minimum, "R1"), key=RISK_ORDER.__getitem__)
    return minimum


def _r0_scope_valid(stats: DiffStats) -> tuple[bool, str]:
    if stats.changed_lines > 50:
        return (
            False,
            f"R0 permits at most 50 changed lines, found {stats.changed_lines}",
        )
    unsafe = [path for path in stats.changed_files if not path.endswith(".md")]
    if unsafe:
        return False, f"R0 permits Markdown-only changes, found: {', '.join(unsafe)}"
    return True, ""


def _validate_binding(
    *, pr_number: int, base_sha: str, head_sha: str, merge_base_sha: str
) -> None:
    if pr_number < 1:
        raise GovernanceError("PR number must be a positive integer")
    for name, value in (
        ("base_sha", base_sha),
        ("head_sha", head_sha),
        ("merge_base_sha", merge_base_sha),
    ):
        if not SHA40_RE.fullmatch(value):
            raise GovernanceError(f"{name} must be a lowercase 40-character Git SHA")


def _validate_stats(stats: DiffStats) -> None:
    if stats.additions < 0 or stats.deletions < 0:
        raise GovernanceError("diff totals must be non-negative")
    if len(set(stats.changed_files)) != len(stats.changed_files):
        raise GovernanceError("changed_files must not contain duplicates")
    if len(set(stats.binary_files)) != len(stats.binary_files):
        raise GovernanceError("binary_files must not contain duplicates")
    if len(set(stats.opaque_files)) != len(stats.opaque_files):
        raise GovernanceError("opaque_files must not contain duplicates")
    if not set(stats.binary_files).issubset(stats.changed_files):
        raise GovernanceError("binary_files must be a subset of changed_files")
    if not set(stats.opaque_files).issubset(stats.changed_files):
        raise GovernanceError("opaque_files must be a subset of changed_files")
    for file_path in stats.changed_files:
        if (
            not isinstance(file_path, str)
            or not file_path
            or file_path != file_path.strip()
            or file_path.startswith("/")
            or any(part in {"", ".", ".."} for part in file_path.split("/"))
            or any(unicodedata.category(char).startswith("C") for char in file_path)
        ):
            raise GovernanceError("changed_files contains an invalid path")


def _build_bundle(
    *,
    output_dir: Path,
    pr_number: int,
    base_sha: str,
    head_sha: str,
    merge_base_sha: str,
    risk_class: str | None,
    diff_bytes: bytes,
    patch_bytes: bytes,
    stats: DiffStats,
    source: str,
) -> Bundle:
    _validate_binding(
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha,
    )
    _validate_stats(stats)
    if not diff_bytes:
        raise GovernanceError("review diff is empty")
    if not patch_bytes:
        raise GovernanceError("review patch is empty")
    if len(diff_bytes) > MAX_ARTIFACT_BYTES or len(patch_bytes) > MAX_ARTIFACT_BYTES:
        raise GovernanceError(
            f"review artifacts exceed the {MAX_ARTIFACT_BYTES}-byte safety limit"
        )
    diff_file_count = sum(
        1 for line in diff_bytes.splitlines() if line.startswith(b"diff --git ")
    )
    if diff_file_count != len(stats.changed_files):
        raise GovernanceError(
            "review diff file count does not match materialized changed-file list: "
            f"diff={diff_file_count}, metadata={len(stats.changed_files)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    diff_hash = _sha256(diff_bytes)
    patch_hash = _sha256(patch_bytes)
    stem = f"weltgewebe-pr-{pr_number}-{_safe_name(head_sha[:12])}-{diff_hash[:12]}"
    diff_path = output_dir / f"{stem}.diff"
    patch_path = output_dir / f"{stem}.patch"
    manifest_path = output_dir / f"{stem}.review.json"
    request_path = output_dir / f"{stem}.review-request.md"
    diff_path.write_bytes(diff_bytes)
    patch_path.write_bytes(patch_bytes)

    binding = {
        "pr_number": pr_number,
        "base_sha": base_sha,
        "head_sha": head_sha,
        "merge_base_sha": merge_base_sha,
        "diff_sha256": diff_hash,
        "risk_class": risk_class,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "weltgewebe-review-bundle",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "source": source,
        "binding": binding,
        "stats": {
            "changed_files": list(stats.changed_files),
            "changed_file_count": len(stats.changed_files),
            "additions": stats.additions,
            "deletions": stats.deletions,
            "binary_files": list(stats.binary_files),
            "opaque_files": list(stats.opaque_files),
        },
        "artifacts": {
            "diff": {
                "filename": diff_path.name,
                "sha256": diff_hash,
                "bytes": len(diff_bytes),
            },
            "patch": {
                "filename": patch_path.name,
                "sha256": patch_hash,
                "bytes": len(patch_bytes),
            },
        },
    }
    manifest_path.write_bytes(_canonical_json(manifest))

    opaque_note = ""
    if stats.opaque_files:
        opaque_note = (
            "\n- Nicht im GitHub-Textdiff dargestellte Dateien: "
            + ", ".join(f"`{item}`" for item in stats.opaque_files)
            + "\n"
        )
    request = f"""# Weltgewebe – exakter Reviewauftrag

Prüfe ausschließlich den beigefügten Diff. Frühere oder spätere Versionen zählen nicht.

- PR: #{pr_number}
- Risikoklasse: {risk_class or "FEHLT"}
- Basis-Commit: `{base_sha}`
- Head-Commit: `{head_sha}`
- Merge-Basis: `{merge_base_sha}`
- Diff-SHA-256: `{diff_hash}`
- Quelle: `{source}`
- Geänderte Dateien: {len(stats.changed_files)}
- Zeilen: +{stats.additions} / -{stats.deletions}
{opaque_note}
Bewerte mindestens eine klar benannte Achse, etwa `correctness`, `security`,
`data-integrity`, `concurrency`, `architecture`, `testing` oder `operations`.
Benenne konkrete Befunde. Ein PASS ist nur zulässig, wenn alle Mergeblocker behoben
oder nachvollziehbar widerlegt sind. Dateien ohne GitHub-Textdarstellung müssen
separat geprüft oder als offener Mergeblocker benannt werden.

Nach dem Review wird der vollständige Reviewtext als normaler Kommentartext
vor dem Marker hinterlegt. `report_sha256` ist der SHA-256 des getrimmten
UTF-8-Reviewtexts vor dem Marker. Danach folgt genau ein Belegblock:

```text
<VOLLSTÄNDIGER REVIEWTEXT>
<!-- weltgewebe-review-evidence
{{
  "schema_version": 1,
  "pr_number": {pr_number},
  "base_sha": "{base_sha}",
  "head_sha": "{head_sha}",
  "diff_sha256": "{diff_hash}",
  "risk_class": "{risk_class or "R?"}",
  "reviewer": "NAME DES PRÜFERS",
  "report_sha256": "SHA-256 DES REVIEWTEXTS VOR DEM MARKER",
  "review_axis": "correctness",
  "verdict": "PASS",
  "findings_resolved": true
}}
-->
```

Der Kommentar muss von einem freigegebenen GitHub-Attestierer stammen. Leere,
zu kurze, mehrfach markierte oder nicht zum Berichtshash passende Kommentare
zählen nicht. Jeder neue Push, Basiswechsel oder Diffwechsel entwertet den Beleg
automatisch.
"""
    request_path.write_text(request, encoding="utf-8")
    return Bundle(
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha,
        diff_sha256=diff_hash,
        patch_sha256=patch_hash,
        manifest_path=manifest_path,
        diff_path=diff_path,
        patch_path=patch_path,
        request_path=request_path,
        stats=stats,
    )


def generate_bundle(
    *,
    repo: Path,
    output_dir: Path,
    base_revision: str,
    head_revision: str,
    pr_number: int,
    risk_class: str | None,
) -> Bundle:
    repo = repo.resolve()
    base_sha = _resolve_sha(repo, base_revision)
    head_sha = _resolve_sha(repo, head_revision)
    merge_base = str(_git(repo, ["merge-base", base_sha, head_sha], text=True)).strip()
    range_spec = f"{base_sha}...{head_sha}"
    diff_bytes = _git(
        repo,
        [
            "diff",
            "--binary",
            "--full-index",
            "--find-renames",
            "--no-ext-diff",
            range_spec,
        ],
    )
    patch_bytes = _git(
        repo,
        [
            "format-patch",
            "--stdout",
            "--binary",
            "--full-index",
            "--no-signature",
            f"{merge_base}..{head_sha}",
        ],
    )
    assert isinstance(diff_bytes, bytes)
    assert isinstance(patch_bytes, bytes)
    return _build_bundle(
        output_dir=output_dir,
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base,
        risk_class=risk_class,
        diff_bytes=diff_bytes,
        patch_bytes=patch_bytes,
        stats=_diff_stats(repo, base_sha, head_sha),
        source="local-git-binary",
    )


def _materialized_metadata(path: Path) -> tuple[int, str, str, str, DiffStats]:
    raw = _load_json(path)
    if not isinstance(raw, dict):
        raise GovernanceError("materialized metadata must be a JSON object")
    required = {
        "schema_version",
        "pr_number",
        "base_sha",
        "head_sha",
        "merge_base_sha",
        "changed_file_count",
        "changed_files",
        "additions",
        "deletions",
        "opaque_files",
    }
    if set(raw) != required:
        missing = sorted(required - set(raw))
        extra = sorted(set(raw) - required)
        raise GovernanceError(
            f"materialized metadata keys mismatch; missing={missing}, extra={extra}"
        )
    schema_version = raw["schema_version"]
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        raise GovernanceError("unsupported materialized metadata schema")
    pr_number = raw["pr_number"]
    additions = raw["additions"]
    deletions = raw["deletions"]
    changed_file_count = raw["changed_file_count"]
    changed_files = raw["changed_files"]
    opaque_files = raw["opaque_files"]
    if not isinstance(pr_number, int) or isinstance(pr_number, bool):
        raise GovernanceError("materialized pr_number must be an integer")
    for name, value in (
        ("changed_file_count", changed_file_count),
        ("additions", additions),
        ("deletions", deletions),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise GovernanceError(f"materialized {name} must be a non-negative integer")
    if not isinstance(changed_files, list) or not all(
        isinstance(item, str) for item in changed_files
    ):
        raise GovernanceError("materialized changed_files must be a string list")
    if not isinstance(opaque_files, list) or not all(
        isinstance(item, str) for item in opaque_files
    ):
        raise GovernanceError("materialized opaque_files must be a string list")
    if changed_file_count != len(changed_files):
        raise GovernanceError(
            "materialized changed_file_count does not match file list"
        )
    stats = DiffStats(
        tuple(changed_files),
        additions,
        deletions,
        (),
        tuple(opaque_files),
    )
    base_sha = raw["base_sha"]
    head_sha = raw["head_sha"]
    merge_base_sha = raw["merge_base_sha"]
    if not all(
        isinstance(value, str) for value in (base_sha, head_sha, merge_base_sha)
    ):
        raise GovernanceError("materialized Git SHAs must be strings")
    _validate_binding(
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha,
    )
    _validate_stats(stats)
    return pr_number, base_sha, head_sha, merge_base_sha, stats


def generate_materialized_bundle(
    *,
    output_dir: Path,
    metadata_file: Path,
    diff_file: Path,
    patch_file: Path,
    risk_class: str | None,
) -> Bundle:
    pr_number, base_sha, head_sha, merge_base_sha, stats = _materialized_metadata(
        metadata_file
    )
    return _build_bundle(
        output_dir=output_dir,
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base_sha,
        risk_class=risk_class,
        diff_bytes=diff_file.read_bytes(),
        patch_bytes=patch_file.read_bytes(),
        stats=stats,
        source="github-pull-api",
    )


def _flatten_comments(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise GovernanceError("comments JSON must be a list")
    flattened: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, list):
            flattened.extend(entry for entry in item if isinstance(entry, dict))
        elif isinstance(item, dict):
            flattened.append(item)
    return flattened


def _evidence_blocks(comments: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for comment_index, comment in enumerate(comments):
        body = comment.get("body") or ""
        if not isinstance(body, str):
            continue
        matches = list(EVIDENCE_RE.finditer(body))
        for block_index, match in enumerate(matches):
            try:
                record = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            report_text = body[: match.start()].strip()
            report_bytes = report_text.encode("utf-8")
            record = dict(record)
            record["_comment_index"] = comment_index
            record["_block_index"] = block_index
            record["_comment_evidence_block_count"] = len(matches)
            record["_report_text_bytes"] = len(report_bytes)
            record["_report_text_sha256"] = _sha256(report_bytes)
            record["_author_association"] = str(
                comment.get("author_association") or ""
            ).upper()
            user = comment.get("user") or {}
            record["_comment_author"] = (
                user.get("login") if isinstance(user, dict) else None
            )
            record["_comment_url"] = comment.get("html_url")
            record["_updated_at"] = (
                comment.get("updated_at") or comment.get("created_at") or ""
            )
            evidence.append(record)
    return evidence


def evaluate_evidence(
    *,
    bundle: Bundle,
    risk_class: str | None,
    comments: Sequence[dict[str, Any]],
    allowed_attesters: frozenset[str],
) -> dict[str, Any]:
    if not allowed_attesters or any(
        not isinstance(login, str) or not GITHUB_LOGIN_RE.fullmatch(login)
        for login in allowed_attesters
    ):
        raise GovernanceError(
            "allowed_attesters must be a non-empty set of GitHub logins"
        )
    normalized_attesters = frozenset(login.casefold() for login in allowed_attesters)
    reasons: list[str] = []
    if risk_class is None:
        reasons.append(
            "PR body must contain exactly one risk marker: <!-- weltgewebe-risk: R0|R1|R2|R3 -->"
        )
        risk_class = "R3"

    if bundle.stats.opaque_files:
        reasons.append(
            "opaque or binary files require a separately verified artifact-review "
            "mechanism and currently block the review evidence gate: "
            + ", ".join(bundle.stats.opaque_files)
        )

    minimum_risk = minimum_risk_for_paths(bundle.stats.changed_files)
    if RISK_ORDER[risk_class] < RISK_ORDER[minimum_risk]:
        reasons.append(
            f"declared risk {risk_class} is below path-derived minimum {minimum_risk}"
        )
    if risk_class == "R0":
        valid, detail = _r0_scope_valid(bundle.stats)
        if not valid:
            reasons.append(detail)

    records = _evidence_blocks(comments)
    exact: list[dict[str, Any]] = []
    stale = 0
    unauthorized = 0
    malformed = 0
    for record in records:
        comment_author = str(record.get("_comment_author") or "").strip()
        if (
            record.get("_author_association") not in AUTHORIZED_ASSOCIATIONS
            or comment_author.casefold() not in normalized_attesters
        ):
            unauthorized += 1
            continue
        required_fields = {
            "schema_version",
            "pr_number",
            "base_sha",
            "head_sha",
            "diff_sha256",
            "risk_class",
            "reviewer",
            "report_sha256",
            "review_axis",
            "verdict",
            "findings_resolved",
        }
        external_fields = {key for key in record if not key.startswith("_")}
        if external_fields != required_fields:
            malformed += 1
            continue
        schema_version = record.get("schema_version")
        pr_number = record.get("pr_number")
        if (
            not isinstance(schema_version, int)
            or isinstance(schema_version, bool)
            or not isinstance(pr_number, int)
            or isinstance(pr_number, bool)
        ):
            malformed += 1
            continue
        if (
            schema_version != SCHEMA_VERSION
            or pr_number != bundle.pr_number
            or record.get("base_sha") != bundle.base_sha
            or record.get("head_sha") != bundle.head_sha
            or record.get("diff_sha256") != bundle.diff_sha256
            or str(record.get("risk_class", "")).upper() != risk_class
        ):
            stale += 1
            continue
        reviewer_value = record.get("reviewer")
        reviewer = reviewer_value.strip() if isinstance(reviewer_value, str) else ""
        report_sha256 = str(record.get("report_sha256") or "").strip()
        axis = str(record.get("review_axis") or "").strip().lower()
        verdict = str(record.get("verdict") or "").strip().upper()
        if (
            not reviewer
            or reviewer != reviewer_value
            or len(reviewer) > 120
            or any(unicodedata.category(char).startswith("C") for char in reviewer)
            or not REPORT_SHA256_RE.fullmatch(report_sha256)
            or report_sha256 != record.get("_report_text_sha256")
            or record.get("_report_text_bytes", 0) < MIN_REVIEW_REPORT_BYTES
            or record.get("_comment_evidence_block_count") != 1
            or axis not in ALLOWED_AXES
            or verdict not in {"PASS", "BLOCKED", "FAIL"}
        ):
            malformed += 1
            continue
        record["reviewer"] = reviewer
        record["report_sha256"] = report_sha256
        record["review_axis"] = axis
        record["verdict"] = verdict
        exact.append(record)

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for record in exact:
        key = (record["reviewer"].casefold(), record["review_axis"])
        ordering = (
            str(record.get("_updated_at") or ""),
            int(record.get("_comment_index", 0)),
            int(record.get("_block_index", 0)),
        )
        previous = latest.get(key)
        if previous is None:
            latest[key] = record
            continue
        previous_ordering = (
            str(previous.get("_updated_at") or ""),
            int(previous.get("_comment_index", 0)),
            int(previous.get("_block_index", 0)),
        )
        if ordering >= previous_ordering:
            latest[key] = record

    blocking = [record for record in latest.values() if record["verdict"] != "PASS"]
    if blocking:
        reasons.append(
            "current exact review evidence contains blocking verdicts: "
            + ", ".join(
                f"{record['reviewer']}/{record['review_axis']}={record['verdict']}"
                for record in blocking
            )
        )

    accepted = [
        record
        for record in latest.values()
        if record["verdict"] == "PASS" and record.get("findings_resolved") is True
    ]
    required = REQUIRED_REVIEWS[risk_class]
    if len(accepted) < required:
        reasons.append(
            f"risk {risk_class} requires {required} exact PASS reviews, found {len(accepted)}"
        )

    reviewer_names = {record["reviewer"].casefold() for record in accepted}
    report_hashes = {record["report_sha256"] for record in accepted}
    axes = {record["review_axis"] for record in accepted}
    if required >= 2:
        if len(reviewer_names) < 2:
            reasons.append("R2/R3 require at least two distinct reviewer identities")
        if len(report_hashes) < 2:
            reasons.append("R2/R3 require at least two distinct review reports")
        if len(axes) < 2:
            reasons.append("R2/R3 require at least two distinct review axes")
    if risk_class == "R3" and not (axes & HIGH_RISK_AXES):
        reasons.append(
            "R3 requires at least one security, privacy, data-integrity, concurrency, migration or operations review"
        )

    accepted_summary = [
        {
            "reviewer": record["reviewer"],
            "report_sha256": record["report_sha256"],
            "review_axis": record["review_axis"],
            "attester": record.get("_comment_author"),
            "comment_url": record.get("_comment_url"),
        }
        for record in sorted(
            accepted,
            key=lambda item: (item["review_axis"], item["reviewer"].casefold()),
        )
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "weltgewebe-review-evaluation",
        "pass": not reasons,
        "risk_class": risk_class,
        "minimum_risk_class": minimum_risk,
        "binding": {
            "pr_number": bundle.pr_number,
            "base_sha": bundle.base_sha,
            "head_sha": bundle.head_sha,
            "merge_base_sha": bundle.merge_base_sha,
            "diff_sha256": bundle.diff_sha256,
        },
        "required_review_count": required,
        "accepted_review_count": len(accepted),
        "accepted_reviews": accepted_summary,
        "stale_evidence_count": stale,
        "unauthorized_evidence_count": unauthorized,
        "malformed_evidence_count": malformed,
        "reasons": reasons,
    }


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"cannot read JSON {path}: {exc}") from exc


def _write_failure(output_dir: Path, message: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "kind": "weltgewebe-review-evaluation",
        "pass": False,
        "reasons": [message],
    }
    (output_dir / "evaluation.json").write_bytes(_canonical_json(payload))


def _command_bundle(args: argparse.Namespace) -> int:
    body = (
        Path(args.pr_body_file).read_text(encoding="utf-8") if args.pr_body_file else ""
    )
    risk_class = parse_risk_class(body)
    bundle = generate_bundle(
        repo=Path(args.repo),
        output_dir=Path(args.output_dir),
        base_revision=args.base_sha,
        head_revision=args.head_sha,
        pr_number=args.pr_number,
        risk_class=risk_class,
    )
    print(bundle.manifest_path)
    return 0


def _command_bundle_materialized(args: argparse.Namespace) -> int:
    body = (
        Path(args.pr_body_file).read_text(encoding="utf-8") if args.pr_body_file else ""
    )
    bundle = generate_materialized_bundle(
        output_dir=Path(args.output_dir),
        metadata_file=Path(args.metadata_file),
        diff_file=Path(args.diff_file),
        patch_file=Path(args.patch_file),
        risk_class=parse_risk_class(body),
    )
    print(bundle.manifest_path)
    return 0


def _evaluate_and_write(
    *,
    output_dir: Path,
    bundle: Bundle,
    risk_class: str | None,
    comments_file: Path,
    authorities_file: Path,
) -> int:
    raw_comments = _load_json(comments_file)
    comments = _flatten_comments(raw_comments)
    evaluation = evaluate_evidence(
        bundle=bundle,
        risk_class=risk_class,
        comments=comments,
        allowed_attesters=load_allowed_attesters(authorities_file),
    )
    (output_dir / "evaluation.json").write_bytes(_canonical_json(evaluation))
    print(json.dumps(evaluation, sort_keys=True))
    return 0 if evaluation["pass"] else 1


def _command_evaluate(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    try:
        body = Path(args.pr_body_file).read_text(encoding="utf-8")
        risk_class = parse_risk_class(body)
        bundle = generate_bundle(
            repo=Path(args.repo),
            output_dir=output_dir,
            base_revision=args.base_sha,
            head_revision=args.head_sha,
            pr_number=args.pr_number,
            risk_class=risk_class,
        )
        return _evaluate_and_write(
            output_dir=output_dir,
            bundle=bundle,
            risk_class=risk_class,
            comments_file=Path(args.comments_file),
            authorities_file=Path(args.authorities_file),
        )
    except Exception as exc:  # fail closed and preserve a machine-readable receipt
        _write_failure(output_dir, f"internal governance failure: {exc}")
        print(f"review governance failed closed: {exc}", file=sys.stderr)
        return 2


def _command_evaluate_materialized(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir)
    try:
        body = Path(args.pr_body_file).read_text(encoding="utf-8")
        risk_class = parse_risk_class(body)
        bundle = generate_materialized_bundle(
            output_dir=output_dir,
            metadata_file=Path(args.metadata_file),
            diff_file=Path(args.diff_file),
            patch_file=Path(args.patch_file),
            risk_class=risk_class,
        )
        return _evaluate_and_write(
            output_dir=output_dir,
            bundle=bundle,
            risk_class=risk_class,
            comments_file=Path(args.comments_file),
            authorities_file=Path(args.authorities_file),
        )
    except Exception as exc:  # fail closed and preserve a machine-readable receipt
        _write_failure(output_dir, f"internal governance failure: {exc}")
        print(f"review governance failed closed: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    bundle = subparsers.add_parser("bundle")
    bundle.add_argument("--repo", required=True)
    bundle.add_argument("--output-dir", required=True)
    bundle.add_argument("--base-sha", required=True)
    bundle.add_argument("--head-sha", required=True)
    bundle.add_argument("--pr-number", required=True, type=int)
    bundle.add_argument("--pr-body-file")

    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--repo", required=True)
    evaluate.add_argument("--output-dir", required=True)
    evaluate.add_argument("--base-sha", required=True)
    evaluate.add_argument("--head-sha", required=True)
    evaluate.add_argument("--pr-number", required=True, type=int)
    evaluate.add_argument("--pr-body-file", required=True)
    evaluate.add_argument("--comments-file", required=True)
    evaluate.add_argument("--authorities-file", required=True)

    for name in ("bundle-materialized", "evaluate-materialized"):
        command = subparsers.add_parser(name)
        command.add_argument("--output-dir", required=True)
        command.add_argument("--metadata-file", required=True)
        command.add_argument("--diff-file", required=True)
        command.add_argument("--patch-file", required=True)
        command.add_argument("--pr-body-file", required=name == "evaluate-materialized")
        if name == "evaluate-materialized":
            command.add_argument("--comments-file", required=True)
            command.add_argument("--authorities-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bundle":
        return _command_bundle(args)
    if args.command == "bundle-materialized":
        return _command_bundle_materialized(args)
    if args.command == "evaluate-materialized":
        return _command_evaluate_materialized(args)
    return _command_evaluate(args)


if __name__ == "__main__":
    raise SystemExit(main())

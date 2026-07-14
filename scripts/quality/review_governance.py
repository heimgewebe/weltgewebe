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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = 1
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


@dataclass(frozen=True)
class DiffStats:
    changed_files: tuple[str, ...]
    additions: int
    deletions: int
    binary_files: tuple[str, ...]

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
    return DiffStats(names, additions, deletions, tuple(binary))


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-") or "unknown"


def _canonical_json(data: Any) -> bytes:
    return (
        json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def parse_risk_class(pr_body: str) -> str | None:
    matches = {match.upper() for match in RISK_RE.findall(pr_body or "")}
    if len(matches) != 1:
        return None
    return next(iter(matches))


def minimum_risk_for_paths(paths: Iterable[str]) -> str:
    minimum = "R0"
    for raw_path in paths:
        path = raw_path.lower()
        if (
            path.startswith(".github/workflows/")
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
    output_dir.mkdir(parents=True, exist_ok=True)
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
            f"{base_sha}..{head_sha}",
        ],
    )
    assert isinstance(diff_bytes, bytes)
    assert isinstance(patch_bytes, bytes)
    diff_hash = _sha256(diff_bytes)
    patch_hash = _sha256(patch_bytes)
    stats = _diff_stats(repo, base_sha, head_sha)

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
        "merge_base_sha": merge_base,
        "diff_sha256": diff_hash,
        "risk_class": risk_class,
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "kind": "weltgewebe-review-bundle",
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "binding": binding,
        "stats": {
            "changed_files": list(stats.changed_files),
            "changed_file_count": len(stats.changed_files),
            "additions": stats.additions,
            "deletions": stats.deletions,
            "binary_files": list(stats.binary_files),
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

    request = f"""# Weltgewebe – exakter Reviewauftrag

Prüfe ausschließlich den beigefügten Diff. Frühere oder spätere Versionen zählen nicht.

- PR: #{pr_number}
- Risikoklasse: {risk_class or "FEHLT"}
- Basis-Commit: `{base_sha}`
- Head-Commit: `{head_sha}`
- Merge-Basis: `{merge_base}`
- Diff-SHA-256: `{diff_hash}`
- Geänderte Dateien: {len(stats.changed_files)}
- Zeilen: +{stats.additions} / -{stats.deletions}

Bewerte mindestens eine klar benannte Achse, etwa `correctness`, `security`,
`data-integrity`, `concurrency`, `architecture`, `testing` oder `operations`.
Benenne konkrete Befunde. Ein PASS ist nur zulässig, wenn alle Mergeblocker behoben
oder nachvollziehbar widerlegt sind.

Nach dem Review wird ein Beleg nach diesem Muster als PR-Kommentar hinterlegt:

```text
<!-- weltgewebe-review-evidence
{{
  "schema_version": 1,
  "pr_number": {pr_number},
  "base_sha": "{base_sha}",
  "head_sha": "{head_sha}",
  "diff_sha256": "{diff_hash}",
  "risk_class": "{risk_class or "R?"}",
  "reviewer": "NAME DES PRÜFERS",
  "review_axis": "correctness",
  "verdict": "PASS",
  "findings_resolved": true
}}
-->
```

Der Kommentar muss von einem GitHub-Owner, Member oder Collaborator stammen. Jeder
neue Push, Basiswechsel oder Diffwechsel entwertet den Beleg automatisch.
"""
    request_path.write_text(request, encoding="utf-8")
    return Bundle(
        pr_number=pr_number,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base_sha=merge_base,
        diff_sha256=diff_hash,
        patch_sha256=patch_hash,
        manifest_path=manifest_path,
        diff_path=diff_path,
        patch_path=patch_path,
        request_path=request_path,
        stats=stats,
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
        for block_index, match in enumerate(EVIDENCE_RE.finditer(body)):
            try:
                record = json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue
            record = dict(record)
            record["_comment_index"] = comment_index
            record["_block_index"] = block_index
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
) -> dict[str, Any]:
    reasons: list[str] = []
    if risk_class is None:
        reasons.append(
            "PR body must contain exactly one risk marker: <!-- weltgewebe-risk: R0|R1|R2|R3 -->"
        )
        risk_class = "R3"

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
        if record.get("_author_association") not in AUTHORIZED_ASSOCIATIONS:
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
            "review_axis",
            "verdict",
            "findings_resolved",
        }
        if not required_fields.issubset(record):
            malformed += 1
            continue
        if (
            record.get("schema_version") != SCHEMA_VERSION
            or record.get("pr_number") != bundle.pr_number
            or record.get("base_sha") != bundle.base_sha
            or record.get("head_sha") != bundle.head_sha
            or record.get("diff_sha256") != bundle.diff_sha256
            or str(record.get("risk_class", "")).upper() != risk_class
        ):
            stale += 1
            continue
        reviewer = str(record.get("reviewer") or "").strip()
        axis = str(record.get("review_axis") or "").strip().lower()
        verdict = str(record.get("verdict") or "").strip().upper()
        if (
            not reviewer
            or axis not in ALLOWED_AXES
            or verdict not in {"PASS", "BLOCKED", "FAIL"}
        ):
            malformed += 1
            continue
        record["reviewer"] = reviewer
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
    axes = {record["review_axis"] for record in accepted}
    if required >= 2:
        if len(reviewer_names) < 2:
            reasons.append("R2/R3 require at least two distinct reviewer identities")
        if len(axes) < 2:
            reasons.append("R2/R3 require at least two distinct review axes")
    if risk_class == "R3" and not (axes & HIGH_RISK_AXES):
        reasons.append(
            "R3 requires at least one security, privacy, data-integrity, concurrency, migration or operations review"
        )

    accepted_summary = [
        {
            "reviewer": record["reviewer"],
            "review_axis": record["review_axis"],
            "comment_author": record.get("_comment_author"),
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
        raw_comments = _load_json(Path(args.comments_file))
        comments = _flatten_comments(raw_comments)
        evaluation = evaluate_evidence(
            bundle=bundle,
            risk_class=risk_class,
            comments=comments,
        )
        (output_dir / "evaluation.json").write_bytes(_canonical_json(evaluation))
        print(json.dumps(evaluation, sort_keys=True))
        return 0 if evaluation["pass"] else 1
    except Exception as exc:  # fail closed and preserve a machine-readable receipt
        _write_failure(output_dir, f"internal governance failure: {exc}")
        print(f"review governance failed closed: {exc}", file=sys.stderr)
        return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("bundle", "evaluate"):
        command = subparsers.add_parser(name)
        command.add_argument("--repo", required=True)
        command.add_argument("--output-dir", required=True)
        command.add_argument("--base-sha", required=True)
        command.add_argument("--head-sha", required=True)
        command.add_argument("--pr-number", required=True, type=int)
        command.add_argument("--pr-body-file", required=name == "evaluate")
        if name == "evaluate":
            command.add_argument("--comments-file", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "bundle":
        return _command_bundle(args)
    return _command_evaluate(args)


if __name__ == "__main__":
    raise SystemExit(main())

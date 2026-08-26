import argparse
import datetime
import json
import os
import re
import subprocess
import sys

from scripts.docmeta.docmeta import (
    REPO_ROOT,
    parse_frontmatter,
    parse_repo_index,
    parse_review_policy,
)

RETIRED_STATUSES = {"archived", "deprecated", "obsolete", "retired", "superseded"}
RETIRED_LIFECYCLE_STATES = {"archived", "deprecated", "obsolete", "retired", "superseded"}
CURRENT_REVIEW_STATUSES = {"active", "canonical", "draft"}
YYYY_MM_DD_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _parse_yyyy_mm_dd(value: str) -> datetime.date:
    if YYYY_MM_DD_RE.fullmatch(value) is None:
        raise ValueError("date must use literal YYYY-MM-DD form")
    return datetime.date.fromisoformat(value)


def _today_from_arg(value: str | None) -> datetime.date:
    if value is None:
        return datetime.date.today()
    try:
        return _parse_yyyy_mm_dd(value)
    except ValueError as exc:
        raise ValueError("--today must be a valid date in YYYY-MM-DD format") from exc


def _tracked_markdown_files(root: str) -> list[str]:
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


def _is_retired(frontmatter: dict) -> bool:
    status = str(frontmatter.get("status", "")).strip().lower()
    lifecycle_state = str(frontmatter.get("lifecycle_state", "")).strip().lower()
    # The lifecycle contract derives review obligations from status before it
    # adds lifecycle_state rules. A contradictory active/archived document must
    # therefore remain review-visible instead of being silently retired.
    if status in CURRENT_REVIEW_STATUSES:
        return False
    return status in RETIRED_STATUSES or lifecycle_state in RETIRED_LIFECYCLE_STATES


def _report_issue(mode: str, message: str, errors: list[str], warnings: list[str]) -> None:
    if mode in {"strict", "fail-closed"}:
        errors.append(message)
    else:
        warnings.append(message)


def _check_review_after(
    *,
    root: str,
    today: datetime.date,
    mode: str,
    errors: list[str],
    warnings: list[str],
    freshness_report: dict,
) -> None:
    for rel_file_path in _tracked_markdown_files(root):
        file_path = os.path.join(root, rel_file_path)
        frontmatter = parse_frontmatter(file_path)
        if not frontmatter:
            continue

        review_after_str = str(frontmatter.get("review_after", "")).strip()
        if not review_after_str:
            continue

        doc_id = str(frontmatter.get("id", rel_file_path))
        entry = freshness_report.setdefault(
            doc_id,
            {
                "file": rel_file_path,
                "last_reviewed": frontmatter.get("last_reviewed"),
                "days_since_review": -1,
                "status": "not_indexed",
            },
        )
        entry["review_after"] = review_after_str
        entry["review_due"] = False
        entry["review_due_days"] = 0
        entry["review_retired"] = _is_retired(frontmatter)

        try:
            review_after_date = _parse_yyyy_mm_dd(review_after_str)
        except ValueError:
            entry["review_due"] = None
            errors.append(
                f"Invalid 'review_after' format '{review_after_str}' in '{rel_file_path}'. "
                "Must be YYYY-MM-DD."
            )
            continue

        # A retired document is historical evidence. Its old deadline must not
        # re-activate it or create a new review obligation.
        if entry["review_retired"]:
            continue

        if review_after_date <= today:
            due_days = (today - review_after_date).days
            entry["review_due"] = True
            entry["review_due_days"] = due_days
            _report_issue(
                mode,
                (
                    f"Document '{rel_file_path}' review_after ({review_after_str}) "
                    f"is due/overdue by {due_days} day(s) as of {today.isoformat()}."
                ),
                errors,
                warnings,
            )


def _check_last_reviewed(
    *,
    root: str,
    repo_index: dict,
    today: datetime.date,
    warn_days: int,
    fail_days: int,
    mode: str,
    errors: list[str],
    warnings: list[str],
    freshness_report: dict,
) -> None:
    for zone_data in repo_index.get("zones", {}).values():
        rel_zone_path = zone_data.get("path")
        if not rel_zone_path:
            continue

        zone_path = os.path.join(root, rel_zone_path)
        if not os.path.exists(zone_path):
            continue

        for doc_file in zone_data.get("canonical_docs", []):
            file_path = os.path.join(zone_path, doc_file)
            rel_file_path = os.path.join(rel_zone_path, doc_file)
            if not os.path.exists(file_path):
                continue

            frontmatter = parse_frontmatter(file_path)
            if not frontmatter:
                continue

            doc_id = str(frontmatter.get("id", rel_file_path))
            last_reviewed_str = frontmatter.get("last_reviewed")
            status = "unknown"
            days_since_review = -1

            if not last_reviewed_str:
                msg = f"Missing 'last_reviewed' in '{rel_file_path}'."
                status = "missing"
                _report_issue(mode, msg, errors, warnings)
            else:
                try:
                    last_reviewed_date = datetime.datetime.strptime(
                        str(last_reviewed_str), "%Y-%m-%d"
                    ).date()
                    days_since_review = (today - last_reviewed_date).days
                    if days_since_review > fail_days:
                        status = "fail"
                        _report_issue(
                            mode,
                            (
                                f"Document '{rel_file_path}' review age "
                                f"({days_since_review} days) exceeds fail limit "
                                f"({fail_days} days)."
                            ),
                            errors,
                            warnings,
                        )
                    elif days_since_review > warn_days:
                        status = "warn"
                        warnings.append(
                            f"Document '{rel_file_path}' review age ({days_since_review} days) "
                            f"exceeds warn limit ({warn_days} days)."
                        )
                    else:
                        status = "pass"
                except ValueError:
                    status = "invalid"
                    errors.append(
                        f"Invalid 'last_reviewed' format '{last_reviewed_str}' in "
                        f"'{rel_file_path}'. Must be YYYY-MM-DD."
                    )

            previous = freshness_report.get(doc_id, {})
            freshness_report[doc_id] = {
                **previous,
                "file": rel_file_path,
                "last_reviewed": last_reviewed_str,
                "days_since_review": days_since_review,
                "status": status,
            }


def _write_artifacts(root: str, freshness_report: dict) -> None:
    artifacts_dir = os.path.join(root, "artifacts", "docmeta")
    os.makedirs(artifacts_dir, exist_ok=True)

    with open(os.path.join(artifacts_dir, "freshness.json"), "w", encoding="utf-8") as f:
        json.dump(freshness_report, f, indent=2, sort_keys=True)

    with open(os.path.join(artifacts_dir, "freshness.md"), "w", encoding="utf-8") as f:
        f.write("# Freshness Report\n\n")
        f.write("| ID | File | Last Reviewed | Age (Days) | Review After | Due | Status |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for doc_id in sorted(freshness_report):
            info = freshness_report[doc_id]
            status = info.get("status", "unknown")
            status_icon = "✅"
            if status == "warn" or info.get("review_due") is True:
                status_icon = "⚠️"
            elif status == "fail":
                status_icon = "❌"
            elif status in {"missing", "invalid"}:
                status_icon = "❓"
            due = "retired" if info.get("review_retired") else str(info.get("review_due", ""))
            f.write(
                f"| {doc_id} | `{info['file']}` | {info.get('last_reviewed')} | "
                f"{info.get('days_since_review', -1)} | {info.get('review_after', '')} | "
                f"{due} | {status_icon} {status} |\n"
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate documentation review age and review_after lifecycle."
    )
    parser.add_argument(
        "--today",
        help="Deterministic ISO date override for tests/reproducible audits (default: local current date).",
    )
    args = parser.parse_args(argv)

    try:
        today = _today_from_arg(args.today)
        policy = parse_review_policy()
        strict_mode = policy.get("strict_manifest", False)
        repo_index = parse_repo_index(strict_manifest=strict_mode)
        warn_days = policy["warn_days"]
        fail_days = policy["fail_days"]
        mode = policy["mode"]
    except (KeyError, ValueError) as exc:
        print(f"Error parsing manifest/policy: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    errors: list[str] = []
    warnings: list[str] = []
    freshness_report: dict = {}

    _check_last_reviewed(
        root=REPO_ROOT,
        repo_index=repo_index,
        today=today,
        warn_days=warn_days,
        fail_days=fail_days,
        mode=mode,
        errors=errors,
        warnings=warnings,
        freshness_report=freshness_report,
    )
    _check_review_after(
        root=REPO_ROOT,
        today=today,
        mode=mode,
        errors=errors,
        warnings=warnings,
        freshness_report=freshness_report,
    )
    _write_artifacts(REPO_ROOT, freshness_report)

    if warnings:
        print(f"\n--- Warnings ({len(warnings)}) ---", file=sys.stderr)
        for warning in warnings:
            print(f"- {warning}", file=sys.stderr)

    if errors:
        print(f"\n--- Errors ({len(errors)}) ---", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        print("\nDoc review age/lifecycle check failed.", file=sys.stderr)
        raise SystemExit(1)

    print(
        f"Doc review age/lifecycle check passed (0 errors, {len(warnings)} warnings)."
    )


if __name__ == "__main__":
    main()

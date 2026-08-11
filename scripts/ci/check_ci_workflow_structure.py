#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
REUSABLE = "./.github/workflows/reusable-web-check.yml"
CALLERS = ("ci.yml", "web.yml", "heavy.yml")


def _has_run_line(text: str, command: str) -> bool:
    expected = f"run: {command}"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == expected or stripped == f"- {expected}":
            return True
    return False


def validate_workflow_texts(texts: dict[str, str]) -> list[str]:
    errors: list[str] = []
    reusable = texts["reusable-web-check.yml"]
    if "  workflow_call:" not in reusable.splitlines():
        errors.append("reusable-web-check.yml must expose the workflow_call contract")
    if "permissions:" in reusable.splitlines():
        errors.append("reusable-web-check.yml must inherit token permissions from each caller")
    if not _has_run_line(reusable, "pnpm playwright install --with-deps"):
        errors.append("reusable web check must own Playwright browser installation")
    if 'PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD: ""' not in reusable:
        errors.append("reusable web check must force-enable Playwright browser installation")
    if not _has_run_line(reusable, "pnpm test:ci") or not _has_run_line(reusable, "pnpm test"):
        errors.append("reusable web check must own both ci and full Playwright suite execution")

    for caller in CALLERS:
        text = texts[caller]
        if f"uses: {REUSABLE}" not in text:
            errors.append(f"{caller} must call {REUSABLE}")
        if _has_run_line(text, "pnpm playwright install --with-deps"):
            errors.append(f"{caller} must not reinstall Playwright directly")
        if _has_run_line(text, "pnpm test:ci") or _has_run_line(text, "pnpm test"):
            errors.append(f"{caller} must not invoke the shared Playwright suites directly")

    ci = texts["ci.yml"]
    if "run_demo_api: true" not in ci or "suite: ci" not in ci:
        errors.append("ci.yml web-e2e must preserve the demo API plus ci-suite contract")
    if "- web-e2e" not in ci:
        errors.append("ci.yml required merge gate must continue to depend on web-e2e")

    web = texts["web.yml"]
    for marker in (
        "run_unit_tests: ${{ github.event_name == 'push' && github.ref != 'refs/heads/main' }}",
        "run_typecheck: true",
        "run_lint: true",
        "run_build: true",
        ".github/workflows/reusable-web-check.yml",
    ):
        if marker not in web:
            errors.append(f"web.yml lost required reusable-web-check contract marker: {marker}")

    heavy = texts["heavy.yml"]
    for marker in (
        "workflow_dispatch: {}",
        "full-ci",
        "if: needs.gate.outputs.run_heavy == 'true'",
        "run_build: true",
        "suite: full",
    ):
        if marker not in heavy:
            errors.append(f"heavy.yml lost on-demand/label gate marker: {marker}")

    return errors


def validate(root: Path = WORKFLOW_DIR) -> list[str]:
    names = (*CALLERS, "reusable-web-check.yml")
    texts = {name: (root / name).read_text(encoding="utf-8") for name in names}
    return validate_workflow_texts(texts)


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("CI workflow composition guard: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

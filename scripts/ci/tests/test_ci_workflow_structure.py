from __future__ import annotations

from pathlib import Path

from scripts.ci.check_ci_workflow_structure import validate, validate_workflow_texts

ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_DIR = ROOT / ".github" / "workflows"


def _texts() -> dict[str, str]:
    names = ("ci.yml", "web.yml", "heavy.yml", "reusable-web-check.yml")
    return {name: (WORKFLOW_DIR / name).read_text(encoding="utf-8") for name in names}


def test_repository_workflows_use_the_reusable_web_check_without_direct_playwright_duplication() -> None:
    assert validate() == []


def test_guard_rejects_reintroduced_direct_playwright_execution() -> None:
    texts = _texts()
    texts["heavy.yml"] += chr(10).join(
        ("", "      - run: pnpm playwright install --with-deps", "      - run: pnpm test", "")
    )
    errors = validate_workflow_texts(texts)
    assert any("heavy.yml must not reinstall Playwright directly" in error for error in errors)
    assert any("heavy.yml must not invoke the shared Playwright suites directly" in error for error in errors)


def test_guard_rejects_reusable_workflow_without_workflow_call() -> None:
    texts = _texts()
    old = chr(10).join(('"on":', "  workflow_call:"))
    new = chr(10).join(('"on":', "  workflow_dispatch:"))
    texts["reusable-web-check.yml"] = texts["reusable-web-check.yml"].replace(old, new)
    errors = validate_workflow_texts(texts)
    assert any("must expose the workflow_call contract" in error for error in errors)


def test_guard_rejects_reusable_workflow_that_overrides_caller_permissions() -> None:
    texts = _texts()
    marker = chr(10).join(("name: Reusable Web Check", ""))
    replacement = chr(10).join(
        ("name: Reusable Web Check", "", "permissions:", "  contents: read", "")
    )
    texts["reusable-web-check.yml"] = texts["reusable-web-check.yml"].replace(
        marker, replacement, 1
    )
    errors = validate_workflow_texts(texts)
    assert any(
        "must inherit token permissions from each caller" in error for error in errors
    )

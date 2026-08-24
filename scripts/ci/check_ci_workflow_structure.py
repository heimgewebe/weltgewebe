#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
REUSABLE = "./.github/workflows/reusable-web-check.yml"
CALLERS = ("ci.yml", "web.yml", "heavy.yml")

CI_TOOL_DOWNLOAD_CONTRACTS = (
    (
        "Install yq",
        (
            'YQ_SHA256="a2c097180dd884a8d50c956ee16a9cec070f30a7947cf4ebf87d5f36213e9ed7"',
            'wget -qO "$YQ_DOWNLOAD" "https://github.com/mikefarah/yq/releases/download/v${YQ_VERSION}/yq_linux_amd64"',
            'printf \'%s  %s\\n\' "$YQ_SHA256" "$YQ_DOWNLOAD" | sha256sum -c -',
            'install -m 0755 "$YQ_DOWNLOAD" "$YQ_BIN"',
        ),
    ),
    (
        "Install cargo-deny",
        (
            'DENY_SHA256="663f655b23c58e7d8eaf1c6b6bd8e197742757b5314bd292fd8dcbc0a16581c6"',
            'curl -sLf "$TARBALL_URL" -o "$TARBALL_PATH"',
            'printf \'%s  %s\\n\' "$DENY_SHA256" "$TARBALL_PATH" | sha256sum -c -',
            'tar xzf "$TARBALL_PATH" -C "$EXTRACT_DIR" --strip-components=1',
            'install -m 0755 "$EXTRACT_DIR/cargo-deny" "$DENY_BIN"',
        ),
    ),
)


def _has_run_line(text: str, command: str) -> bool:
    expected = f"run: {command}"
    for line in text.splitlines():
        stripped = line.strip()
        if stripped == expected or stripped == f"- {expected}":
            return True
    return False


def _named_step(text: str, name: str) -> str | None:
    marker = f"      - name: {name}\n"
    start = text.find(marker)
    if start < 0:
        return None
    end = text.find("\n      - name: ", start + len(marker))
    return text[start:] if end < 0 else text[start:end]


def _active_line_index(block: str, command: str) -> int | None:
    matches = [
        index
        for index, line in enumerate(block.splitlines())
        if line.strip() == command
    ]
    return matches[0] if len(matches) == 1 else None


def _validate_tool_download_integrity(ci: str, errors: list[str]) -> None:
    for step_name, commands in CI_TOOL_DOWNLOAD_CONTRACTS:
        block = _named_step(ci, step_name)
        if block is None:
            errors.append(f"ci.yml must retain the {step_name} step")
            continue

        positions: list[int] = []
        missing = False
        for command in commands:
            position = _active_line_index(block, command)
            if position is None:
                errors.append(
                    f"ci.yml {step_name} download integrity contract lost exact active line: {command}"
                )
                missing = True
            else:
                positions.append(position)

        if not missing and positions != sorted(positions):
            errors.append(
                f"ci.yml {step_name} must verify the pinned SHA-256 before using the download"
            )


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
    _validate_tool_download_integrity(ci, errors)

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

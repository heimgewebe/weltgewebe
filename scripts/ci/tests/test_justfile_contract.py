from __future__ import annotations

import json
from pathlib import Path
import re
import shlex
import unittest


ROOT = Path(__file__).resolve().parents[3]
JUSTFILE = ROOT / "Justfile"
WEB_PACKAGE = ROOT / "apps" / "web" / "package.json"
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
WEB_WORKFLOW = ROOT / ".github" / "workflows" / "web.yml"
CONTINUATION = chr(92)
SHELL_OPERATORS = {";", "&&", "||", "|"}
PACKAGE_MANAGERS = {"pnpm", "npm"}
PACKAGE_OPTIONS_WITH_VALUE = {
    "pnpm": {
        "--config",
        "--dir",
        "--filter",
        "--lockfile-dir",
        "--network-concurrency",
        "--reporter",
        "--store-dir",
        "--virtual-store-dir",
        "--workspace-concurrency",
        "-C",
        "-F",
    },
    "npm": {
        "--cache",
        "--prefix",
        "--registry",
        "--userconfig",
        "--workspace",
        "-w",
    },
}
PACKAGE_BOOLEAN_OPTIONS = {
    "pnpm": {
        "--if-present",
        "--ignore-scripts",
        "--offline",
        "--prefer-offline",
        "--recursive",
        "--silent",
        "--workspace-root",
        "-r",
        "-s",
        "-w",
    },
    "npm": {
        "--if-present",
        "--ignore-scripts",
        "--silent",
        "-s",
    },
}
PACKAGE_BUILTINS = {
    "add",
    "ci",
    "config",
    "install",
    "list",
    "remove",
    "setup",
    "update",
}


def continued(command: str) -> str:
    return f"{command}; {CONTINUATION}"


def shell_commands(command: str) -> list[list[str]]:
    command = command.replace("\n", " ; ")
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    lexer.commenters = ""
    commands: list[list[str]] = [[]]
    for token in lexer:
        if token in SHELL_OPERATORS:
            if commands[-1]:
                commands.append([])
            continue
        commands[-1].append(token)
    return [tokens for tokens in commands if tokens]


def skip_environment_assignments(tokens: list[str], index: int = 0) -> int:
    while index < len(tokens) and re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[index]
    ):
        index += 1
    return index


def skip_package_options(tokens: list[str], index: int, tool: str) -> int:
    while index < len(tokens) and tokens[index].startswith("-"):
        option = tokens[index]
        if option == "--":
            return index + 1
        if option.startswith("--") and "=" in option:
            index += 1
            continue
        if option in PACKAGE_OPTIONS_WITH_VALUE[tool]:
            if index + 1 >= len(tokens) or tokens[index + 1].startswith("-"):
                raise ValueError(f"missing value for {tool} option {option}")
            index += 2
            continue
        if option in PACKAGE_BOOLEAN_OPTIONS[tool]:
            index += 1
            continue
        raise ValueError(f"unsupported {tool} option {option}")
    return index


def package_invocation(
    tokens: list[str], scripts: dict[str, str]
) -> tuple[str, str] | None:
    index = skip_environment_assignments(tokens)
    if index >= len(tokens) or tokens[index] not in PACKAGE_MANAGERS:
        return None
    tool = tokens[index]
    index = skip_package_options(tokens, index + 1, tool)
    if index >= len(tokens):
        raise ValueError(f"{tool} command is missing")
    command = tokens[index]
    index += 1

    if command in {"exec", "dlx"}:
        index = skip_package_options(tokens, index, tool)
        if index >= len(tokens):
            raise ValueError(f"{tool} {command} target is missing")
        return ("binary", tokens[index])

    if command == "run":
        index = skip_package_options(tokens, index, tool)
        if index >= len(tokens):
            raise ValueError(f"{tool} run script is missing")
        return ("script", tokens[index])

    if command in scripts:
        return ("script", command)
    if command in PACKAGE_BUILTINS:
        return ("builtin", command)
    return ("builtin", command)


def direct_binary(tokens: list[str]) -> str | None:
    index = skip_environment_assignments(tokens)
    if index >= len(tokens):
        return None
    return tokens[index]


def script_uses_binary(
    script: str,
    scripts: dict[str, str],
    binary: str,
    visiting: set[str] | None = None,
    memo: dict[str, bool] | None = None,
) -> bool:
    visiting = set() if visiting is None else visiting
    memo = {} if memo is None else memo
    if script in memo:
        return memo[script]
    if script in visiting:
        return False
    visiting.add(script)
    lifecycle = [
        name for name in (f"pre{script}", script, f"post{script}") if name in scripts
    ]
    try:
        for name in lifecycle:
            for tokens in shell_commands(scripts[name]):
                if direct_binary(tokens) == binary:
                    memo[script] = True
                    return True
                invocation = package_invocation(tokens, scripts)
                if invocation is None:
                    continue
                kind, target = invocation
                if kind == "binary" and target == binary:
                    memo[script] = True
                    return True
                if kind == "script" and script_uses_binary(
                    target, scripts, binary, visiting, memo
                ):
                    memo[script] = True
                    return True
    except ValueError:
        memo[script] = True
        return True
    finally:
        visiting.discard(script)
    memo[script] = False
    return False


def run_uses_binary(run: str, scripts: dict[str, str], binary: str) -> bool:
    try:
        for tokens in shell_commands(run):
            if direct_binary(tokens) == binary:
                return True
            invocation = package_invocation(tokens, scripts)
            if invocation is None:
                continue
            kind, target = invocation
            if kind == "binary" and target == binary:
                return True
            if kind == "script" and script_uses_binary(target, scripts, binary):
                return True
    except ValueError:
        return True
    return False


def trigger_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.index('"on":\n')
    candidates = [
        position
        for marker in ("\njobs:\n", "\nconcurrency:\n")
        if (position := text.find(marker, start)) != -1
    ]
    return text[start : min(candidates)]


def workflow_steps(path: Path) -> list[dict[str, str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    steps: list[dict[str, str]] = []
    index = 0
    while index < len(lines):
        match = re.match(r"^(\s*)- name:\s*(.+)$", lines[index])
        if match is None:
            index += 1
            continue
        indent = len(match.group(1))
        step: dict[str, str] = {"name": match.group(2).strip("\"'")}
        index += 1
        while index < len(lines):
            next_step = re.match(r"^(\s*)- name:\s*(.+)$", lines[index])
            if next_step is not None and len(next_step.group(1)) == indent:
                break
            stripped = lines[index].strip()
            current_indent = len(lines[index]) - len(lines[index].lstrip())
            if stripped and current_indent <= indent:
                break
            if stripped.startswith("if:"):
                step["if"] = stripped.removeprefix("if:").strip()
            elif stripped.startswith("run:"):
                value = stripped.removeprefix("run:").strip()
                if value in {"|", ">"}:
                    run_indent = len(lines[index]) - len(lines[index].lstrip())
                    block: list[str] = []
                    index += 1
                    while index < len(lines):
                        raw = lines[index]
                        current_indent = len(raw) - len(raw.lstrip())
                        if raw.strip() and current_indent <= run_indent:
                            index -= 1
                            break
                        block.append(raw[run_indent + 2 :] if raw.strip() else "")
                        index += 1
                    step["run"] = "\n".join(block)
                else:
                    step["run"] = value
            index += 1
        steps.append(step)
    return steps


class JustfileContractTests(unittest.TestCase):
    def ci_recipe_lines(self) -> list[str]:
        text = JUSTFILE.read_text(encoding="utf-8")
        start = text.index("\nci:\n")
        end = text.index("\n# ---------- Rust ----------", start)
        return text[start:end].splitlines()

    def executable_lines(self) -> list[str]:
        return [
            line.lstrip("\t")
            for line in self.ci_recipe_lines()
            if line.startswith("\t")
            and not line.startswith("\t#")
            and not line.startswith("\t@echo")
        ]

    def web_scripts(self) -> dict[str, str]:
        scripts = json.loads(WEB_PACKAGE.read_text(encoding="utf-8")).get("scripts")
        self.assertIsInstance(scripts, dict)
        self.assertTrue(
            all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in scripts.items()
            )
        )
        return scripts

    def test_just_ci_web_block_is_exact_and_unconditional(self) -> None:
        lines = self.executable_lines()
        start = lines.index(f"if [ -d apps/web ]; then {CONTINUATION}")
        end = lines.index("fi", start)
        self.assertEqual(
            lines[start : end + 1],
            [
                f"if [ -d apps/web ]; then {CONTINUATION}",
                continued("pushd apps/web >/dev/null"),
                continued("pnpm install --frozen-lockfile"),
                continued("pnpm sync"),
                continued("pnpm exec vitest run"),
                continued("pnpm build"),
                continued("pnpm run ci"),
                continued("popd >/dev/null"),
                "fi",
            ],
        )

    def test_hosted_events_cover_unit_tests_without_pr_or_main_duplication(
        self,
    ) -> None:
        scripts = self.web_scripts()
        ci_triggers = trigger_block(CI_WORKFLOW)
        web_triggers = trigger_block(WEB_WORKFLOW)
        self.assertIn("branches: [main]", ci_triggers)
        self.assertIn("pull_request:", ci_triggers)
        self.assertIn("branches: [main, dev, 'feat/**', 'fix/**']", web_triggers)
        self.assertIn("pull_request:", web_triggers)

        ci_steps = workflow_steps(CI_WORKFLOW)
        web_steps = workflow_steps(WEB_WORKFLOW)
        self.assertTrue(
            any(
                any(tokens == ["just", "ci"] for tokens in shell_commands(step["run"]))
                for step in ci_steps
                if "run" in step
            )
        )
        self.assertFalse(
            any(
                run_uses_binary(step["run"], scripts, "vitest")
                for step in ci_steps
                if "run" in step
            )
        )
        unit_steps = [
            step
            for step in web_steps
            if "run" in step and run_uses_binary(step["run"], scripts, "vitest")
        ]
        self.assertEqual(
            unit_steps,
            [
                {
                    "name": "Unit tests (non-main branch pushes)",
                    "if": "github.event_name == 'push' && github.ref != 'refs/heads/main'",
                    "run": "pnpm test:unit",
                }
            ],
        )
        self.assertTrue(
            any(
                step.get("name") == "Test (CI)"
                and step.get("run") == "pnpm test:ci"
                and run_uses_binary(step["run"], scripts, "playwright")
                for step in web_steps
            )
        )

    def test_local_package_scripts_do_not_reach_playwright(self) -> None:
        scripts = self.web_scripts()
        for script in ("sync", "build", "ci"):
            self.assertFalse(script_uses_binary(script, scripts, "playwright"), script)

    def test_resolver_handles_option_values_hooks_cycles_and_malformed_scripts(
        self,
    ) -> None:
        direct_cases = {
            "pnpm-dir": "pnpm --dir . run browser",
            "pnpm-filter": "pnpm --filter weltgewebe-web run browser",
            "npm-prefix": "npm --prefix . run browser",
            "pnpm-exec": "pnpm --dir . exec playwright test",
            "npm-exec": "npm --prefix . exec playwright test",
        }
        for name, command in direct_cases.items():
            scripts = {"root": command, "browser": "playwright test"}
            self.assertTrue(script_uses_binary("root", scripts, "playwright"), name)

        scripts = {
            "browser": "playwright test",
            "wrapper": "pnpm --silent run browser",
            "ci": "echo ok",
            "preci": "npm run wrapper",
            "cycle-a": "pnpm cycle-b",
            "cycle-b": "pnpm cycle-a && pnpm browser",
            "broken-root": "pnpm broken",
            "broken": "echo '",
            "safe": "echo playwright && test -d playwright",
        }
        self.assertTrue(script_uses_binary("wrapper", scripts, "playwright"))
        self.assertTrue(script_uses_binary("ci", scripts, "playwright"))
        self.assertTrue(script_uses_binary("cycle-a", scripts, "playwright"))
        self.assertTrue(script_uses_binary("broken-root", scripts, "playwright"))
        self.assertFalse(script_uses_binary("safe", scripts, "playwright"))

    def test_workflow_run_parser_detects_unit_command_variants(self) -> None:
        scripts = self.web_scripts()
        for command in (
            "pnpm test:unit",
            "pnpm run test:unit",
            "pnpm exec vitest run",
            "echo prepare\npnpm test:unit",
        ):
            self.assertTrue(run_uses_binary(command, scripts, "vitest"), command)

    def test_rust_formatting_stays_check_only(self) -> None:
        lines = self.executable_lines()
        self.assertIn(continued("cargo fmt -- --check"), lines)
        self.assertNotIn(continued("cargo fmt --all"), lines)


if __name__ == "__main__":
    unittest.main()

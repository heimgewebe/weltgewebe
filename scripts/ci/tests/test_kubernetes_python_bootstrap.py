"""Keep the Kubernetes workflows on one hash-verified Python bootstrap.

The Kubernetes security and validation workflows render manifests, validate the
platform contract and scan the result with Trivy. Every one of those jobs runs
repository Python, so the dependency that carries them must come from a single
hash-bound authority: the ``tools/py`` project and its ``uv.lock``.

A version-only ``pip install`` reintroduces a weaker parallel supply-chain path
next to the locked one, which is exactly how the original finding arose. These
tests fail closed on that regression instead of leaving the property to prose.
"""

from __future__ import annotations

from pathlib import Path
import re
import tomllib
from typing import Any
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = ROOT / ".github/workflows"
TOOLS_PROJECT = ROOT / "tools/py"

# Discovered rather than listed, so a new Kubernetes workflow is covered the day
# it appears. The known files are asserted separately so a rename cannot silently
# empty the guard.
KUBERNETES_WORKFLOWS = tuple(sorted(path.name for path in WORKFLOWS.glob("kubernetes*.yml")))
REQUIRED_WORKFLOWS = frozenset(
    {
        "kubernetes-platform.yml",
        "kubernetes-platform-proof.yml",
        "kubernetes-proof-oci-mirror.yml",
    }
)

LOCKED_SYNC = "uv sync --project tools/py --locked"
LOCKED_RUN = "uv run --project tools/py --locked"
PROJECT_RUN = "uv run --project tools/py"
UV_VERSION_EXPRESSION = re.compile(
    r"^\$\{\{\s*steps\.([A-Za-z0-9_-]+)\.outputs\.uv_version\s*\}\}$"
)
UV_VERSION_ASSIGNMENT = re.compile(
    r'''(?m)^\s*([A-Za-z_][A-Za-z0-9_]*)=\$\(grep '\^uv:' toolchain\.versions\.yml \| cut -d '"' -f2\)\s*$'''
)
FOREIGN_INSTALLERS = re.compile(
    r"\b(?:pip|pip3|pipx|easy_install)\b[^;&|\n]*?\binstall\b"
    r"|\bpython3?\s+-m\s+pip\b[^;&|\n]*?\binstall\b"
)
# A host Python interpreter invoked as a command.  ``env`` and absolute/explicit
# paths are command wrappers too; plain words inside arguments/paths stay ignored.
BARE_PYTHON = re.compile(
    r"(?:^|[|;&]\s*|\(\s*|\bthen\s+|\bdo\s+)"
    # Common shell command wrappers must not hide the real executable.  Allow
    # wrapper chains such as ``sudo env python`` and explicit wrapper paths.
    r"(?:"
    r"(?:(?:/|\./|\.\./)[^\s;&|()]*/)?"
    r"(?:"
    r"env(?:\s+(?:-[^\s;&|()]+|[A-Za-z_][A-Za-z0-9_]*=[^\s;&|()]+))*"
    r"|command(?:\s+-p)?"
    r"|exec(?:\s+-[cl])?"
    r"|nohup"
    r"|sudo(?:\s+(?:-[A-Za-z]+|--[A-Za-z-]+)(?:\s+(?!python3?\b)[^\s;&|()]+)?)*"
    r"|time(?:\s+-p)?"
    r")\s+"
    r")*"
    r"(?:(?:/|\./|\.\./)[^\s;&|()]*/)?"
    r"(python3?)(?=$|\s|[;&|)])"
)
VALIDATOR_DEPENDENCY = "pyyaml"


def _steps(job: Any) -> list[dict[str, Any]]:
    if not isinstance(job, dict):
        return []
    return [step for step in (job.get("steps") or []) if isinstance(step, dict)]


def _run(step: dict[str, Any]) -> str:
    return str(step.get("run") or "")


def _logical_lines(script: str) -> list[str]:
    """Join shell backslash continuations so a command reads as one line."""

    joined = re.sub(r"\\\s*\n\s*", " ", script)
    return [line.strip() for line in joined.splitlines() if line.strip()]


def _repository_python_step(step: dict[str, Any]) -> bool:
    """Return whether a step invokes repository Python by any supported path."""

    for line in _logical_lines(_run(step)):
        if PROJECT_RUN in line or BARE_PYTHON.search(line):
            return True
    return False


def bootstrap_violations(workflow: dict[str, Any], label: str) -> list[str]:
    """Report repository-Python jobs that escape or precede the locked bootstrap."""

    violations: list[str] = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        steps = _steps(job)
        runs = [index for index, step in enumerate(steps) if _repository_python_step(step)]
        if not runs:
            continue

        for index in runs:
            run = _run(steps[index])
            if PROJECT_RUN in run and LOCKED_RUN not in run:
                violations.append(
                    f"{label}:{job_id} runs repository Python without the locked runner: {PROJECT_RUN!r}"
                )

        syncs = [index for index, step in enumerate(steps) if LOCKED_SYNC in _run(step)]
        if not syncs:
            violations.append(f"{label}:{job_id} runs repository Python without {LOCKED_SYNC!r}")
        elif min(syncs) > min(runs):
            violations.append(f"{label}:{job_id} runs repository Python before syncing the lock")
    return violations


def foreign_installer_violations(workflow: dict[str, Any], label: str) -> list[str]:
    """Report steps that bootstrap Python packages outside the locked project."""

    violations: list[str] = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        for step in _steps(job):
            for line in _logical_lines(_run(step)):
                match = FOREIGN_INSTALLERS.search(line)
                if match:
                    violations.append(
                        f"{label}:{job_id} installs outside tools/py: {match.group(0)}"
                    )
    return violations


def bare_interpreter_violations(workflow: dict[str, Any], label: str) -> list[str]:
    """Report Python invoked outside the locked runner.

    Requiring the sync only when the locked runner is already used would let a
    job escape the contract by calling the host interpreter directly.
    """

    violations: list[str] = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        for step in _steps(job):
            for line in _logical_lines(_run(step)):
                # The regex is anchored to shell command positions, so the Python
                # argument of LOCKED_RUN is not a host invocation.  Do not skip the
                # whole line: ``LOCKED_RUN ... && python ...`` must still fail.
                match = BARE_PYTHON.search(line)
                if match:
                    violations.append(
                        f"{label}:{job_id} runs {match.group(1)!r} outside {LOCKED_RUN!r}: {line}"
                    )
    return violations


def uv_version_violations(workflow: dict[str, Any], label: str) -> list[str]:
    """Report setup-uv steps whose version is not derived from toolchain.versions.yml."""

    violations: list[str] = []
    for job_id, job in (workflow.get("jobs") or {}).items():
        steps = _steps(job)
        for step in steps:
            if not str(step.get("uses") or "").startswith("astral-sh/setup-uv@"):
                continue

            version = str((step.get("with") or {}).get("version", ""))
            expression = UV_VERSION_EXPRESSION.fullmatch(version)
            if not expression:
                violations.append(f"{label}:{job_id} pins uv inline as {version!r}")
                continue

            producer_id = expression.group(1)
            producers = [candidate for candidate in steps if str(candidate.get("id") or "") == producer_id]
            if len(producers) != 1:
                violations.append(
                    f"{label}:{job_id} references uv-version output from non-unique step {producer_id!r}"
                )
                continue

            producer_run = _run(producers[0])
            assignment = UV_VERSION_ASSIGNMENT.search(producer_run)
            if not assignment:
                violations.append(
                    f"{label}:{job_id} uv-version step {producer_id!r} does not derive its value from toolchain.versions.yml"
                )
                continue

            variable = assignment.group(1)
            writes_output = (
                "GITHUB_OUTPUT" in producer_run
                and "uv_version" in producer_run
                and re.search(rf"\$\{{?{re.escape(variable)}\}}?", producer_run) is not None
            )
            if not writes_output:
                violations.append(
                    f"{label}:{job_id} uv-version step {producer_id!r} does not publish the derived value"
                )
    return violations


def _load(name: str) -> dict[str, Any]:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


class KubernetesPythonBootstrapTests(unittest.TestCase):
    def test_the_known_kubernetes_workflows_are_all_discovered(self) -> None:
        missing = sorted(REQUIRED_WORKFLOWS - set(KUBERNETES_WORKFLOWS))
        self.assertEqual(missing, [], "a renamed workflow would silently empty this guard")

    def test_no_kubernetes_job_runs_python_outside_the_locked_runner(self) -> None:
        violations = [
            violation
            for name in KUBERNETES_WORKFLOWS
            for violation in bare_interpreter_violations(_load(name), name)
        ]
        self.assertEqual(violations, [])

    def test_every_python_job_syncs_the_hash_locked_project_first(self) -> None:
        covered = 0
        violations: list[str] = []
        for name in KUBERNETES_WORKFLOWS:
            workflow = _load(name)
            violations.extend(bootstrap_violations(workflow, name))
            covered += sum(
                1
                for job in (workflow.get("jobs") or {}).values()
                if any(_repository_python_step(step) for step in _steps(job))
            )
        self.assertEqual(violations, [])
        self.assertGreaterEqual(
            covered, 6, "expected the Kubernetes contract, proof and Trivy jobs to be covered"
        )

    def test_no_kubernetes_job_installs_dependencies_outside_the_lock(self) -> None:
        violations = [
            violation
            for name in KUBERNETES_WORKFLOWS
            for violation in foreign_installer_violations(_load(name), name)
        ]
        self.assertEqual(violations, [])

    def test_uv_itself_comes_from_the_single_toolchain_authority(self) -> None:
        toolchain = yaml.safe_load((ROOT / "toolchain.versions.yml").read_text(encoding="utf-8"))
        self.assertIsInstance(toolchain.get("uv"), str)
        violations = [
            violation
            for name in KUBERNETES_WORKFLOWS
            for violation in uv_version_violations(_load(name), name)
        ]
        self.assertEqual(violations, [])

    def test_validator_dependency_is_exactly_pinned_in_one_project(self) -> None:
        pyproject = tomllib.loads((TOOLS_PROJECT / "pyproject.toml").read_text(encoding="utf-8"))
        pinned = [
            item
            for item in pyproject["project"]["dependencies"]
            if item.split("==")[0].strip().lower() == VALIDATOR_DEPENDENCY
        ]
        self.assertEqual(len(pinned), 1, f"{VALIDATOR_DEPENDENCY} must be declared exactly once")
        self.assertRegex(
            pinned[0],
            r"^[A-Za-z0-9._-]+==[0-9][0-9A-Za-z.\-]*$",
            "the validator dependency must carry an exact == pin",
        )

    def test_lock_binds_every_validator_artifact_to_a_sha256(self) -> None:
        lock = tomllib.loads((TOOLS_PROJECT / "uv.lock").read_text(encoding="utf-8"))
        packages = [
            package
            for package in lock.get("package", [])
            if package.get("name", "").lower() == VALIDATOR_DEPENDENCY
        ]
        self.assertEqual(len(packages), 1, f"{VALIDATOR_DEPENDENCY} must be locked once")

        artifacts = [packages[0]["sdist"]] if packages[0].get("sdist") else []
        artifacts.extend(packages[0].get("wheels") or [])
        self.assertTrue(artifacts, "the locked validator dependency binds no artifact")
        for artifact in artifacts:
            self.assertRegex(
                str(artifact.get("hash", "")),
                r"^sha256:[0-9a-f]{64}$",
                f"unhashed artifact in the lock: {artifact.get('url', '')}",
            )

    def test_no_second_dependency_authority_is_referenced(self) -> None:
        for name in KUBERNETES_WORKFLOWS:
            self.assertNotIn(
                "requirements.txt",
                (WORKFLOWS / name).read_text(encoding="utf-8"),
                f"{name} introduces a second Python dependency authority",
            )


class KubernetesPythonBootstrapGuardTests(unittest.TestCase):
    """The guard must reject the regressions it exists to prevent."""

    def test_pip_bootstrap_next_to_the_lock_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "trivy-rendered-security": {
                    "steps": [
                        {"run": LOCKED_SYNC},
                        {"run": "python -m pip install --no-cache-dir pyyaml==6.0.2"},
                        {"run": f"{LOCKED_RUN} python scripts/security/trivy_rendered_manifests.py"},
                    ]
                }
            }
        }
        self.assertEqual(bootstrap_violations(workflow, "w"), [])
        self.assertEqual(len(foreign_installer_violations(workflow, "w")), 1)

    def test_pip_global_options_before_install_are_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {
                            "run": "python -m pip --disable-pip-version-check --no-input install pyyaml==6.0.3"
                        }
                    ]
                }
            }
        }
        self.assertEqual(len(foreign_installer_violations(workflow, "w")), 1)

    def test_missing_sync_is_reported(self) -> None:
        workflow = {
            "jobs": {"contract": {"steps": [{"run": f"{LOCKED_RUN} python -m unittest"}]}}
        }
        self.assertEqual(len(bootstrap_violations(workflow, "w")), 1)

    def test_unlocked_project_runner_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": LOCKED_SYNC},
                        {"run": "uv run --project tools/py python -m unittest"},
                    ]
                }
            }
        }
        self.assertEqual(len(bootstrap_violations(workflow, "w")), 1)

    def test_host_interpreter_without_sync_is_seen_by_bootstrap_guard(self) -> None:
        workflow = {
            "jobs": {"contract": {"steps": [{"run": "python scripts/platform/validate_platform.py"}]}}
        }
        self.assertEqual(len(bootstrap_violations(workflow, "w")), 1)

    def test_sync_after_first_locked_run_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": f"{LOCKED_RUN} python -m unittest"},
                        {"run": LOCKED_SYNC},
                    ]
                }
            }
        }
        self.assertEqual(len(bootstrap_violations(workflow, "w")), 1)

    def test_inline_uv_version_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {
                            "uses": "astral-sh/setup-uv@" + "a" * 40,
                            "with": {"version": "0.9.11"},
                        }
                    ]
                }
            }
        }
        self.assertEqual(len(uv_version_violations(workflow, "w")), 1)

    def test_hard_coded_uv_output_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {
                            "id": "uv-version",
                            "run": "echo 'uv_version=0.9.11' >> \"${GITHUB_OUTPUT}\"",
                        },
                        {
                            "uses": "astral-sh/setup-uv@" + "a" * 40,
                            "with": {"version": "${{ steps.uv-version.outputs.uv_version }}"},
                        },
                    ]
                }
            }
        }
        self.assertEqual(len(uv_version_violations(workflow, "w")), 1)

    def test_fake_derivation_inside_assignment_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {
                            "id": "uv-version",
                            "run": "UV_VERSION=$(printf 0.9.11; : toolchain.versions.yml)\nprintf 'uv_version=%s\\n' \"${UV_VERSION}\" >> \"${GITHUB_OUTPUT}\"",
                        },
                        {
                            "uses": "astral-sh/setup-uv@" + "a" * 40,
                            "with": {"version": "${{ steps.uv-version.outputs.uv_version }}"},
                        },
                    ]
                }
            }
        }
        self.assertEqual(len(uv_version_violations(workflow, "w")), 1)

    def test_mentioning_toolchain_file_without_deriving_output_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {
                            "id": "uv-version",
                            "run": "cat toolchain.versions.yml >/dev/null\necho 'uv_version=0.9.11' >> \"${GITHUB_OUTPUT}\"",
                        },
                        {
                            "uses": "astral-sh/setup-uv@" + "a" * 40,
                            "with": {"version": "${{ steps.uv-version.outputs.uv_version }}"},
                        },
                    ]
                }
            }
        }
        self.assertEqual(len(uv_version_violations(workflow, "w")), 1)

    def test_env_wrapped_host_interpreter_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": LOCKED_SYNC},
                        {"run": "env PYTHONUTF8=1 python scripts/platform/validate_platform.py --render"},
                    ]
                }
            }
        }
        self.assertEqual(len(bare_interpreter_violations(workflow, "w")), 1)

    def test_common_command_wrappers_cannot_hide_host_python(self) -> None:
        commands = (
            "command python x.py",
            "command -p python x.py",
            "exec python x.py",
            "nohup python x.py",
            "sudo python x.py",
            "sudo -n python x.py",
            "sudo -u root python x.py",
            "time python x.py",
            "time -p python x.py",
            "/usr/bin/env python x.py",
            "sudo env PYTHONUTF8=1 python x.py",
        )
        for command in commands:
            with self.subTest(command=command):
                workflow = {"jobs": {"contract": {"steps": [{"run": command}]}}}
                self.assertEqual(len(bare_interpreter_violations(workflow, "w")), 1)

    def test_absolute_host_interpreter_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [{"run": "/usr/bin/python3 scripts/platform/validate_platform.py"}]
                }
            }
        }
        self.assertEqual(len(bare_interpreter_violations(workflow, "w")), 1)

    def test_bare_interpreter_after_locked_run_on_same_line_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": f"{LOCKED_RUN} python -m unittest && python scripts/platform/validate_platform.py"}
                    ]
                }
            }
        }
        self.assertEqual(len(bare_interpreter_violations(workflow, "w")), 1)

    def test_python_as_plain_argument_is_not_a_host_interpreter(self) -> None:
        workflow = {"jobs": {"contract": {"steps": [{"run": "printf '%s\n' python"}]}}}
        self.assertEqual(bare_interpreter_violations(workflow, "w"), [])

    def test_host_interpreter_next_to_the_lock_is_reported(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": LOCKED_SYNC},
                        {"run": "python3 scripts/platform/validate_platform.py --render"},
                    ]
                }
            }
        }
        self.assertEqual(len(bare_interpreter_violations(workflow, "w")), 1)

    def test_continuation_lines_do_not_hide_a_foreign_installer(self) -> None:
        workflow = {"jobs": {"contract": {"steps": [{"run": "pip \\\n  install pyyaml==6.0.2"}]}}}
        self.assertEqual(len(foreign_installer_violations(workflow, "w")), 1)

    def test_continuation_lines_do_not_produce_a_false_bare_interpreter(self) -> None:
        workflow = {
            "jobs": {"contract": {"steps": [{"run": f"{LOCKED_RUN} \\\n  python -m unittest"}]}}
        }
        self.assertEqual(bare_interpreter_violations(workflow, "w"), [])

    def test_paths_and_flags_are_not_mistaken_for_an_interpreter(self) -> None:
        workflow = {
            "jobs": {
                "contract": {
                    "steps": [
                        {"run": "cat .python-version"},
                        {"run": "kubectl apply -f platform/python-app.yaml"},
                    ]
                }
            }
        }
        self.assertEqual(bare_interpreter_violations(workflow, "w"), [])

    def test_jobs_without_repository_python_are_not_forced_to_sync(self) -> None:
        workflow = {"jobs": {"verify-read-access": {"steps": [{"run": "crane digest ref"}]}}}
        self.assertEqual(bootstrap_violations(workflow, "w"), [])


if __name__ == "__main__":
    unittest.main()

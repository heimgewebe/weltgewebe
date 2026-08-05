"""Regression contract for uv-bound workflow trigger inputs."""

from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]


class UvWorkflowTriggerContractTest(unittest.TestCase):
    def _trigger_section(self, relative: str) -> str:
        text = (ROOT / relative).read_text(encoding="utf-8")
        marker = "\njobs:\n"
        self.assertIn(marker, text, relative)
        return text.split(marker, 1)[0]

    def assert_trigger_inputs(self, relative: str, expected: tuple[str, ...]) -> None:
        trigger = self._trigger_section(relative)
        for item in expected:
            self.assertIn(f'- "{item}"', trigger, f"{relative} misses trigger input {item}")

    def test_agent_preflight_tracks_all_python_environment_inputs(self) -> None:
        self.assert_trigger_inputs(
            ".github/workflows/agent-safety-preflight.yml",
            ("tools/py/pyproject.toml", "tools/py/uv.lock", "toolchain.versions.yml", ".python-version"),
        )

    def test_policycheck_tracks_all_python_environment_inputs(self) -> None:
        self.assert_trigger_inputs(
            ".github/workflows/policycheck.yml",
            ("tools/py/**", "toolchain.versions.yml", ".python-version"),
        )

    def test_platform_proof_tracks_all_python_environment_inputs(self) -> None:
        self.assert_trigger_inputs(
            ".github/workflows/kubernetes-platform-proof.yml",
            ("tools/py/**", "toolchain.versions.yml", ".python-version"),
        )


    def test_core_guard_job_bootstraps_uv_before_fixture_suites(self) -> None:
        text = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        guard_job = text.split("\n  guard-tests:\n", 1)[1].split("\n  ci:\n", 1)[0]
        setup_uv = "uses: astral-sh/setup-uv@11f9893b081a58869d3b5fccaea48c9e9e46f990"
        fixture_step = "- name: Run guard fixture suites"
        self.assertIn("python-version-file: '.python-version'", guard_job)
        self.assertIn(setup_uv, guard_job)
        self.assertIn("uv sync --project tools/py --locked", guard_job)
        self.assertIn(fixture_step, guard_job)
        self.assertLess(guard_job.index(setup_uv), guard_job.index(fixture_step))


if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]


class ComposeDevBuildIdentityContractTests(unittest.TestCase):
    def test_web_service_receives_caller_bound_git_commit(self) -> None:
        compose = (ROOT / "infra/compose/compose.core.yml").read_text(encoding="utf-8")
        self.assertIn("GIT_COMMIT_SHA: ${GIT_COMMIT_SHA:-}", compose)

    def test_compose_smoke_binds_the_exact_github_revision(self) -> None:
        workflow = (ROOT / ".github/workflows/compose-smoke.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("GIT_COMMIT_SHA: ${{ github.sha }}", workflow)
        self.assertIn(
            "docker compose -f infra/compose/compose.core.yml --profile dev up -d --build",
            workflow,
        )

    def test_make_up_derives_the_exact_local_head(self) -> None:
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn(
            'GIT_COMMIT_SHA="$$(git rev-parse HEAD)" docker compose '
            "-f infra/compose/compose.core.yml --profile dev up -d --build",
            makefile,
        )


if __name__ == "__main__":
    unittest.main()

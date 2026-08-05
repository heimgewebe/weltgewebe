from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[3]
COMPOSE = ROOT / "infra/compose/compose.core.yml"
WORKFLOW = ROOT / ".github/workflows/compose-smoke.yml"


def load_yaml(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise AssertionError(f"{path} must contain a YAML mapping")
    return payload


def workflow_triggers(payload: dict) -> dict:
    # PyYAML 1.1 interprets the unquoted key `on` as boolean True.
    triggers = payload.get("on", payload.get(True))
    if not isinstance(triggers, dict):
        raise AssertionError("workflow must define mapping-style triggers")
    return triggers


def volume_by_target(volumes: list, target: str) -> dict:
    for volume in volumes:
        if isinstance(volume, str):
            parts = volume.split(":")
            if len(parts) < 2:
                continue
            source, candidate_target, *options = parts
            if candidate_target == target:
                return {
                    "source": source,
                    "target": candidate_target,
                    "read_only": "ro" in options,
                }
        elif isinstance(volume, dict) and volume.get("target") == target:
            return {
                "source": volume.get("source"),
                "target": volume.get("target"),
                "read_only": bool(volume.get("read_only")),
            }
    raise AssertionError(f"volume target {target!r} not found")


class ComposeDevBuildIdentityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose = load_yaml(COMPOSE)
        cls.workflow = load_yaml(WORKFLOW)

    def test_web_service_receives_caller_bound_git_commit(self) -> None:
        web = self.compose["services"]["web"]
        self.assertEqual(
            web["environment"]["GIT_COMMIT_SHA"],
            "${GIT_COMMIT_SHA:-}",
        )

    def test_web_service_mounts_repository_basemap_styles_read_only(self) -> None:
        web = self.compose["services"]["web"]
        mount = volume_by_target(web["volumes"], "/map-style")
        self.assertEqual(mount["source"], "../../map-style")
        self.assertTrue(mount["read_only"])

    def test_repository_basemap_style_inputs_exist(self) -> None:
        for filename in (
            "style.json",
            "style-dark.json",
            "style-germany.json",
            "style-germany-dark.json",
        ):
            with self.subTest(filename=filename):
                self.assertTrue((ROOT / "map-style" / filename).is_file())

    def test_database_healthcheck_queries_the_configured_database(self) -> None:
        healthcheck = self.compose["services"]["db"]["healthcheck"]["test"]
        self.assertIsInstance(healthcheck, list)
        self.assertEqual(healthcheck[0], "CMD-SHELL")
        command = " ".join(str(part) for part in healthcheck[1:])
        self.assertIn("pg_isready -q -h 127.0.0.1", command)
        self.assertIn("psql -X -w -qAt -v ON_ERROR_STOP=1", command)
        self.assertIn('-U "$${POSTGRES_USER}"', command)
        self.assertIn('-d "$${POSTGRES_DB}"', command)
        self.assertIn("-c 'SELECT 1'", command)
        self.assertIn("grep -qx '1'", command)

    def test_compose_smoke_binds_the_exact_github_revision(self) -> None:
        self.assertEqual(
            self.workflow["env"]["GIT_COMMIT_SHA"],
            "${{ github.sha }}",
        )
        push_paths = workflow_triggers(self.workflow)["push"]["paths"]
        self.assertIn("map-style/**", push_paths)
        steps = self.workflow["jobs"]["smoke"]["steps"]
        compose_up = next(
            step for step in steps if step.get("name") == "Compose up (detached)"
        )
        self.assertEqual(
            compose_up["run"],
            "docker compose -f infra/compose/compose.core.yml --profile dev up -d --build",
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

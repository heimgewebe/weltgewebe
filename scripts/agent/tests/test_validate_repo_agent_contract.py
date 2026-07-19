"""Tests for scripts.agent.validate_repo_agent_contract."""

import json
import tempfile
import unittest
from pathlib import Path

from scripts.agent.validate_repo_agent_contract import (
    READING_ORDER_REQUIRED_PREFIX,
    validate_repo_agent_contract,
)

VALID_CONTRACT = {
    "architecture": {
        "repo_role": "repo_contract_authority",
        "operator_role": "external_operator_execution",
        "operator_name": "grabowski",
        "repo_generic_write_mode": "rejected",
    },
    "reading_order": [
        "agent-contract.json",
        "repo.meta.yaml",
        "AGENTS.md",
        "agent-policy.yaml",
        "docs/policies/agent-reading-protocol.md",
    ],
    "safe_read_paths": ["src/"],
    "guarded_write_paths": [
        ".wgx/generated-artifacts.yml",
        "agent-contract.json",
        "src/",
    ],
    "forbidden_write_paths": ["docs/_generated/"],
    "required_checks": ["just test"],
    "local_checks_before_patch": ["just check"],
    "generated_artifacts": {
        "direct_agent_edit": "forbidden",
        "derived_write_authority": "trusted_generators_only",
        "trusted_generator_registry": ".wgx/generated-artifacts.yml",
        "allowed_target_prefixes": ["docs/_generated/"],
    },
    "validation_profiles": {"generator_profile": {"named_checks": ["generator check"]}},
    "compatibility_projections": [
        {
            "role": "compatibility_projection",
            "path": "repo.meta.yaml",
            "projected_fields": {"safe_read_paths": "read_paths"},
        },
        {
            "role": "compatibility_projection",
            "path": "agent-policy.yaml",
            "projected_fields": {"safe_read_paths": "safe_reads"},
        },
    ],
}

VALID_SCHEMA = {"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}

VALID_REPO_META = """
# Compatibility Projection
read_paths:
  - "src/"
"""

VALID_AGENT_POLICY = """
# Compatibility Projection
safe_reads:
  - "src/"
"""

VALID_REGISTRY = """
schema_version: 1
artifacts:
  - path: docs/_generated/output.md
    kind: generated
    generator: ["python3", "gen.py"]
"""


class TestValidateRepoAgentContract(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.tmp.name)
        (self.repo_root / "contracts" / "agent").mkdir(parents=True)
        (self.repo_root / ".wgx").mkdir(parents=True)
        self.write_json("contracts/agent/agent-contract.schema.json", VALID_SCHEMA)
        self.write_json("agent-contract.json", VALID_CONTRACT)
        self.write_file("repo.meta.yaml", VALID_REPO_META)
        self.write_file("agent-policy.yaml", VALID_AGENT_POLICY)
        self.write_file(".wgx/generated-artifacts.yml", VALID_REGISTRY)

    def tearDown(self):
        self.tmp.cleanup()

    def write_file(self, rel_path, content):
        (self.repo_root / rel_path).write_text(content, encoding="utf-8")

    def write_json(self, rel_path, data):
        self.write_file(rel_path, json.dumps(data))

    def test_repository_schema_requires_full_reading_order(self):
        repo_root = Path(__file__).resolve().parents[3]
        schema = json.loads(
            (repo_root / "contracts/agent/agent-contract.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            schema["properties"]["reading_order"]["minItems"],
            len(READING_ORDER_REQUIRED_PREFIX),
        )

    def test_repository_contract_and_schema_validate_together(self):
        repo_root = Path(__file__).resolve().parents[3]
        self.assertEqual(validate_repo_agent_contract(repo_root), [])

    def test_valid_contract(self):
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertEqual(findings, [])

    def test_duplicate_json_key(self):
        content = json.dumps(VALID_CONTRACT)
        content = content[:-1] + ', "safe_read_paths": ["other/"]}'
        self.write_file("agent-contract.json", content)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_CHECK_ERROR"
                and "duplicate json key" in f["message"].lower()
                for f in findings
            )
        )

    def test_nan_infinity(self):
        content = json.dumps(VALID_CONTRACT)
        content = content[:-1] + ', "invalid": NaN}'
        self.write_file("agent-contract.json", content)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_CHECK_ERROR"
                and "nan" in f["message"].lower()
                for f in findings
            )
        )

    def test_schema_error(self):
        schema = {"type": "array"}
        self.write_json("contracts/agent/agent-contract.schema.json", schema)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(any(f["code"] == "AGENT_CONTRACT_SCHEMA" for f in findings))

    def test_wrong_architecture_role(self):
        contract = dict(VALID_CONTRACT)
        contract["architecture"] = dict(VALID_CONTRACT["architecture"])
        contract["architecture"]["repo_role"] = "wrong_role"
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_ARCHITECTURE" for f in findings)
        )

    def test_reading_order_error(self):
        contract = dict(VALID_CONTRACT)
        contract["reading_order"] = ["repo.meta.yaml", "agent-contract.json"]
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_READING_ORDER" for f in findings)
        )

    def test_projection_drift_repo_meta(self):
        self.write_file("repo.meta.yaml", VALID_REPO_META.replace("src/", "docs/"))
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_PROJECTION_DRIFT"
                and "repo.meta.yaml" in f["path"]
                for f in findings
            )
        )

    def test_projection_drift_agent_policy(self):
        self.write_file(
            "agent-policy.yaml", VALID_AGENT_POLICY.replace("src/", "docs/")
        )
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_PROJECTION_DRIFT"
                and "agent-policy.yaml" in f["path"]
                for f in findings
            )
        )

    def test_missing_projection_marker(self):
        self.write_file("repo.meta.yaml", "read_paths:\n  - src/")
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_PROJECTION_MARKER" for f in findings)
        )

    def test_direct_generated_edits_not_forbidden(self):
        contract = dict(VALID_CONTRACT)
        contract["generated_artifacts"] = dict(VALID_CONTRACT["generated_artifacts"])
        contract["generated_artifacts"]["direct_agent_edit"] = "allowed"
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any("direct agent edits" in f["message"].lower() for f in findings)
        )

    def test_generator_target_outside_forbidden_paths(self):
        registry = """
        artifacts:
          - path: src/output.md
            kind: generated
            generator: ["python3", "gen.py"]
        """
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                "must stay under an allowed_target_prefixes prefix" in f["message"]
                for f in findings
            )
        )

    def test_generated_secret_target_is_rejected(self):
        registry = """
        artifacts:
          - path: secrets/generated-token.txt
            kind: generated
            generator: ["python3", "gen.py"]
        """
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR"
                and "allowed_target_prefixes" in f["message"]
                for f in findings
            )
        )

    def test_authority_files_must_be_guarded(self):
        contract = dict(VALID_CONTRACT)
        contract["guarded_write_paths"] = ["src/"]
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_AUTHORITY_GUARD"
                and "agent-contract.json" in f["message"]
                for f in findings
            )
        )
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_AUTHORITY_GUARD"
                and ".wgx/generated-artifacts.yml" in f["message"]
                for f in findings
            )
        )

    def test_generated_target_prefixes_are_fixed(self):
        contract = dict(VALID_CONTRACT)
        contract["generated_artifacts"] = dict(VALID_CONTRACT["generated_artifacts"])
        contract["generated_artifacts"]["allowed_target_prefixes"] = ["secrets/"]
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_GENERATED_TARGETS" for f in findings)
        )

    def test_duplicate_generator_write(self):
        registry = """
        artifacts:
          - path: docs/_generated/out1.md
            kind: generated
            generator: ["python3", "gen.py"]
          - path: docs/_generated/out1.md
            kind: generated
            generator: ["python3", "gen.py"]
        """
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any("duplicate artifact path" in f["message"] for f in findings)
        )

    def test_missing_registry(self):
        (self.repo_root / ".wgx" / "generated-artifacts.yml").unlink()
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any("generator registry file is missing" in f["message"] for f in findings)
        )

    def test_invalid_registry_yaml(self):
        self.write_file(".wgx/generated-artifacts.yml", "invalid: yaml: :")
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR" for f in findings)
        )

    def test_missing_yaml(self):
        (self.repo_root / "repo.meta.yaml").unlink()
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                "missing" in f["message"] and "repo.meta.yaml" in f["path"]
                for f in findings
            )
        )

    def test_invalid_yaml(self):
        self.write_file("repo.meta.yaml", "Compatibility Projection\ninvalid: yaml: :")
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_PROJECTION_YAML_ERROR" for f in findings)
        )

    def test_duplicate_key_projection(self):
        self.write_file("repo.meta.yaml", "Compatibility Projection\nread_paths:\n  - src/\nread_paths:\n  - other/")
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_PROJECTION_YAML_ERROR" for f in findings)
        )

    def test_duplicate_key_registry(self):
        registry = """
schema_version: 1
artifacts:
  - path: docs/_generated/out1.md
    kind: generated
    generator: ["python3", "gen.py"]
artifacts:
  - path: docs/_generated/out2.md
    kind: generated
    generator: ["python3", "gen.py"]
"""
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR" and "duplicate key" in f["message"].lower() for f in findings)
        )

    def test_bad_registry_path(self):
        contract = dict(VALID_CONTRACT)
        contract["generated_artifacts"] = dict(VALID_CONTRACT["generated_artifacts"])
        contract["generated_artifacts"]["trusted_generator_registry"] = "/etc/passwd"
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR" and "must be exactly" in f["message"] for f in findings)
        )

    def test_absolute_artifact_path_is_rejected(self):
        registry = """
artifacts:
  - path: /tmp/output.md
    kind: generated
    generator: ["python3", "gen.py"]
"""
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR"
                and "repository-relative" in f["message"]
                for f in findings
            )
        )

    def test_projection_path_traversal_is_rejected(self):
        contract = dict(VALID_CONTRACT)
        contract["compatibility_projections"] = [
            {
                "role": "compatibility_projection",
                "path": "../repo.meta.yaml",
                "projected_fields": {"safe_read_paths": "read_paths"},
            }
        ]
        self.write_json("agent-contract.json", contract)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_PROJECTION"
                and "repository-relative" in f["message"]
                for f in findings
            )
        )

    def test_empty_generator_argument_is_rejected(self):
        registry = """
artifacts:
  - path: docs/_generated/output.md
    kind: generated
    generator: ["python3", ""]
"""
        self.write_file(".wgx/generated-artifacts.yml", registry)
        findings = validate_repo_agent_contract(self.repo_root)
        self.assertTrue(
            any(
                f["code"] == "AGENT_CONTRACT_REGISTRY_ERROR"
                and "generator must be a list of strings" in f["message"]
                for f in findings
            )
        )


if __name__ == "__main__":
    unittest.main()

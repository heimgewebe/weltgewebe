import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import scripts.docmeta.validate_claim_registry as validator


class TestValidateClaimRegistry(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(validator.REPO_ROOT)
        self.temp_dir = Path(tempfile.mkdtemp(prefix="claim-registry-test-", dir=self.repo_root))

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_registry(self, payload: object, file_name: str = "registry.json") -> str:
        path = self.temp_dir / file_name
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        return str(path.relative_to(self.repo_root))

    def _valid_claim(self) -> dict:
        return {
            "id": "CLAIM-AGENT-SAFE-003",
            "status": "established",
            "subject": "AGENT-SAFE-003",
            "statement": "Minimal claim-evidence spine exists",
            "evidence": [{"path": "README.md", "kind": "documentation"}],
            "validation": ["python3 scripts/docmeta/validate_claim_registry.py"],
            "updated": "2026-06-01",
        }

    def test_valid_minimal_registry_passes(self):
        registry = self._write_registry({"version": 1, "claims": [self._valid_claim()]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 0)
        self.assertEqual(output["findings_count"], 0)

    def test_missing_registry_returns_exit_2(self):
        output, exit_code = validator.run_validation("docs/claims/does-not-exist.yml")
        self.assertEqual(exit_code, 2)
        self.assertEqual(output["findings"][0]["code"], "REGISTRY_MISSING")

    def test_invalid_top_level(self):
        registry = self._write_registry([self._valid_claim()])
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertEqual(output["findings"][0]["code"], "INVALID_TOP_LEVEL")

    def test_missing_version(self):
        registry = self._write_registry({"claims": [self._valid_claim()]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "MISSING_VERSION" for f in output["findings"]))

    def test_missing_claims(self):
        registry = self._write_registry({"version": 1})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "MISSING_CLAIMS" for f in output["findings"]))

    def test_claim_without_id(self):
        claim = self._valid_claim()
        del claim["id"]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "CLAIM_MISSING_FIELD" for f in output["findings"]))

    def test_invalid_claim_id(self):
        claim = self._valid_claim()
        claim["id"] = "bad-id"
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "CLAIM_INVALID_ID" for f in output["findings"]))

    def test_duplicate_claim_id(self):
        claim = self._valid_claim()
        registry = self._write_registry({"version": 1, "claims": [claim, dict(claim)]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "CLAIM_DUPLICATE_ID" for f in output["findings"]))

    def test_invalid_status(self):
        claim = self._valid_claim()
        claim["status"] = "done"
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "CLAIM_INVALID_STATUS" for f in output["findings"]))

    def test_established_missing_evidence_path(self):
        claim = self._valid_claim()
        claim["evidence"] = [{"path": "docs/claims/does-not-exist.md", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "EVIDENCE_PATH_MISSING" for f in output["findings"]))

    def test_absolute_evidence_path_rejected(self):
        claim = self._valid_claim()
        claim["evidence"] = [{"path": "/etc/hosts", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "EVIDENCE_PATH_OUTSIDE_REPO" for f in output["findings"]))

    def test_parent_traversal_evidence_path_rejected(self):
        claim = self._valid_claim()
        claim["evidence"] = [{"path": "../outside.md", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "EVIDENCE_PATH_OUTSIDE_REPO" for f in output["findings"]))

    def test_proposed_missing_evidence_path_allowed(self):
        claim = self._valid_claim()
        claim["status"] = "proposed"
        claim["evidence"] = [{"path": "docs/claims/does-not-exist.md", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 0)
        self.assertFalse(any(f["code"] == "EVIDENCE_PATH_MISSING" for f in output["findings"]))

    def test_proposed_absolute_evidence_path_still_rejected(self):
        claim = self._valid_claim()
        claim["status"] = "proposed"
        claim["evidence"] = [{"path": "/etc/hosts", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "EVIDENCE_PATH_OUTSIDE_REPO" for f in output["findings"]))

    def test_valid_relative_evidence_path_still_passes(self):
        claim = self._valid_claim()
        claim["evidence"] = [{"path": "README.md", "kind": "documentation"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 0)
        self.assertFalse(any(f["code"] == "EVIDENCE_PATH_OUTSIDE_REPO" for f in output["findings"]))

    def test_evidence_missing_kind(self):
        claim = self._valid_claim()
        claim["evidence"] = [{"path": "README.md"}]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "EVIDENCE_MISSING_FIELD" for f in output["findings"]))

    def test_claim_missing_validation(self):
        claim = self._valid_claim()
        del claim["validation"]
        registry = self._write_registry({"version": 1, "claims": [claim]})
        output, exit_code = validator.run_validation(registry)
        self.assertEqual(exit_code, 1)
        self.assertTrue(any(f["code"] == "CLAIM_MISSING_VALIDATION" for f in output["findings"]))

    def test_cli_outputs_valid_json(self):
        registry = self._write_registry({"version": 1, "claims": [self._valid_claim()]})
        cmd = [
            "python3",
            "scripts/docmeta/validate_claim_registry.py",
            "--registry",
            registry,
        ]
        proc = subprocess.run(
            cmd,
            cwd=self.repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0)
        parsed = json.loads(proc.stdout)
        self.assertEqual(parsed["findings_count"], 0)

    def test_real_registry_validates(self):
        output, exit_code = validator.run_validation("docs/claims/registry.yml")
        self.assertEqual(exit_code, 0)
        self.assertEqual(output["findings_count"], 0)

    def test_parse_error_returns_exit_2(self):
        broken_path = self.temp_dir / "broken.yml"
        broken_path.write_text("{not-json", encoding="utf-8")
        rel = str(broken_path.relative_to(self.repo_root))
        output, exit_code = validator.run_validation(rel)
        self.assertEqual(exit_code, 2)
        self.assertEqual(output["findings"][0]["code"], "REGISTRY_PARSE_ERROR")


if __name__ == "__main__":
    unittest.main()

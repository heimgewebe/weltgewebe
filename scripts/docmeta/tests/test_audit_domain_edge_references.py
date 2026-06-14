import json
import os
import subprocess
import tempfile
import unittest

SCRIPT_PATH = ["python3", "-m", "scripts.docmeta.audit_domain_edge_references"]

def run_script(*args, env=None):
    env_vars = os.environ.copy()
    if env:
        env_vars.update(env)
    # Remove DATABASE_URL if it was somehow inherited and we aren't overriding it
    if env is not None and "DATABASE_URL" not in env and "DATABASE_URL" in env_vars:
        del env_vars["DATABASE_URL"]

    return subprocess.run(
        SCRIPT_PATH + list(args),
        capture_output=True,
        text=True,
        env=env_vars
    )


class TestAuditDomainEdgeReferences(unittest.TestCase):
    def test_no_input_fails(self):
        result = run_script()
        self.assertNotEqual(result.returncode, 0)

    def test_missing_nodes_file_fails(self):
        result = run_script("--nodes-jsonl", "does_not_exist.jsonl", "--edges-jsonl", "also_does_not_exist.jsonl")
        self.assertNotEqual(result.returncode, 0)

    def test_missing_edges_file_fails(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nodes_file:
            result = run_script("--nodes-jsonl", nodes_file.name, "--edges-jsonl", "does_not_exist.jsonl")
            self.assertNotEqual(result.returncode, 0)

    def test_all_typed_node_references_valid(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["typed_node_references"], 2)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], True)
            self.assertIs(data["policy_signals"]["requires_runtime_data_run"], False)

    def test_all_typed_node_references_valid_but_repo_fixture(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "repo-fixture", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["typed_node_references"], 2)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], False)
            self.assertIs(data["policy_signals"]["requires_runtime_data_run"], True)

    def test_typed_node_missing_source_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-b"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "missing-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["typed_node_missing_references"], 1)
            self.assertIs(data["policy_signals"]["requires_cleanup"], True)
            self.assertIs(data["policy_signals"]["requires_policy_decision"], True)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], False)

    def test_typed_node_missing_target_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "missing-b", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            finding = next(f for f in data["findings"] if f["side"] == "target")
            self.assertEqual(finding["classification"], "typed_node_missing_reference")

    def test_both_missing_references(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-something"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "missing-a", "source_type": "node", "target_id": "missing-b", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["edges_with_both_missing_node_references"], 1)

    def test_typed_non_node_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "acc-b", "target_type": "account"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json", "--source-kind", "runtime")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["typed_non_node_references"], 1)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], False)
            self.assertIs(data["policy_signals"]["loose_reference_semantics_observed"], True)
            self.assertIs(data["policy_signals"]["requires_policy_decision"], True)

    def test_typed_unknown_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "ext-1", "source_type": "external", "target_id": "node-a", "target_type": "node"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["typed_unknown_references"], 1)
            self.assertIs(data["policy_signals"]["requires_policy_decision"], True)

    def test_untyped_existing_node_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
            nf.flush()
            # Missing source_type/target_type entirely
            ef.write('{"id": "edge-1", "source_id": "node-a", "target_id": "node-b"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["untyped_existing_node_references"], 2)
            self.assertIs(data["policy_signals"]["requires_policy_decision"], True)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], False)

    def test_untyped_missing_reference(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "edge-1", "source_id": "node-a", "target_id": "missing-b"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["untyped_missing_references"], 1)
            self.assertIs(data["policy_signals"]["requires_cleanup"], True)

    def test_malformed_edge_missing_source_id(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            # Target ID is there, source_id missing
            ef.write('{"id": "edge-1", "target_id": "node-b"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["malformed_edges"], 1)
            self.assertIs(data["policy_signals"]["strict_node_fk_ready"], False)

    def test_invalid_json_line(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{invalid_json}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["invalid_json_records"], 1)

    def test_non_object_json_line(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('["an", "array"]\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            self.assertEqual(data["summary"]["non_object_json_records"], 1)

    def test_redaction_default(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "my-secret-edge-id", "source_id": "my-secret-source-id", "source_type": "node", "target_id": "my-secret-target-id", "target_type": "account"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            out_str = json.dumps(data)
            self.assertNotIn("my-secret", out_str)
            self.assertIn("edge:sha256:", out_str)
            self.assertIn("ref:sha256:", out_str)

    def test_show_ids_opt_in(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
            nf.write('{"id": "node-a"}\n')
            nf.flush()
            ef.write('{"id": "my-secret-edge-id", "source_id": "my-secret-source-id", "source_type": "node", "target_id": "my-secret-target-id", "target_type": "account"}\n')
            ef.flush()

            result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json", "--show-ids")
            self.assertEqual(result.returncode, 0)
            data = json.loads(result.stdout)

            out_str = json.dumps(data)
            self.assertIn("my-secret-edge-id", out_str)
            self.assertIn("my-secret-source-id", out_str)

    def test_postgres_without_database_url_fails(self):
        result = run_script("--postgres", env={})
        self.assertNotEqual(result.returncode, 0)

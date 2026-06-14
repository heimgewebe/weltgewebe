import json
import os
import subprocess
import tempfile
import pytest

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

def test_no_input_fails():
    result = run_script()
    assert result.returncode != 0

def test_missing_nodes_file_fails():
    result = run_script("--nodes-jsonl", "does_not_exist.jsonl", "--edges-jsonl", "also_does_not_exist.jsonl")
    assert result.returncode != 0

def test_missing_edges_file_fails():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nodes_file:
        result = run_script("--nodes-jsonl", nodes_file.name, "--edges-jsonl", "does_not_exist.jsonl")
        assert result.returncode != 0

def test_all_typed_node_references_valid():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["typed_node_references"] == 2
        assert data["policy_signals"]["strict_node_fk_ready"] is True
        assert data["policy_signals"]["requires_runtime_data_run"] is False

def test_all_typed_node_references_valid_but_repo_fixture():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "repo-fixture", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["typed_node_references"] == 2
        assert data["policy_signals"]["strict_node_fk_ready"] is False
        assert data["policy_signals"]["requires_runtime_data_run"] is True

def test_typed_node_missing_source_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-b"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "missing-a", "source_type": "node", "target_id": "node-b", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["typed_node_missing_references"] == 1
        assert data["policy_signals"]["requires_cleanup"] is True
        assert data["policy_signals"]["requires_policy_decision"] is True
        assert data["policy_signals"]["strict_node_fk_ready"] is False

def test_typed_node_missing_target_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "missing-b", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        finding = next(f for f in data["findings"] if f["side"] == "target")
        assert finding["classification"] == "typed_node_missing_reference"

def test_both_missing_references():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-something"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "missing-a", "source_type": "node", "target_id": "missing-b", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["edges_with_both_missing_node_references"] == 1

def test_typed_non_node_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "node-a", "source_type": "node", "target_id": "acc-b", "target_type": "account"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json", "--source-kind", "runtime")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["typed_non_node_references"] == 1
        assert data["policy_signals"]["strict_node_fk_ready"] is False
        assert data["policy_signals"]["loose_reference_semantics_observed"] is True
        assert data["policy_signals"]["requires_policy_decision"] is True

def test_typed_unknown_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "ext-1", "source_type": "external", "target_id": "node-a", "target_type": "node"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["typed_unknown_references"] == 1
        assert data["policy_signals"]["requires_policy_decision"] is True

def test_untyped_existing_node_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n{"id": "node-b"}\n')
        nf.flush()
        # Missing source_type/target_type entirely
        ef.write('{"id": "edge-1", "source_id": "node-a", "target_id": "node-b"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["untyped_existing_node_references"] == 2
        assert data["policy_signals"]["requires_policy_decision"] is True
        assert data["policy_signals"]["strict_node_fk_ready"] is False

def test_untyped_missing_reference():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "edge-1", "source_id": "node-a", "target_id": "missing-b"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["untyped_missing_references"] == 1
        assert data["policy_signals"]["requires_cleanup"] is True

def test_malformed_edge_missing_source_id():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        # Target ID is there, source_id missing
        ef.write('{"id": "edge-1", "target_id": "node-b"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--source-kind", "runtime", "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["malformed_edges"] == 1
        assert data["policy_signals"]["strict_node_fk_ready"] is False

def test_invalid_json_line():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{invalid_json}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["invalid_json_records"] == 1

def test_non_object_json_line():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('["an", "array"]\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        assert data["summary"]["non_object_json_records"] == 1

def test_redaction_default():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "my-secret-edge-id", "source_id": "my-secret-source-id", "source_type": "node", "target_id": "my-secret-target-id", "target_type": "account"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        out_str = json.dumps(data)
        assert "my-secret" not in out_str
        assert "edge:sha256:" in out_str
        assert "ref:sha256:" in out_str

def test_show_ids_opt_in():
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as nf, tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl') as ef:
        nf.write('{"id": "node-a"}\n')
        nf.flush()
        ef.write('{"id": "my-secret-edge-id", "source_id": "my-secret-source-id", "source_type": "node", "target_id": "my-secret-target-id", "target_type": "account"}\n')
        ef.flush()

        result = run_script("--nodes-jsonl", nf.name, "--edges-jsonl", ef.name, "--format", "json", "--show-ids")
        assert result.returncode == 0
        data = json.loads(result.stdout)

        out_str = json.dumps(data)
        assert "my-secret-edge-id" in out_str
        assert "my-secret-source-id" in out_str

def test_postgres_without_database_url_fails():
    result = run_script("--postgres", env={})
    assert result.returncode != 0

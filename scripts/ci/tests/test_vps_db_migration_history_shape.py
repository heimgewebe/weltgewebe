import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "ops" / "check_vps_db_migration_history_shape.py"


def _fake_docker(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "docker"
    path.write_text("#!/usr/bin/env python3\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def _run(fake_docker: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--docker-bin", str(fake_docker), "--json"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def test_missing_history_table_blocks_before_api_start(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
print('history_table=absent')
print('user_relation_count=0')
print('base_table_count=0')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "blocked"
    assert payload["history_table"] == "absent"
    assert payload["reason"] == "app_schema_empty_or_migration_history_absent"
    assert payload["helper_started_api"] is False
    assert payload["helper_applied_migrations"] is False
    assert payload["helper_read_env_file"] is False


def test_present_nonempty_clean_history_passes(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=5')
    print('failed_history_count=0')
    print('duplicate_version_count=0')
else:
    print('history_table=present')
    print('user_relation_count=10')
    print('base_table_count=9')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 0
    assert payload["status"] == "pass"
    assert payload["history_table"] == "present"
    assert payload["history_row_count"] == 5
    assert payload["failed_history_count"] == 0
    assert payload["duplicate_version_count"] == 0


def test_present_but_empty_history_blocks(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=0')
    print('failed_history_count=0')
    print('duplicate_version_count=0')
else:
    print('history_table=present')
    print('user_relation_count=1')
    print('base_table_count=1')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "migration_history_empty"


def test_failed_history_blocks(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=3')
    print('failed_history_count=1')
    print('duplicate_version_count=0')
else:
    print('history_table=present')
    print('user_relation_count=3')
    print('base_table_count=3')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "failed_migration_history_rows"


def test_catalog_probe_error_is_nonpassing(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
print('catalog unavailable', file=sys.stderr)
sys.exit(2)
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "catalog_probe_failed"
    assert "catalog unavailable" in payload["command_error"]


def test_history_only_schema_blocks(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=4')
    print('failed_history_count=0')
    print('duplicate_version_count=0')
else:
    print('history_table=present')
    print('user_relation_count=0')
    print('base_table_count=0')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "app_schema_empty"


def test_duplicate_history_versions_block(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=4')
    print('failed_history_count=0')
    print('duplicate_version_count=1')
else:
    print('history_table=present')
    print('user_relation_count=4')
    print('base_table_count=4')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "blocked"
    assert payload["reason"] == "duplicate_migration_versions"


def test_noninteger_catalog_count_is_error(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
print('history_table=present')
print('user_relation_count=not-a-number')
print('base_table_count=1')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "catalog_probe_failed"


def test_noninteger_history_count_is_error(tmp_path):
    fake = _fake_docker(
        tmp_path,
        """
import sys
script = sys.argv[-1]
if 'history_row_count' in script:
    print('history_row_count=not-a-number')
    print('failed_history_count=0')
    print('duplicate_version_count=0')
else:
    print('history_table=present')
    print('user_relation_count=2')
    print('base_table_count=2')
""",
    )

    result = _run(fake)
    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert payload["status"] == "error"
    assert payload["reason"] == "history_probe_failed"

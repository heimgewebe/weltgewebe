import json
import os
import tempfile
import unittest

from scripts.docmeta.validate_task_index import validate_task_index


def _make_task(**overrides):
    task = {
        "id": "TASK-CTL-001",
        "title": "Task Control Phase 2",
        "area": "docs",
        "status": "open",
        "priority": "high",
        "effort": "M",
        "risk": "medium",
        "owner": "unknown",
        "evidence": [],
        "missing_evidence": ["Evidenz steht aus"],
        "acceptance": ["docs/tasks/ existiert"],
        "links": {"issues": [], "prs": [], "docs": []},
        "updated_at": "2026-05-28",
    }
    task.update(overrides)
    return task


def _make_index(tasks=None, **top_overrides):
    data = {
        "schema_version": "1.0.0",
        "generated_at": None,
        "curation": "manual_phase2_seed",
        "source_files": [],
        "tasks": tasks if tasks is not None else [_make_task()],
    }
    data.update(top_overrides)
    return data


class TestValidateTaskIndex(unittest.TestCase):

    def _write(self, data):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        json.dump(data, f, ensure_ascii=False)
        f.close()
        return f.name

    # -------------------------------------------------------------------------
    # Passing cases
    # -------------------------------------------------------------------------

    def test_valid_seed_passes(self):
        path = self._write(_make_index())
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_high_priority_with_acceptance_passes(self):
        path = self._write(_make_index([_make_task(priority="high", acceptance=["criterion"])]))
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_done_with_evidence_passes(self):
        path = self._write(
            _make_index([_make_task(status="done", evidence=["some/proof/file.rs"])])
        )
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_missing_docs_path_explained_passes(self):
        path = self._write(
            _make_index([
                _make_task(
                    links={"issues": [], "prs": [], "docs": ["docs/nonexistent.md"]},
                    missing_evidence=["docs/nonexistent.md nicht vorhanden"],
                )
            ])
        )
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_medium_priority_empty_acceptance_passes(self):
        path = self._write(
            _make_index([_make_task(id="OPT-CI-001", priority="medium", acceptance=[])])
        )
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_generated_at_null_passes(self):
        path = self._write(_make_index(generated_at=None))
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    def test_generated_at_string_passes(self):
        path = self._write(_make_index(generated_at="2026-05-28T17:00:00Z"))
        try:
            self.assertEqual(validate_task_index(path), [])
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # Duplicate ID
    # -------------------------------------------------------------------------

    def test_duplicate_ids_fail(self):
        tasks = [_make_task(), _make_task()]
        path = self._write(_make_index(tasks))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("duplicate" in e for e in errors), errors)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # High priority / done business rules
    # -------------------------------------------------------------------------

    def test_high_priority_without_acceptance_fails(self):
        path = self._write(_make_index([_make_task(priority="high", acceptance=[])]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("acceptance" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_done_without_evidence_fails(self):
        path = self._write(_make_index([_make_task(status="done", evidence=[])]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("evidence" in e for e in errors), errors)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # Path checks
    # -------------------------------------------------------------------------

    def test_missing_docs_path_unexplained_fails(self):
        path = self._write(
            _make_index([
                _make_task(
                    links={"issues": [], "prs": [], "docs": ["docs/nonexistent/path.md"]},
                    missing_evidence=[],
                )
            ])
        )
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(
                any("docs/nonexistent/path.md" in e for e in errors), errors
            )
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # Enum / pattern failures
    # -------------------------------------------------------------------------

    def test_invalid_status_fails(self):
        path = self._write(_make_index([_make_task(status="inprogress")]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("status" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_invalid_id_pattern_fails(self):
        path = self._write(_make_index([_make_task(id="task-001")]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(
                any("id" in e.lower() or "pattern" in e.lower() for e in errors), errors
            )
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # Missing required field
    # -------------------------------------------------------------------------

    def test_missing_required_task_field_fails(self):
        task = _make_task()
        del task["title"]
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("title" in e for e in errors), errors)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # File not found
    # -------------------------------------------------------------------------

    def test_file_not_found_returns_error(self):
        errors = validate_task_index("/tmp/does_not_exist_XYZ_weltgewebe.json")
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("not found" in e for e in errors), errors)

    # -------------------------------------------------------------------------
    # Top-level schema enforcement
    # -------------------------------------------------------------------------

    def test_missing_curation_fails(self):
        data = _make_index()
        del data["curation"]
        path = self._write(data)
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("curation" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_missing_source_files_fails(self):
        data = _make_index()
        del data["source_files"]
        path = self._write(data)
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("source_files" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_extra_top_level_key_fails(self):
        data = _make_index()
        data["unexpected_key"] = "surprise"
        path = self._write(data)
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("unexpected_key" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_source_files_as_string_fails(self):
        data = _make_index()
        data["source_files"] = "not-an-array"
        path = self._write(data)
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("source_files" in e for e in errors), errors)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # Task-level schema enforcement
    # -------------------------------------------------------------------------

    def test_extra_task_key_fails(self):
        task = _make_task()
        task["surprise_field"] = "unexpected"
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("surprise_field" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_evidence_as_string_fails(self):
        task = _make_task(evidence="not-an-array")
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("evidence" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_acceptance_as_string_fails(self):
        task = _make_task(acceptance="not-an-array")
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("acceptance" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_missing_evidence_as_string_fails(self):
        task = _make_task(missing_evidence="not-an-array")
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("missing_evidence" in e for e in errors), errors)
        finally:
            os.unlink(path)

    # -------------------------------------------------------------------------
    # links schema enforcement
    # -------------------------------------------------------------------------

    def test_links_docs_as_string_fails(self):
        task = _make_task(links={"issues": [], "prs": [], "docs": "not-an-array"})
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("docs" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_links_extra_key_fails(self):
        task = _make_task(links={"issues": [], "prs": [], "docs": [], "extra": "nope"})
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("extra" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_links_issues_wrong_type_fails(self):
        task = _make_task(links={"issues": "string", "prs": [], "docs": []})
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("issues" in e for e in errors), errors)
        finally:
            os.unlink(path)

    def test_links_prs_wrong_type_fails(self):
        task = _make_task(links={"issues": [], "prs": 42, "docs": []})
        path = self._write(_make_index([task]))
        try:
            errors = validate_task_index(path)
            self.assertGreater(len(errors), 0)
            self.assertTrue(any("prs" in e for e in errors), errors)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

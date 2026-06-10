import os
import tempfile
import unittest

from scripts.docmeta.docmeta import (
    REPO_ROOT,
    parse_frontmatter,
    parse_repo_index,
    parse_review_policy,
    extract_depends_on,
)

class TestDocMetaParser(unittest.TestCase):
    def test_parse_frontmatter_crlf_eof(self):
        content = "---\r\nid: test-id\r\nrole: norm\r\n---"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-id')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_spacing(self):
        content = "---\n id : test \n role : norm \n---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test')
            self.assertEqual(data.get('role'), 'norm')
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_block_list(self):
        content = "---\n" \
                  "id: test-block\n" \
                  "organ: governance\n" \
                  "verifies_with:\n" \
                  "  - scripts/a.py\n" \
                  "  - scripts/b.py\n" \
                  "depends_on: []\n" \
                  "audit_gaps:\n" \
                  "  - first known debt\n" \
                  "  - second known debt\n" \
                  "---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-block')
            self.assertEqual(data.get('organ'), 'governance')
            self.assertEqual(data.get('verifies_with'), ['scripts/a.py', 'scripts/b.py'])
            self.assertEqual(data.get('depends_on'), [])
            self.assertEqual(data.get('audit_gaps'), ['first known debt', 'second known debt'])
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_empty_organ_and_unknown_block_list(self):
        content = "---\n" \
                  "id: test-robustness\n" \
                  "organ:\n" \
                  "tags:\n" \
                  "  - architecture\n" \
                  "  - draft\n" \
                  "verifies_with:\n" \
                  "  - scripts/verify.py\n" \
                  "---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-robustness')
            # 'organ' missing value should be parsed as empty string
            self.assertEqual(data.get('organ'), '')
            # 'tags' blocklist shouldn't be parsed since it's not whitelisted
            self.assertEqual(data.get('tags'), '')
            self.assertEqual(data.get('verifies_with'), ['scripts/verify.py'])
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_inline_list(self):
        content = "---\n" \
                  "id: test-inline\n" \
                  "organ: runtime\n" \
                  "verifies_with: [scripts/x.py, scripts/y.py]\n" \
                  "---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-inline')
            self.assertEqual(data.get('organ'), 'runtime')
            self.assertEqual(data.get('verifies_with'), ['scripts/x.py', 'scripts/y.py'])
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_inline_audit_gaps(self):
        content = "---\n" \
                  "id: test-inline-gaps\n" \
                  "audit_gaps: [inline gap 1, inline gap 2]\n" \
                  "---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            self.assertEqual(data.get('id'), 'test-inline-gaps')
            self.assertEqual(data.get('audit_gaps'), ['inline gap 1', 'inline gap 2'])
        finally:
            os.remove(temp_path)

    def _parse_depends_on(self, fragment):
        content = f"---\nid: dep-doc\n{fragment}---\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        try:
            data = parse_frontmatter(temp_path)
            self.assertIsNotNone(data)
            return data
        finally:
            os.remove(temp_path)

    def test_parse_frontmatter_depends_on_inline_empty(self):
        """Real markdown ``depends_on: []`` parses to an empty list, not a string."""
        data = self._parse_depends_on("depends_on: []\n")
        self.assertEqual(data.get('depends_on'), [])
        self.assertIsInstance(data.get('depends_on'), list)

    def test_parse_frontmatter_depends_on_block_list(self):
        """Real markdown block list parses to a list of IDs."""
        data = self._parse_depends_on("depends_on:\n  - doc-a\n  - doc-b\n")
        self.assertEqual(data.get('depends_on'), ['doc-a', 'doc-b'])

    def test_parse_frontmatter_depends_on_scalar_stays_scalar(self):
        """A bare scalar ``depends_on: doc-a`` must NOT be silently wrapped into
        ``['doc-a']``; it stays a string so schema validation can flag the type."""
        data = self._parse_depends_on("depends_on: doc-a\n")
        self.assertEqual(data.get('depends_on'), 'doc-a')
        self.assertNotIsInstance(data.get('depends_on'), list)

class TestDocMetaStrictParsers(unittest.TestCase):
    def test_repo_index_typo_fail(self):
        content = "---\nzonez:\n  norm:\n    path: architecture/\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Unknown key at root level 'zonez'"):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_strict_manifest_missing_canonical_docs_fails(self):
        content = "---\nzones:\n  norm:\n    path: architecture/\nchecks:\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Strict Mode: Zone 'norm' has no canonical_docs."):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_review_policy_missing_mode(self):
        content = "---\nwarn_days: 90\nfail_days: 180\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Missing required key 'mode'"):
                parse_review_policy(policy_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_missing_cycle_days(self):
        content = "---\nmode: warn\nfail_days: 180\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Missing required key 'warn_days'"):
                parse_review_policy(policy_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_invalid_days(self):
        content = "---\nwarn_days: x\nfail_days: 180\nmode: warn\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Invalid warn_days.*Must be a positive integer."):
                parse_review_policy(policy_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_review_policy_fail_days_must_exceed_warn_days(self):
        content = "---\nwarn_days: 90\nfail_days: 90\nmode: warn\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name
        try:
            with self.assertRaisesRegex(ValueError, r"fail_days.*must be greater than warn_days"):
                parse_review_policy(policy_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_repo_index_excessive_whitespace(self):
        content = """
# some comments

zones:
  norm:
    path: architecture/
    canonical_docs:
      - doc1.md

      - doc2.md

checks:
  - check.py
"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            data = parse_repo_index(manifest_path=temp_path)
            self.assertEqual(len(data['zones']['norm']['canonical_docs']), 2)
            self.assertEqual(data['checks'][0], 'check.py')
        finally:
            os.remove(temp_path)

    def test_strict_manifest_empty_zones_fails(self):
        content = "---\nzones:\nchecks:\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "The 'zones' section cannot be empty when strict_manifest=True"):
                parse_repo_index(manifest_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)

    def test_repo_index_malformed_missing_colon(self):
        content = "zones\n  norm:\n    path: architecture/\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Expected key-value or key: at root level"):
                parse_repo_index(manifest_path=temp_path)
        finally:
            os.remove(temp_path)

    def test_review_policy_unknown_key_strict_fail(self):
        content = "---\nwarn_days: 90\nfail_days: 180\nmode: warn\nstrict_manifest: true\nunknown_key: val\n"
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_path = f.name

        try:
            with self.assertRaisesRegex(ValueError, "Unknown key 'unknown_key' in review policy"):
                parse_review_policy(policy_path=temp_path, strict_manifest=True)
        finally:
            os.remove(temp_path)


class TestExtractDependsOn(unittest.TestCase):
    """Dependency extraction: direct ``depends_on`` is canonical, ``relations`` is fallback."""

    def test_direct_depends_on_is_read(self):
        fm = {'depends_on': ['doc-a', 'doc-b']}
        self.assertEqual(extract_depends_on(fm), ['doc-a', 'doc-b'])

    def test_empty_direct_depends_on_returns_empty_list(self):
        fm = {'depends_on': []}
        self.assertEqual(extract_depends_on(fm), [])

    def test_direct_depends_on_wins_over_relations(self):
        fm = {
            'depends_on': ['doc-a'],
            'relations': [{'type': 'depends_on', 'target': 'doc-legacy'}],
        }
        self.assertEqual(extract_depends_on(fm), ['doc-a'])

    def test_empty_direct_depends_on_wins_over_relations(self):
        """An explicit empty list wins; it must not silently fall back to relations."""
        fm = {
            'depends_on': [],
            'relations': [{'type': 'depends_on', 'target': 'doc-legacy'}],
        }
        self.assertEqual(extract_depends_on(fm), [])

    def test_legacy_relations_fallback_when_direct_absent(self):
        fm = {'relations': [{'type': 'depends_on', 'target': 'doc-legacy'}]}
        self.assertEqual(extract_depends_on(fm), ['doc-legacy'])

    def test_malformed_direct_depends_on_does_not_fallback_to_relations(self):
        """A present-but-non-list ``depends_on`` key blocks the legacy fallback.
        Extraction returns [] and schema validation is responsible for the type error."""
        fm = {
            'depends_on': 'doc-a',
            'relations': [{'type': 'depends_on', 'target': 'doc-legacy'}],
        }
        self.assertEqual(extract_depends_on(fm), [])

    def test_no_dependencies_at_all(self):
        self.assertEqual(extract_depends_on({}), [])


class TestRepoWideCanonicalDocInvariant(unittest.TestCase):
    """Every canonical doc listed in manifest/repo-index.yaml must carry
    an ``id`` (str), a ``depends_on`` (list), and a ``verifies_with`` (list)
    after frontmatter parsing.  This reads the real manifest and real files.

    Enforcement at runtime is owned by the docmeta schema guard
    (``validate_schema.py`` + ``contracts/docmeta.schema.json``, which marks
    these fields ``required``).  This test is independent proof on the raw
    ``parse_frontmatter`` output — it does not rely on the validator's list
    coercion shim, so it catches files that only pass via normalization."""

    def test_canonical_docs_have_required_list_fields(self):
        manifest_path = os.path.join(REPO_ROOT, "manifest", "repo-index.yaml")
        if not os.path.exists(manifest_path):
            self.skipTest(f"manifest/repo-index.yaml not found at {manifest_path}")

        repo_index = parse_repo_index(manifest_path=manifest_path)
        zones = repo_index.get("zones", {})
        self.assertTrue(zones, "repo-index.yaml must define at least one zone")

        failures = []
        for zone_name, zone_data in zones.items():
            rel_zone_path = zone_data.get("path", "")
            for doc_file in zone_data.get("canonical_docs", []):
                rel_path = os.path.join(rel_zone_path, doc_file)
                full_path = os.path.join(REPO_ROOT, rel_path)
                if not os.path.exists(full_path):
                    failures.append(f"{rel_path}: file not found")
                    continue
                fm = parse_frontmatter(full_path)
                if fm is None:
                    failures.append(f"{rel_path}: no frontmatter")
                    continue
                doc_id = fm.get("id")
                if not isinstance(doc_id, str) or not doc_id:
                    failures.append(f"{rel_path}: 'id' missing or not a non-empty string")
                depends_on = fm.get("depends_on")
                if not isinstance(depends_on, list):
                    failures.append(
                        f"{rel_path}: 'depends_on' is {type(depends_on).__name__!r}, "
                        "expected list (use 'depends_on: []' for empty)"
                    )
                verifies_with = fm.get("verifies_with")
                if not isinstance(verifies_with, list):
                    failures.append(
                        f"{rel_path}: 'verifies_with' is {type(verifies_with).__name__!r}, "
                        "expected list (use 'verifies_with: []' for empty)"
                    )

        if failures:
            self.fail(
                f"{len(failures)} canonical doc(s) failed invariant check:\n"
                + "\n".join(f"  - {f}" for f in failures)
            )


if __name__ == '__main__':
    unittest.main()

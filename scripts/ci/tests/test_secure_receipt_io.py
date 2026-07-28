#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "ops" / "weltgewebe_secure_receipt_io.py"
SPEC = importlib.util.spec_from_file_location("weltgewebe_secure_receipt_io", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
secure_io = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(secure_io)


class SecureReceiptIoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.root.chmod(0o700)
        self.uid = os.geteuid()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_round_trip_is_atomic_bounded_and_mode_0600(self) -> None:
        path = self.root / "receipt.json"
        payload = {"schema_version": 1, "value": "Wale 🐋"}

        secure_io.write_secure_json(path, payload, expected_uid=self.uid)

        self.assertEqual(
            secure_io.read_secure_json(path, expected_uid=self.uid), payload
        )
        metadata = path.stat()
        self.assertEqual(stat.S_IMODE(metadata.st_mode), 0o600)
        self.assertEqual(metadata.st_nlink, 1)
        self.assertFalse(list(self.root.glob(".receipt.json.*.tmp")))

    def test_encoding_mode_preserves_existing_writer_contracts(self) -> None:
        path = self.root / "receipt.json"
        secure_io.write_secure_json(
            path, {"value": "🐋"}, expected_uid=self.uid
        )
        self.assertIn("\\ud83d\\udc0b", path.read_text(encoding="utf-8"))

        secure_io.write_secure_json(
            path,
            {"value": "🐋"},
            expected_uid=self.uid,
            ensure_ascii=False,
        )
        self.assertIn("🐋", path.read_text(encoding="utf-8"))

    def test_missing_ok_only_relaxes_absence(self) -> None:
        path = self.root / "missing.json"
        self.assertIsNone(
            secure_io.read_secure_json(path, expected_uid=self.uid, missing_ok=True)
        )
        with self.assertRaises(FileNotFoundError):
            secure_io.read_secure_json(path, expected_uid=self.uid)

    def test_invalid_json_is_payload_error(self) -> None:
        path = self.root / "receipt.json"
        path.write_text("{not-json", encoding="utf-8")
        path.chmod(0o600)

        with self.assertRaises(secure_io.SecurePayloadError):
            secure_io.read_secure_json(path, expected_uid=self.uid)

    def test_non_object_json_is_payload_error(self) -> None:
        path = self.root / "receipt.json"
        path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        path.chmod(0o600)

        with self.assertRaises(secure_io.SecurePayloadError):
            secure_io.read_secure_json(path, expected_uid=self.uid)

    def test_symlink_and_hardlink_are_metadata_errors(self) -> None:
        target = self.root / "target.json"
        target.write_text("{}", encoding="utf-8")
        target.chmod(0o600)
        symlink = self.root / "symlink.json"
        symlink.symlink_to(target.name)
        hardlink = self.root / "hardlink.json"
        os.link(target, hardlink)

        with self.assertRaises(secure_io.SecureMetadataError):
            secure_io.read_secure_json(symlink, expected_uid=self.uid)
        with self.assertRaises(secure_io.SecureMetadataError):
            secure_io.read_secure_json(hardlink, expected_uid=self.uid)

    def test_world_writable_directory_is_rejected(self) -> None:
        self.root.chmod(0o722)
        with self.assertRaises(secure_io.SecureMetadataError):
            secure_io.write_secure_json(
                self.root / "receipt.json", {}, expected_uid=self.uid
            )

    def test_payload_limit_fails_before_target_creation(self) -> None:
        path = self.root / "receipt.json"
        with self.assertRaises(secure_io.SecurePayloadError):
            secure_io.write_secure_json(
                path,
                {"value": "x" * 1024},
                expected_uid=self.uid,
                max_bytes=32,
            )
        self.assertFalse(path.exists())

    def test_default_contract_is_root_bound(self) -> None:
        if self.uid == 0:
            self.skipTest("test runner is already root")
        with self.assertRaises(secure_io.SecureMetadataError):
            secure_io.validate_secure_directory(self.root)


if __name__ == "__main__":
    unittest.main()

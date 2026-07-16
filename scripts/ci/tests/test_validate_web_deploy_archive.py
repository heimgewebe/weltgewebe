from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[2] / "ops" / "validate_web_deploy_archive.py"
SPEC = importlib.util.spec_from_file_location("validate_web_deploy_archive", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

ArchiveValidationError = MODULE.ArchiveValidationError
validate_archive = MODULE.validate_archive


class ValidateWebDeployArchiveTests(unittest.TestCase):
    def make_archive(
        self, members: list[tarfile.TarInfo], payload: bytes = b"ok"
    ) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "web.tar.gz"
        with tarfile.open(path, mode="w:gz") as bundle:
            for member in members:
                if member.isfile():
                    member.size = len(payload)
                    bundle.addfile(member, io.BytesIO(payload))
                else:
                    bundle.addfile(member)
        return path

    def valid_members(self) -> list[tarfile.TarInfo]:
        root = tarfile.TarInfo("build/")
        root.type = tarfile.DIRTYPE
        app = tarfile.TarInfo("build/_app/")
        app.type = tarfile.DIRTYPE
        return [
            root,
            app,
            tarfile.TarInfo("build/index.html"),
            tarfile.TarInfo("build/_app/version.json"),
        ]

    def test_accepts_regular_build_tree(self) -> None:
        summary = validate_archive(self.make_archive(self.valid_members()))
        self.assertEqual(summary.member_count, 4)
        self.assertEqual(summary.expanded_bytes, 4)
        self.assertEqual(summary.largest_file_bytes, 2)

    def test_rejects_path_outside_build_tree(self) -> None:
        members = self.valid_members() + [tarfile.TarInfo("etc/passwd")]
        with self.assertRaisesRegex(ArchiveValidationError, "unexpected archive path"):
            validate_archive(self.make_archive(members))

    def test_rejects_symlink(self) -> None:
        member = tarfile.TarInfo("build/current")
        member.type = tarfile.SYMTYPE
        member.linkname = "/etc"
        with self.assertRaisesRegex(ArchiveValidationError, "unsupported archive member type"):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_duplicate_canonical_path(self) -> None:
        members = self.valid_members() + [tarfile.TarInfo("build/index.html")]
        with self.assertRaisesRegex(ArchiveValidationError, "duplicate archive path"):
            validate_archive(self.make_archive(members))

    def test_rejects_noncanonical_path(self) -> None:
        members = self.valid_members() + [tarfile.TarInfo("build//extra.js")]
        with self.assertRaisesRegex(ArchiveValidationError, "non-canonical archive path"):
            validate_archive(self.make_archive(members))

    def test_rejects_control_character(self) -> None:
        members = self.valid_members() + [tarfile.TarInfo("build/bad\nname")]
        with self.assertRaisesRegex(ArchiveValidationError, "unsafe archive path characters"):
            validate_archive(self.make_archive(members))

    def test_rejects_elevated_permission_bits(self) -> None:
        member = tarfile.TarInfo("build/helper")
        member.mode = 0o4755
        with self.assertRaisesRegex(ArchiveValidationError, "elevated permission bits"):
            validate_archive(self.make_archive(self.valid_members() + [member]))

    def test_rejects_expanded_size_limit(self) -> None:
        archive = self.make_archive(self.valid_members(), payload=b"four")
        with self.assertRaisesRegex(ArchiveValidationError, "expanded limit"):
            validate_archive(archive, max_expanded_bytes=7)

    def test_rejects_per_file_size_limit(self) -> None:
        archive = self.make_archive(self.valid_members(), payload=b"four")
        with self.assertRaisesRegex(ArchiveValidationError, "per-file limit"):
            validate_archive(archive, max_file_bytes=3)

    def test_requires_version_contract(self) -> None:
        members = self.valid_members()[:-1]
        with self.assertRaisesRegex(ArchiveValidationError, "missing required regular files"):
            validate_archive(self.make_archive(members))


if __name__ == "__main__":
    unittest.main()

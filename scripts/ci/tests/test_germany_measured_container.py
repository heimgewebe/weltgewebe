from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "basemap" / "run-measured-container.py"
SPEC = importlib.util.spec_from_file_location("measured_container", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class GermanyMeasuredContainerTest(unittest.TestCase):
    def test_parses_docker_binary_and_decimal_sizes(self) -> None:
        self.assertEqual(MODULE.parse_size("1KiB"), 1024)
        self.assertEqual(MODULE.parse_size("1.5MiB"), 1572864)
        self.assertEqual(MODULE.parse_size("2MB"), 2000000)
        self.assertEqual(
            MODULE.parse_pair("1GiB / 2GiB"), (1073741824, 2147483648)
        )

    def test_rejects_unknown_size_units(self) -> None:
        with self.assertRaisesRegex(MODULE.MeasurementError, "unrecognized"):
            MODULE.parse_size("12 bananas")

    def test_workspace_measurement_ignores_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "a.bin").write_bytes(b"a" * 10)
            child = root / "child"
            child.mkdir()
            (child / "b.bin").write_bytes(b"b" * 20)
            (root / "loop").symlink_to(root, target_is_directory=True)
            self.assertEqual(MODULE.workspace_bytes(root), 30)


if __name__ == "__main__":
    unittest.main()

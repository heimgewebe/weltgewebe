from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
BUILDER = REPO / "scripts" / "basemap" / "build-schleswig-holstein-pmtiles.sh"
INPUT_SHA256 = "3e5efb30488daa87a098d61bf1f60155f89cdcf900aeadee5a1cd27910bfd450"


class SchleswigHolsteinBasemapBuilderTest(unittest.TestCase):
    def test_transient_planetiler_failures_retry_without_reusing_partial_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            script = root / "scripts" / "basemap" / BUILDER.name
            script.parent.mkdir(parents=True)
            shutil.copy2(BUILDER, script)

            basemap_dir = root / "build" / "basemap"
            basemap_dir.mkdir(parents=True)
            (basemap_dir / "schleswig-holstein-260101.osm.pbf").write_bytes(b"fixture")

            fake_bin = root / "fake-bin"
            fake_bin.mkdir()
            count_path = root / "docker-count"
            reuse_path = root / "partial-output-reused"
            output_path = basemap_dir / "basemap-schleswig-holstein-v0.1.0.pmtiles"

            self._write_executable(
                fake_bin / "sha256sum",
                f'''#!/usr/bin/env bash
printf '%s  %s\\n' "{INPUT_SHA256}" "$1"
''',
            )
            self._write_executable(
                fake_bin / "sleep",
                "#!/usr/bin/env bash\nexit 0\n",
            )
            self._write_executable(
                fake_bin / "docker",
                '''#!/usr/bin/env bash
set -euo pipefail
count=0
if [[ -f "$MOCK_DOCKER_COUNT" ]]; then
  count="$(cat "$MOCK_DOCKER_COUNT")"
fi
count=$((count + 1))
printf '%s\\n' "$count" > "$MOCK_DOCKER_COUNT"
if [[ -e "$MOCK_OUTPUT" ]]; then
  printf 'partial output was reused on attempt %s\\n' "$count" > "$MOCK_REUSE_MARKER"
  exit 91
fi
printf 'partial-%s' "$count" > "$MOCK_OUTPUT"
if [[ "$count" -lt 3 ]]; then
  exit 1
fi
printf 'PMTiles\\003fixture' > "$MOCK_OUTPUT"
''',
            )

            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{fake_bin}:{environment['PATH']}",
                    "PLANETILER_MAX_ATTEMPTS": "3",
                    "PLANETILER_RETRY_DELAY_SECONDS": "0",
                    "MOCK_DOCKER_COUNT": str(count_path),
                    "MOCK_OUTPUT": str(output_path),
                    "MOCK_REUSE_MARKER": str(reuse_path),
                }
            )

            completed = subprocess.run(
                ["bash", str(script)],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(count_path.read_text(encoding="utf-8").strip(), "3")
            self.assertFalse(reuse_path.exists())
            self.assertTrue(output_path.read_bytes().startswith(b"PMTiles"))

            metadata = json.loads(
                (basemap_dir / "basemap-schleswig-holstein-v0.1.0.meta.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(metadata["region"], "schleswig-holstein")
            self.assertEqual(metadata["status"], "ready")
            self.assertIn("retrying", completed.stderr)

    @staticmethod
    def _write_executable(path: Path, content: str) -> None:
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()

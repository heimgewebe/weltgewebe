"""Coverage for the VPS HTTP smoke Caddy preflight contract."""

from __future__ import annotations

import os
import pathlib
import subprocess
import tempfile
import unittest


class VpsHttpSmokeCspContractTest(unittest.TestCase):
    def test_vps_http_smoke_caddyfile_matches_static_csp_guard_target(self) -> None:
        repo = pathlib.Path(__file__).resolve().parents[3]
        guard = repo / "scripts" / "preflight" / "csp_contract_static.sh"
        smoke_caddyfile = repo / "infra" / "caddy" / "Caddyfile.http-smoke"

        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            build_dir = root / "apps" / "web" / "build"
            build_dir.mkdir(parents=True)
            (build_dir / "index.html").write_text(
                '<html><head><script>console.log("inline")</script></head></html>',
                encoding="utf-8",
            )

            env = os.environ.copy()
            env.update(
                {
                    "ROOT": str(root),
                    "REQUIRE_FRONTEND": "1",
                    "CADDYFILE_PATH": str(smoke_caddyfile),
                    "CADDY_TARGET_SITE": "weltgewebe.net",
                }
            )

            result = subprocess.run(
                ["bash", str(guard)],
                cwd=repo,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )


if __name__ == "__main__":
    unittest.main()

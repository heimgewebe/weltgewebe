"""Coverage for the route-only VPS HTTP smoke security boundary."""

from __future__ import annotations

import http.client
import pathlib
import shutil
import socket
import subprocess
import tempfile
import time
import unittest


class VpsHttpSmokeCspContractTest(unittest.TestCase):
    def test_route_only_smoke_has_strict_non_app_baseline(self) -> None:
        repo = pathlib.Path(__file__).resolve().parents[3]
        smoke = (repo / "infra" / "caddy" / "Caddyfile.http-smoke").read_text(
            encoding="utf-8"
        )

        # This surface deliberately never serves the Svelte app, so it can use a
        # strict header CSP without conflicting with SvelteKit's hash-authorized
        # inline bootstrap. It must not be treated as a frontend CSP smoke.
        self.assertIn("default-src 'none'", smoke)
        self.assertIn("frame-ancestors 'none'", smoke)
        self.assertIn('X-Content-Type-Options "nosniff"', smoke)
        self.assertNotIn("'unsafe-inline'", smoke)
        self.assertNotIn("file_server", smoke)
        self.assertIn('respond "dns-free smoke only" 404', smoke)


    @unittest.skipUnless(shutil.which("caddy"), "caddy binary required for runtime header proof")
    def test_route_only_smoke_runtime_emits_strict_csp_headers(self) -> None:
        repo = pathlib.Path(__file__).resolve().parents[3]
        source = (repo / "infra" / "caddy" / "Caddyfile.http-smoke").read_text(encoding="utf-8")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        runtime = "{\n    admin off\n}\n\n" + source.replace(
            "http://commonthing.net", f"http://127.0.0.1:{port}"
        )
        with tempfile.TemporaryDirectory() as tmp:
            config = pathlib.Path(tmp) / "Caddyfile"
            config.write_text(runtime, encoding="utf-8")
            process = subprocess.Popen(
                ["caddy", "run", "--config", str(config), "--adapter", "caddyfile"],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                deadline = time.monotonic() + 5
                response = None
                while time.monotonic() < deadline:
                    try:
                        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
                        connection.request("GET", "/unmatched")
                        response = connection.getresponse()
                        break
                    except OSError:
                        time.sleep(0.05)
                if response is None:
                    stderr = process.stderr.read() if process.stderr else ""
                    self.fail(f"caddy smoke runtime did not become ready: {stderr}")
                self.assertEqual(response.status, 404)
                policy = response.getheader("Content-Security-Policy") or ""
                self.assertIn("default-src 'none'", policy)
                self.assertIn("frame-ancestors 'none'", policy)
                self.assertNotIn("unsafe-inline", policy)
                self.assertEqual(response.getheader("X-Content-Type-Options"), "nosniff")
                self.assertTrue((response.getheader("Content-Type") or "").startswith("text/plain"))
                response.read()
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def test_production_static_csp_guard_does_not_target_route_only_smoke(self) -> None:
        repo = pathlib.Path(__file__).resolve().parents[3]
        workflow = (repo / ".github" / "workflows" / "deploy-check.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("CADDYFILE_PATH=infra/caddy/Caddyfile.heim", workflow)
        self.assertNotIn("CADDYFILE_PATH=infra/caddy/Caddyfile.http-smoke", workflow)


if __name__ == "__main__":
    unittest.main()

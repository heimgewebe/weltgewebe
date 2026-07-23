from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[3]
CASES = (
    ("infra/caddy/Caddyfile", None),
    ("infra/caddy/Caddyfile.heim", "weltgewebe.home.arpa"),
    ("infra/caddy/Caddyfile.vps", "weltgewebe.net"),
)


def adapt(relative: str) -> dict:
    result = subprocess.run(
        ["caddy", "adapt", "--config", relative, "--adapter", "caddyfile"],
        cwd=REPO, text=True, capture_output=True, check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
    return json.loads(result.stdout)


def app_routes(config: dict, host: str | None) -> list[dict]:
    servers = config["apps"]["http"]["servers"]
    if host is None:
        return next(iter(servers.values()))["routes"]
    for server in servers.values():
        if ":443" not in server.get("listen", []):
            continue
        for route in server.get("routes", []):
            matches = route.get("match", [])
            if any(host in matcher.get("host", []) for matcher in matches):
                handles = route.get("handle", [])
                if len(handles) == 1 and handles[0].get("handler") == "subroute":
                    return handles[0].get("routes", [])
    raise AssertionError(f"no HTTPS app route for {host}")


def collect_csp(routes: list[dict]) -> list[tuple[object, str]]:
    found: list[tuple[object, str]] = []
    for route in routes:
        for handler in route.get("handle", []):
            if handler.get("handler") == "headers":
                values = handler.get("response", {}).get("set", {}).get("Content-Security-Policy", [])
                found.extend((route.get("match"), value) for value in values)
            if handler.get("handler") == "subroute":
                found.extend(collect_csp(handler.get("routes", [])))
    return found


@unittest.skipUnless(shutil.which("caddy"), "caddy binary required")
class StaticAppCaddyAdaptedCspTest(unittest.TestCase):
    def test_adapted_app_route_has_only_split_csp_pair(self) -> None:
        for relative, host in CASES:
            with self.subTest(caddyfile=relative):
                policies = collect_csp(app_routes(adapt(relative), host))
                self.assertEqual(len(policies), 2, policies)
                strict = [item for item in policies if "default-src 'none'" in item[1]]
                frontend = [item for item in policies if "default-src 'none'" not in item[1]]
                self.assertEqual(len(strict), 1, policies)
                self.assertEqual(len(frontend), 1, policies)
                self.assertIn("frame-ancestors 'none'", strict[0][1])
                self.assertNotIn("unsafe-inline", strict[0][1])
                directives = {part.strip().split()[0] for part in frontend[0][1].split(";") if part.strip()}
                self.assertNotIn("default-src", directives)
                self.assertNotIn("script-src", directives)
                self.assertIn("frame-ancestors", directives)
                self.assertIn("not", json.dumps(frontend[0][0]))


if __name__ == "__main__":
    unittest.main()

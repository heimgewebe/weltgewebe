from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import unittest

REPO = Path(__file__).resolve().parents[3]
MAGIC_LINK_CONFIRM_PATH = "/api/auth/magic-link/consume"
MAGIC_POLICY = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none';"
STRICT_POLICY = "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';"
CASES = (
    ("infra/caddy/Caddyfile", None, ["/api/*"]),
    ("infra/caddy/Caddyfile.heim", "weltgewebe.home.arpa", ["/api/*"]),
    ("infra/caddy/Caddyfile.vps", "weltgewebe.net", ["/api/*", "/health/*"]),
)


def adapt(relative: str) -> dict:
    result = subprocess.run(
        ["caddy", "adapt", "--config", relative, "--adapter", "caddyfile"],
        cwd=REPO,
        text=True,
        capture_output=True,
        check=False,
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


def collect_csp(routes: list[dict]) -> list[dict]:
    found: list[dict] = []
    for route in routes:
        for handler in route.get("handle", []):
            if handler.get("handler") == "headers":
                response = handler.get("response", {})
                for value in response.get("set", {}).get("Content-Security-Policy", []):
                    found.append(
                        {
                            "match": route.get("match"),
                            "policy": value,
                            "deferred": response.get("deferred", False),
                        }
                    )
            if handler.get("handler") == "subroute":
                found.extend(collect_csp(handler.get("routes", [])))
    return found


def directive_map(policy: str) -> dict[str, tuple[str, ...]]:
    directives: dict[str, tuple[str, ...]] = {}
    for raw in policy.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split()
        directives[parts[0]] = tuple(parts[1:])
    return directives


@unittest.skipUnless(shutil.which("caddy"), "caddy binary required")
class StaticAppCaddyAdaptedCspTest(unittest.TestCase):
    def test_adapted_app_route_has_exact_matchers_and_canonical_edge_csp(self) -> None:
        for relative, host, protected_paths in CASES:
            with self.subTest(caddyfile=relative):
                policies = collect_csp(app_routes(adapt(relative), host))
                self.assertEqual(len(policies), 3, policies)

                magic = [item for item in policies if item["policy"] == MAGIC_POLICY]
                strict = [item for item in policies if item["policy"] == STRICT_POLICY]
                frontend = [
                    item
                    for item in policies
                    if item["policy"] not in {MAGIC_POLICY, STRICT_POLICY}
                ]
                self.assertEqual(len(magic), 1, policies)
                self.assertEqual(len(strict), 1, policies)
                self.assertEqual(len(frontend), 1, policies)

                magic_match = [
                    {
                        "method": ["GET"],
                        "path": [MAGIC_LINK_CONFIRM_PATH],
                    }
                ]
                strict_match = [
                    {
                        "not": [
                            {
                                "method": ["GET"],
                                "path": [MAGIC_LINK_CONFIRM_PATH],
                            }
                        ],
                        "path": protected_paths,
                    }
                ]
                frontend_match = [{"not": [{"path": protected_paths}]}]

                self.assertEqual(magic[0]["match"], magic_match)
                self.assertEqual(strict[0]["match"], strict_match)
                self.assertEqual(frontend[0]["match"], frontend_match)

                self.assertTrue(
                    magic[0]["deferred"],
                    "magic-link CSP must overwrite any upstream CSP after proxying",
                )
                self.assertTrue(
                    strict[0]["deferred"],
                    "strict API CSP must overwrite any upstream CSP after proxying",
                )

                self.assertEqual(
                    directive_map(magic[0]["policy"]),
                    {
                        "default-src": ("'none'",),
                        "style-src": ("'unsafe-inline'",),
                        "form-action": ("'self'",),
                        "base-uri": ("'none'",),
                        "frame-ancestors": ("'none'",),
                    },
                )
                self.assertNotIn("script-src", directive_map(magic[0]["policy"]))

                frontend_directives = directive_map(frontend[0]["policy"])
                self.assertNotIn("default-src", frontend_directives)
                self.assertNotIn("script-src", frontend_directives)
                self.assertEqual(frontend_directives["frame-ancestors"], ("'none'",))


if __name__ == "__main__":
    unittest.main()

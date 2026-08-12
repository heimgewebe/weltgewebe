from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "scripts" / "ops" / "resolve_vps_public_bind.py"
spec = importlib.util.spec_from_file_location("resolve_vps_public_bind", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ResolveVpsPublicBindTests(unittest.TestCase):
    def test_ignores_tailscale_and_private_addresses(self) -> None:
        ipv4, ipv6 = module.resolve_public_bindings([
            "172.21.0.1",
            "100.119.99.55",
            "94.16.121.119",
            "fd7a:115c:a1e0::913a:6338",
            "2a03:4000:21:c74:b47a:7bff:fee6:70d",
        ])
        self.assertEqual(ipv4, "94.16.121.119")
        self.assertEqual(ipv6, "[2a03:4000:21:c74:b47a:7bff:fee6:70d]")

    def test_requires_global_ipv4(self) -> None:
        with self.assertRaisesRegex(ValueError, "global IPv4"):
            module.resolve_public_bindings(["100.119.99.55", "2a03:4000::1"])

    def test_requires_global_ipv6(self) -> None:
        with self.assertRaisesRegex(ValueError, "global IPv6"):
            module.resolve_public_bindings(["94.16.121.119", "fd7a:115c:a1e0::1"])


if __name__ == "__main__":
    unittest.main()

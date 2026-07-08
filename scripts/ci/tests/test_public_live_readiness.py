from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Mapping


REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "ops" / "check_public_live_readiness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_public_live_readiness", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load public live readiness module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FakeWorld:
    def __init__(self, *, ip: str = "94.16.121.119", version: str = "51d8061a") -> None:
        self.module = _load_module()
        self.ip = ip
        self.version = version
        self.commit = "51d8061a6920e4bf1dd6dda9784c4fc928f43bb9"
        self.requests: list[tuple[str, Mapping[str, str] | None]] = []

    def resolver(self, host: str) -> set[str]:
        return {self.ip}

    def fetcher(
        self,
        url: str,
        headers: Mapping[str, str] | None,
        _timeout: float,
    ):
        self.requests.append((url, headers))
        FetchResult = self.module.FetchResult
        if url == "http://weltgewebe.net/":
            return FetchResult(url, 308, {"Location": "https://weltgewebe.net/"}, b"")
        if url in {"https://weltgewebe.net/", "https://www.weltgewebe.net/", "https://weltgewebe.net/map"}:
            return FetchResult(url, 200, {"Content-Type": "text/html"}, b'<!doctype html><script src="/_app/x.js"></script>')
        if url == "https://api.weltgewebe.net/health/ready":
            body = {"status": "ok", "checks": {"database": True, "nats": True, "policy": True}}
            return FetchResult(url, 200, {"Content-Type": "application/json"}, json.dumps(body).encode())
        if url == "https://weltgewebe.net/_app/version.json":
            body = {"version": self.version, "commit": self.commit, "build_id": f"{self.version}-test"}
            return FetchResult(url, 200, {"Content-Type": "application/json"}, json.dumps(body).encode())
        if url == "https://weltgewebe.net/local-basemap/style.json":
            body = {"glyphs": "/local-basemap/glyphs/{fontstack}/{range}.pbf"}
            return FetchResult(url, 200, {"Content-Type": "application/json"}, json.dumps(body).encode())
        if url == "https://weltgewebe.net/local-basemap/glyphs/Noto%20Sans%20Regular/0-255.pbf":
            return FetchResult(url, 200, {}, b"glyph-bytes")
        if url == "https://weltgewebe.net/local-basemap/basemap-hamburg-v0.1.0.pmtiles":
            return FetchResult(url, 206, {"Content-Range": "bytes 0-15/100"}, b"PMTiles\x03fake")
        return FetchResult(url, 404, {}, b"")

    def checker(self):
        return self.module.PublicLiveChecker(
            expected_version=self.version,
            expected_commit=self.commit,
            resolver=self.resolver,
            fetcher=self.fetcher,
        )


class PublicLiveReadinessTest(unittest.TestCase):
    def test_successful_public_live_receipt_checks_expected_surfaces(self) -> None:
        fake = FakeWorld()
        results = fake.checker().run()

        self.assertTrue(all(result.ok for result in results), [result.payload() for result in results])
        names = {result.name for result in results}
        self.assertEqual(
            names,
            {
                "dns:weltgewebe.net",
                "dns:www.weltgewebe.net",
                "dns:api.weltgewebe.net",
                "http-redirect",
                "https-root:weltgewebe.net",
                "https-root:www.weltgewebe.net",
                "map-route",
                "api-ready",
                "version-json",
                "basemap-style",
                "glyph-range",
                "pmtiles-header",
            },
        )
        pmtiles_requests = [headers for url, headers in fake.requests if url.endswith(".pmtiles")]
        self.assertEqual(pmtiles_requests, [{"Range": "bytes=0-15"}])

    def test_wrong_dns_ip_fails(self) -> None:
        fake = FakeWorld(ip="213.21.44.105")
        results = fake.checker().run()

        failed_dns = [result for result in results if result.name.startswith("dns:")]
        self.assertTrue(failed_dns)
        self.assertTrue(all(not result.ok for result in failed_dns))

    def test_version_mismatch_fails(self) -> None:
        fake = FakeWorld(version="old")
        checker = fake.module.PublicLiveChecker(
            expected_version="51d8061a",
            expected_commit=fake.commit,
            resolver=fake.resolver,
            fetcher=fake.fetcher,
        )

        failures = [result for result in checker.run() if result.name == "version-json"]
        self.assertEqual(len(failures), 1)
        self.assertFalse(failures[0].ok)
        self.assertIn("mismatch", failures[0].detail)

    def test_api_ready_requires_database_nats_and_policy(self) -> None:
        fake = FakeWorld()

        def bad_fetcher(url: str, headers: Mapping[str, str] | None, timeout: float):
            if url == "https://api.weltgewebe.net/health/ready":
                body = {"status": "ok", "checks": {"database": True, "nats": False, "policy": True}}
                return fake.module.FetchResult(url, 200, {}, json.dumps(body).encode())
            return fake.fetcher(url, headers, timeout)

        checker = fake.module.PublicLiveChecker(resolver=fake.resolver, fetcher=bad_fetcher)
        api_result = [result for result in checker.run() if result.name == "api-ready"][0]

        self.assertFalse(api_result.ok)
        self.assertEqual(api_result.data["missing"], ["nats"])

    def test_pmtiles_header_must_start_with_pmtiles_signature(self) -> None:
        fake = FakeWorld()

        def bad_fetcher(url: str, headers: Mapping[str, str] | None, timeout: float):
            if url.endswith(".pmtiles"):
                return fake.module.FetchResult(url, 200, {}, b"not-pmtiles")
            return fake.fetcher(url, headers, timeout)

        checker = fake.module.PublicLiveChecker(resolver=fake.resolver, fetcher=bad_fetcher)
        pmtiles_result = [result for result in checker.run() if result.name == "pmtiles-header"][0]

        self.assertFalse(pmtiles_result.ok)
        self.assertIn("missing", pmtiles_result.detail)


class PublicLiveReadinessIPv6Test(unittest.TestCase):
    def test_ipv6_aaaa_checks_are_optional(self) -> None:
        fake = FakeWorld()
        results = fake.checker().run()

        self.assertFalse(any(result.name.startswith("dns-aaaa:") for result in results))

    def test_expected_ipv6_requires_matching_authoritative_aaaa_records(self) -> None:
        fake = FakeWorld()
        original = fake.module.dig_resolve_ipv6
        try:
            fake.module.dig_resolve_ipv6 = lambda host, servers: {"2a03:4000:21:c74:b47a:7bff:fee6:70d"}
            checker = fake.module.PublicLiveChecker(
                expected_ipv6="2a03:4000:21:c74:b47a:7bff:fee6:70d",
                authoritative_servers=("ns.inwx.de",),
                resolver=fake.resolver,
                fetcher=fake.fetcher,
            )
            results = checker.run()
        finally:
            fake.module.dig_resolve_ipv6 = original

        ipv6_results = [result for result in results if result.name.startswith("dns-aaaa:")]
        self.assertEqual(len(ipv6_results), 3)
        self.assertTrue(all(result.ok for result in ipv6_results))

    def test_wrong_ipv6_aaaa_fails(self) -> None:
        fake = FakeWorld()
        original = fake.module.dig_resolve_ipv6
        try:
            fake.module.dig_resolve_ipv6 = lambda host, servers: {"2001:db8::1"}
            checker = fake.module.PublicLiveChecker(
                expected_ipv6="2a03:4000:21:c74:b47a:7bff:fee6:70d",
                authoritative_servers=("ns.inwx.de",),
                resolver=fake.resolver,
                fetcher=fake.fetcher,
            )
            results = checker.run()
        finally:
            fake.module.dig_resolve_ipv6 = original

        ipv6_results = [result for result in results if result.name.startswith("dns-aaaa:")]
        self.assertEqual(len(ipv6_results), 3)
        self.assertTrue(all(not result.ok for result in ipv6_results))

if __name__ == "__main__":
    unittest.main()

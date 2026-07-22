#!/usr/bin/env python3
"""Check the public weltgewebe VPS live-readiness surface.

The checker is intentionally read-only. It performs DNS lookups and public HTTP(S)
requests only. It does not read env files, connect to the VPS, mutate runtime
state, or print confidential values.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

DEFAULT_DOMAIN = "weltgewebe.net"
DEFAULT_WWW_DOMAIN = "www.weltgewebe.net"
DEFAULT_API_DOMAIN = "api.weltgewebe.net"
DEFAULT_EXPECTED_IP = "94.16.121.119"
DEFAULT_GLYPH_PATH = "/local-basemap/glyphs/Noto%20Sans%20Regular/0-255.pbf"
PMTILES_CONTENT_TYPE = "application/octet-stream"
DEFAULT_PMTILES_PATHS = (
    ("hamburg-stable", "/local-basemap/basemap-hamburg.pmtiles"),
    ("hamburg-versioned", "/local-basemap/basemap-hamburg-v0.1.0.pmtiles"),
    (
        "schleswig-holstein-stable",
        "/local-basemap/basemap-schleswig-holstein.pmtiles",
    ),
    (
        "schleswig-holstein-versioned",
        "/local-basemap/basemap-schleswig-holstein-v0.1.0.pmtiles",
    ),
)
API_REQUIRED_CHECKS = ("database", "nats", "policy")


@dataclass(frozen=True)
class FetchResult:
    url: str
    status: int
    headers: Mapping[str, str]
    body: bytes
    final_url: str | None = None


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    detail: str
    data: dict[str, object] = field(default_factory=dict)

    def payload(self) -> dict[str, object]:
        return {
            "name": self.name,
            "status": "pass" if self.ok else "fail",
            "detail": self.detail,
            **({"data": self.data} if self.data else {}),
        }


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        return None


class PublicLiveCheckError(RuntimeError):
    pass


Resolver = Callable[[str], set[str]]
Fetcher = Callable[[str, Mapping[str, str] | None, float], FetchResult]


def _lower_headers(headers: Mapping[str, str]) -> dict[str, str]:
    return {key.lower(): value for key, value in headers.items()}


def socket_resolve_ipv4(host: str) -> set[str]:
    answers = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
    return {item[4][0] for item in answers}


def dig_resolve_record(host: str, authoritative_servers: Sequence[str], record_type: str) -> set[str]:
    answers: set[str] = set()
    for server in authoritative_servers:
        proc = subprocess.run(
            ["dig", "+short", f"@{server}", host, record_type],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise PublicLiveCheckError(
                f"dig failed for {host} {record_type} via {server}: {(proc.stderr or proc.stdout).strip()}"
            )
        for line in proc.stdout.splitlines():
            value = line.strip()
            if value:
                answers.add(value)
    return answers


def dig_resolve_ipv4(host: str, authoritative_servers: Sequence[str]) -> set[str]:
    return {
        value
        for value in dig_resolve_record(host, authoritative_servers, "A")
        if all(part.isdigit() for part in value.split("."))
    }


def dig_resolve_ipv6(host: str, authoritative_servers: Sequence[str]) -> set[str]:
    return {value for value in dig_resolve_record(host, authoritative_servers, "AAAA") if ":" in value}


def fetch_url(
    url: str,
    headers: Mapping[str, str] | None = None,
    timeout: float = 8.0,
    max_bytes: int = 512_000,
) -> FetchResult:
    request = urllib.request.Request(url, headers=dict(headers or {}), method="GET")
    context = ssl.create_default_context()
    opener = urllib.request.build_opener(
        NoRedirectHandler,
        urllib.request.HTTPSHandler(context=context),
    )
    try:
        with opener.open(request, timeout=timeout) as response:
            body = response.read(max_bytes + 1)
            return FetchResult(
                url=url,
                status=response.getcode(),
                headers=dict(response.headers.items()),
                body=body[:max_bytes],
                final_url=response.geturl(),
            )
    except urllib.error.HTTPError as error:
        body = error.read(max_bytes + 1)
        return FetchResult(
            url=url,
            status=error.code,
            headers=dict(error.headers.items()),
            body=body[:max_bytes],
            final_url=error.url,
        )
    except urllib.error.URLError as error:
        raise PublicLiveCheckError(f"request failed for {url}: {error}") from error


def pass_result(name: str, detail: str, **data: object) -> CheckResult:
    return CheckResult(name=name, ok=True, detail=detail, data=dict(data))


def fail_result(name: str, detail: str, **data: object) -> CheckResult:
    return CheckResult(name=name, ok=False, detail=detail, data=dict(data))


@dataclass
class PublicLiveChecker:
    domain: str = DEFAULT_DOMAIN
    www_domain: str = DEFAULT_WWW_DOMAIN
    api_domain: str = DEFAULT_API_DOMAIN
    expected_ip: str = DEFAULT_EXPECTED_IP
    expected_ipv6: str | None = None
    expected_version: str | None = None
    expected_commit: str | None = None
    authoritative_servers: Sequence[str] = ()
    timeout: float = 8.0
    resolver: Resolver = socket_resolve_ipv4
    fetcher: Fetcher = fetch_url
    glyph_path: str = DEFAULT_GLYPH_PATH
    pmtiles_paths: Sequence[tuple[str, str]] = DEFAULT_PMTILES_PATHS

    def run(self) -> list[CheckResult]:
        checks = [
            *self.check_dns(),
            *self.check_dns_ipv6(),
            self.check_http_redirect(),
            self.check_https_root(self.domain),
            self.check_https_root(self.www_domain),
            self.check_map_route(),
            self.check_api_ready(),
            self.check_public_metrics_private(
                "metrics-private:app",
                f"https://{self.domain}/api/metrics",
            ),
            self.check_public_metrics_private(
                "metrics-private:api",
                f"https://{self.api_domain}/metrics",
            ),
            self.check_version_json(),
            self.check_basemap_style(),
            self.check_glyph_range(),
            *self.check_pmtiles_headers(),
        ]
        return checks

    def check_dns(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for host in (self.domain, self.www_domain, self.api_domain):
            try:
                observed = sorted(self.resolve_host(host))
            except Exception as exc:
                results.append(fail_result(f"dns:{host}", str(exc)))
                continue
            if observed == [self.expected_ip]:
                results.append(pass_result(f"dns:{host}", "A record matches expected VPS IPv4", observed=observed))
            else:
                results.append(
                    fail_result(
                        f"dns:{host}",
                        "A record does not match expected VPS IPv4",
                        observed=observed,
                        expected=[self.expected_ip],
                    )
                )
        return results

    def check_dns_ipv6(self) -> list[CheckResult]:
        if not self.expected_ipv6:
            return []
        results: list[CheckResult] = []
        for host in (self.domain, self.www_domain, self.api_domain):
            try:
                observed = sorted(dig_resolve_ipv6(host, self.authoritative_servers))
            except Exception as exc:
                results.append(fail_result(f"dns-aaaa:{host}", str(exc)))
                continue
            if observed == [self.expected_ipv6]:
                results.append(pass_result(f"dns-aaaa:{host}", "AAAA record matches expected VPS IPv6", observed=observed))
            else:
                results.append(
                    fail_result(
                        f"dns-aaaa:{host}",
                        "AAAA record does not match expected VPS IPv6",
                        observed=observed,
                        expected=[self.expected_ipv6],
                    )
                )
        return results

    def resolve_host(self, host: str) -> set[str]:
        if self.authoritative_servers:
            return dig_resolve_ipv4(host, self.authoritative_servers)
        return self.resolver(host)

    def check_http_redirect(self) -> CheckResult:
        url = f"http://{self.domain}/"
        try:
            result = self.fetcher(url, None, self.timeout)
        except Exception as exc:
            return fail_result("http-redirect", str(exc), url=url)
        location = _lower_headers(result.headers).get("location", "")
        if result.status in {301, 302, 307, 308} and location.startswith(f"https://{self.domain}"):
            return pass_result("http-redirect", "HTTP redirects to HTTPS", status=result.status, location=location)
        return fail_result("http-redirect", "HTTP did not redirect to the canonical HTTPS site", status=result.status, location=location)

    def check_https_root(self, host: str) -> CheckResult:
        url = f"https://{host}/"
        try:
            result = self.fetcher(url, None, self.timeout)
        except Exception as exc:
            return fail_result(f"https-root:{host}", str(exc), url=url)
        if result.status == 200 and b"_app/" in result.body:
            return pass_result(f"https-root:{host}", "HTTPS root serves the app shell", status=result.status)
        return fail_result(f"https-root:{host}", "HTTPS root did not serve the app shell", status=result.status)

    def check_map_route(self) -> CheckResult:
        url = f"https://{self.domain}/map"
        try:
            result = self.fetcher(url, None, self.timeout)
        except Exception as exc:
            return fail_result("map-route", str(exc), url=url)
        if result.status == 200 and b"_app/" in result.body:
            return pass_result("map-route", "Map route serves the app shell", status=result.status)
        return fail_result("map-route", "Map route did not serve the app shell", status=result.status)

    def check_api_ready(self) -> CheckResult:
        url = f"https://{self.api_domain}/health/ready"
        try:
            result = self.fetcher(url, None, self.timeout)
            payload = json.loads(result.body.decode("utf-8"))
        except Exception as exc:
            return fail_result("api-ready", str(exc), url=url)
        checks = payload.get("checks") if isinstance(payload, dict) else None
        if result.status == 200 and payload.get("status") == "ok" and isinstance(checks, dict):
            missing = [key for key in API_REQUIRED_CHECKS if checks.get(key) is not True]
            if not missing:
                return pass_result("api-ready", "API ready endpoint reports database/nats/policy true", status=result.status)
            return fail_result("api-ready", "API ready endpoint has failed checks", missing=missing, checks=checks)
        return fail_result("api-ready", "API ready endpoint did not report ok", status=result.status, payload=payload)

    def check_public_metrics_private(self, name: str, url: str) -> CheckResult:
        try:
            result = self.fetcher(url, None, self.timeout)
        except Exception as exc:
            return fail_result(name, str(exc), url=url)
        if result.status == 404:
            return pass_result(name, "Public metrics route is not exposed", status=result.status, url=url)
        return fail_result(
            name,
            "Public metrics route is exposed or does not fail closed",
            status=result.status,
            url=url,
        )

    def check_version_json(self) -> CheckResult:
        url = f"https://{self.domain}/_app/version.json"
        try:
            result = self.fetcher(url, None, self.timeout)
            payload = json.loads(result.body.decode("utf-8"))
        except Exception as exc:
            return fail_result("version-json", str(exc), url=url)
        if result.status != 200:
            return fail_result("version-json", "version.json did not return 200", status=result.status)
        version = payload.get("version")
        commit = payload.get("commit")
        if not isinstance(version, str) or not version:
            return fail_result("version-json", "version.json has no valid version", payload=payload)
        if self.expected_version and version != self.expected_version:
            return fail_result("version-json", "version mismatch", observed=version, expected=self.expected_version)
        if self.expected_commit and commit != self.expected_commit:
            return fail_result("version-json", "commit mismatch", observed=commit, expected=self.expected_commit)
        return pass_result("version-json", "version.json is current", version=version, commit=commit)

    def check_basemap_style(self) -> CheckResult:
        url = f"https://{self.domain}/local-basemap/style.json"
        try:
            result = self.fetcher(url, None, self.timeout)
            payload = json.loads(result.body.decode("utf-8"))
        except Exception as exc:
            return fail_result("basemap-style", str(exc), url=url)
        glyphs = payload.get("glyphs") if isinstance(payload, dict) else None
        cache_control = _lower_headers(result.headers).get("cache-control", "")
        cache_tokens = {token.strip().lower() for token in cache_control.split(",")}
        if result.status != 200 or not isinstance(glyphs, str) or "/local-basemap/glyphs/" not in glyphs:
            return fail_result("basemap-style", "Local basemap style missing local glyph reference", status=result.status, glyphs=glyphs)
        if not {"no-cache", "must-revalidate"}.issubset(cache_tokens):
            return fail_result(
                "basemap-style",
                "Local basemap style cache policy is not revalidating",
                cache_control=cache_control,
            )
        return pass_result(
            "basemap-style",
            "Local basemap style is reachable, local, and revalidating",
            glyphs=glyphs,
            cache_control=cache_control,
        )

    def check_glyph_range(self) -> CheckResult:
        url = f"https://{self.domain}{self.glyph_path}"
        try:
            result = self.fetcher(url, None, self.timeout)
        except Exception as exc:
            return fail_result("glyph-range", str(exc), url=url)
        if result.status == 200 and len(result.body) > 0:
            return pass_result("glyph-range", "Glyph range PBF is publicly reachable", bytes=len(result.body))
        return fail_result("glyph-range", "Glyph range PBF is not reachable", status=result.status, bytes=len(result.body))

    def check_pmtiles_headers(self) -> list[CheckResult]:
        return [self.check_pmtiles_header(region, path) for region, path in self.pmtiles_paths]

    def check_pmtiles_header(self, region: str, path: str) -> CheckResult:
        name = f"pmtiles-header:{region}"
        url = f"https://{self.domain}{path}"
        try:
            full = self.fetcher(url, None, self.timeout)
            partial = self.fetcher(
                url,
                {"Range": "bytes=0-15"},
                self.timeout,
            )
        except Exception as exc:
            return fail_result(name, str(exc), url=url)

        full_headers = _lower_headers(full.headers)
        partial_headers = _lower_headers(partial.headers)
        full_type = full_headers.get("content-type", "").split(";", 1)[0].strip().lower()
        partial_type = (
            partial_headers.get("content-type", "").split(";", 1)[0].strip().lower()
        )
        accept_ranges = full_headers.get("accept-ranges", "").lower()
        content_range = partial_headers.get("content-range", "")

        failures: list[str] = []
        if full.status != 200:
            failures.append(f"full status {full.status} != 200")
        if not full.body.startswith(b"PMTiles"):
            failures.append("full response is missing PMTiles signature")
        if full_type != PMTILES_CONTENT_TYPE:
            failures.append(
                f"full content-type {full_type or '<missing>'} != {PMTILES_CONTENT_TYPE}"
            )
        if accept_ranges != "bytes":
            failures.append(f"accept-ranges {accept_ranges or '<missing>'} != bytes")
        if partial.status != 206:
            failures.append(f"range status {partial.status} != 206")
        if not partial.body.startswith(b"PMTiles"):
            failures.append("range response is missing PMTiles signature")
        if partial_type != PMTILES_CONTENT_TYPE:
            failures.append(
                f"range content-type {partial_type or '<missing>'} != {PMTILES_CONTENT_TYPE}"
            )
        if not content_range.startswith("bytes 0-15/"):
            failures.append(
                f"content-range {content_range or '<missing>'} does not start with bytes 0-15/"
            )

        if failures:
            return fail_result(
                name,
                "; ".join(failures),
                region=region,
                full_status=full.status,
                range_status=partial.status,
                full_content_type=full_type,
                range_content_type=partial_type,
                accept_ranges=accept_ranges,
                content_range=content_range,
            )

        return pass_result(
            name,
            "Regional PMTiles full and Range representation contract is public",
            region=region,
            full_status=full.status,
            range_status=partial.status,
            content_type=full_type,
            accept_ranges=accept_ranges,
            content_range=content_range,
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check public weltgewebe live-readiness.")
    parser.add_argument("--domain", default=DEFAULT_DOMAIN)
    parser.add_argument("--www-domain", default=DEFAULT_WWW_DOMAIN)
    parser.add_argument("--api-domain", default=DEFAULT_API_DOMAIN)
    parser.add_argument("--expected-ip", default=DEFAULT_EXPECTED_IP)
    parser.add_argument("--expected-ipv6")
    parser.add_argument("--expected-version")
    parser.add_argument("--expected-commit")
    parser.add_argument("--authoritative-server", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    checker = PublicLiveChecker(
        domain=args.domain,
        www_domain=args.www_domain,
        api_domain=args.api_domain,
        expected_ip=args.expected_ip,
        expected_ipv6=args.expected_ipv6,
        expected_version=args.expected_version,
        expected_commit=args.expected_commit,
        authoritative_servers=tuple(args.authoritative_server),
        timeout=args.timeout,
    )
    results = checker.run()
    ok = all(result.ok for result in results)
    payload = {"status": "pass" if ok else "fail", "checks": [result.payload() for result in results]}
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        for result in results:
            marker = "PASS" if result.ok else "FAIL"
            print(f"{marker}: {result.name}: {result.detail}")
        print(f"overall={payload['status']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

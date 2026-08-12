#!/usr/bin/env python3
"""Resolve unambiguous public host addresses for the VPS Caddy listener."""

from __future__ import annotations

import argparse
import ipaddress
import subprocess
import sys


def _global_addresses(addresses: list[str], version: int) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
    parsed = set()
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw.strip())
        except ValueError:
            continue
        if address.version == version and address.is_global:
            parsed.add(address)
    return sorted(parsed, key=int)


def resolve_public_ipv4(addresses: list[str]) -> str:
    ipv4 = _global_addresses(addresses, 4)
    if not ipv4:
        raise ValueError("no global IPv4 address is available for public Caddy binding")
    if len(ipv4) > 1:
        raise ValueError("multiple global IPv4 addresses are available; set CADDY_BIND explicitly")
    return str(ipv4[0])


def resolve_public_ipv6(addresses: list[str]) -> str | None:
    ipv6 = _global_addresses(addresses, 6)
    if not ipv6:
        return None
    if len(ipv6) > 1:
        raise ValueError("multiple global IPv6 addresses are available; set CADDY_IPV6_BIND explicitly")
    return f"[{ipv6[0]}]"


def resolve_public_bindings(addresses: list[str]) -> tuple[str, str | None]:
    return resolve_public_ipv4(addresses), resolve_public_ipv6(addresses)


def host_addresses() -> list[str]:
    completed = subprocess.run(
        ["hostname", "-I"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    return completed.stdout.split()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--family", choices=("ipv4", "ipv6", "both"), default="both")
    parser.add_argument("addresses", nargs="*")
    args = parser.parse_args(argv)
    addresses = args.addresses or host_addresses()
    try:
        if args.family == "ipv4":
            print(resolve_public_ipv4(addresses))
        elif args.family == "ipv6":
            ipv6 = resolve_public_ipv6(addresses)
            if ipv6 is not None:
                print(ipv6)
        else:
            ipv4, ipv6 = resolve_public_bindings(addresses)
            print(ipv4)
            if ipv6 is not None:
                print(ipv6)
    except (ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

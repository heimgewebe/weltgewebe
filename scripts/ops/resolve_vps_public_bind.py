#!/usr/bin/env python3
"""Resolve public host addresses for the VPS Caddy listener."""

from __future__ import annotations

import argparse
import ipaddress
import subprocess
import sys


def resolve_public_bindings(addresses: list[str]) -> tuple[str, str]:
    parsed = []
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw.strip())
        except ValueError:
            continue
        if address.is_global:
            parsed.append(address)

    ipv4 = sorted((item for item in parsed if item.version == 4), key=int)
    ipv6 = sorted((item for item in parsed if item.version == 6), key=int)
    if not ipv4:
        raise ValueError("no global IPv4 address is available for public Caddy binding")
    if not ipv6:
        raise ValueError("no global IPv6 address is available for public Caddy binding")
    return str(ipv4[0]), f"[{ipv6[0]}]"


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
    parser.add_argument("addresses", nargs="*")
    args = parser.parse_args(argv)
    addresses = args.addresses or host_addresses()
    try:
        ipv4, ipv6 = resolve_public_bindings(addresses)
    except (ValueError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(ipv4)
    print(ipv6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

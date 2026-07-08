from __future__ import annotations

from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
VPS_OVERRIDE = REPO / "infra" / "compose" / "compose.vps.override.yml"
VPS_RUNBOOK = REPO / "docs" / "deploy" / "vps.md"


def test_vps_override_publishes_caddy_on_ipv6_host_ports() -> None:
    text = VPS_OVERRIDE.read_text(encoding="utf-8")

    assert '"${CADDY_IPV6_BIND:-[::]}:80:80"' in text
    assert '"${CADDY_IPV6_BIND:-[::]}:443:443"' in text


def test_vps_runbook_keeps_ipv6_separate_from_ipv4_public_cutover() -> None:
    text = VPS_RUNBOOK.read_text(encoding="utf-8")

    assert "AAAA-Record" in text
    assert "nur falls IPv6 geprüft und freigegeben ist" in text
    assert "--expected-ipv6" in text

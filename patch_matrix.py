with open("docs/reports/auth-status-matrix.json", "r") as f:
    content = f.read()

content = content.replace(
    '"ist": "Die heutige MVP-/Runtime-Linie nutzt /auth/me und einen In-Memory Session-Store. Das liefert einen funktional verwandten Session-Check, ist aber noch nicht deckungsgleich mit dem Zielrahmen aus GET /auth/session plus belastbarem Persistenzmodell",',
    '"ist": "Die MVP-Linie nutzt einen In-Memory Session-Store. GET /auth/session wurde implementiert (inklusive expires_at), deckt aber die Persistenzanforderungen, Session Refresh und dynamische device_id noch nicht vollständig ab",'
)

content = content.replace(
    '"sauber verifizierbarer Session-Check (GET /auth/session)",',
    '"dynamische device_id-Integration",'
)

content = content.replace(
    '"Cookie-Verhalten",',
    '"Cookie-Sicherheits-Verifikation",'
)

content = content.replace(
    '"Routen-Tests"',
    '"Routen-Tests über Unit-Tests hinaus"'
)

with open("docs/reports/auth-status-matrix.json", "w") as f:
    f.write(content)

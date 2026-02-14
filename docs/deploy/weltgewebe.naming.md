# Weltgewebe Naming Policy

## 1. Zweck

Definition des Namensraums für Weltgewebe-Dienste im Heimserver-Kontext.
Dieses Dokument beschreibt die Integration der Weltgewebe-Services (z.B. API) in die lokale Infrastruktur.

## 2. Repo-Rolle

* **Public-Deployment:** Dieses Repository verwaltet das Deployment für öffentliche Endpunkte (z.B. `weltgewebe.net`).
* **Heimserver-Integration:** Für interne Endpunkte (`*.home.arpa`) definiert dieses Repository lediglich den Contract (Referenz). Die Durchsetzung (Enforcement) und die eigentliche Konfiguration (Caddy Gateway, Pi-hole) liegen im externen Heimserver-Repository.

> **Hinweis:** Integration logic resides in the external Heimserver repository.

## 3. Abgrenzung

* **Weltgewebe:** Kartenbasiertes Common-Interface und API (dieses Repository).
* **Heimgewebe:** Separater Organismus für lokale Dienste und Gateway-Funktionen (externes Repository, separater Namensraum).

## 4. Normative Regeln

1. **Weltgewebe-Domains** (`*.weltgewebe.home.arpa`) verweisen ausschließlich auf Services dieses Repositories.
2. **Keine Überschneidung:** Heimgewebe-Domains (`*.heimgewebe.home.arpa`) werden hier nicht definiert oder verwaltet.
3. **Caddy:** Bindet strikt pro FQDN.
4. **.home.arpa** ist der kanonische TLD-Suffix (RFC 8375).

## 5. Kanonische Domains

### Weltgewebe

* `api.weltgewebe.home.arpa`
  * Interner Endpunkt für die Weltgewebe-API.
  * Upstream: `api` Service (Port 8080).

* `weltgewebe.home.arpa` (optional)
  * Landing-Page oder Redirect (derzeit nicht provisioniert).

## 6. DNS-Konfiguration (Heimserver-Repo)

Die folgende Konfiguration dient als Referenz für das externe Heimserver-Repository (z.B. in `infra/pihole/optional/99-weltgewebe.conf`):

```conf
# Optional: Enable only if Caddy is serving this domain on the gateway.
# Replace <GATEWAY_IP> with the actual IP address of the Heimserver.
address=/api.weltgewebe.home.arpa/<GATEWAY_IP>
```

## 7. Drift-Prävention

Service-Namen und Pfade müssen der Semantik folgen. Wenn `weltgewebe-api` faktisch Heimgewebe-Aufgaben übernimmt, muss
dies im Heimgewebe-Repo geregelt werden. Hier gilt: Weltgewebe-Label = Weltgewebe-Inhalt.

---
id: runbooks.weltgewebe-ddns-runtime-verification
title: Weltgewebe DynDNS Runtime-Verifikation
doc_type: runbook
status: active
summary: Kontrollierte Ende-zu-Ende-Abnahme des Heimberry-DynDNS-Dienstes.
relations:
  - type: relates_to
    target: docs/runbooks/README.md
  - type: relates_to
    target: docs/deploy/domain-mail-migration-ionos-to-inwx-mailbox-brevo.md
  - type: relates_to
    target: docs/deploy/heimserver.deployment.md
  - type: relates_to
    target: docs/runbooks/incident-response.md
---

# Weltgewebe DynDNS Runtime-Verifikation

## Vertrag

Die Implementierung gehört zu `heimgewebe/heimserver`. Erlaubt sind ausschließlich `weltgewebe.net`, `www.weltgewebe.net` und `api.weltgewebe.net`. Ein Pull Request oder Repository-Test beweist noch keinen installierten Runtime-Zustand. Die Abnahme erfolgt erst nach Review und Merge des zu installierenden Heimserver-Commits.

## Erforderliche Belege

1. Der saubere Heimserver-Checkout steht auf einem exakten Commit von `main`; dessen Hash wird im Abschlussbericht festgehalten.
2. Updater, Service und Timer stimmen bytegenau mit diesem Checkout überein. Der Standard-Installer wird vor der Aktivierung ausgeführt und anschließend mit `--check` geprüft.
3. `--activate` beendet den unmittelbaren Service-Lauf erfolgreich, bevor der Timer aktiviert wird. Erwartet werden `Result=success`, `ExecMainStatus=0` sowie ein aktiver und aktivierter Timer.
4. Jeder der drei autoritativen INWX-Nameserver liefert für jeden der drei erlaubten Hosts genau einen A-Record mit der aktuellen öffentlichen IPv4.
5. HTTPS antwortet für Apex, `www` und `api` ohne TLS-Fehler.
6. `https://weltgewebe.net/api/health/live` und `https://api.weltgewebe.net/health/live` antworten erfolgreich.
7. Heimberry besitzt keinen Listener des DynDNS-Prozesses. Auf dem Heimserver meldet `ops/checks/preflight.sh` keine direkte Exposition der App- oder Datenbankports 8080 und 5432.
8. Journald enthält keine Credential-Werte.

## Referenzbefehle

Auf Heimberry: `git pull --ff-only origin main`, Commit mit `git rev-parse HEAD` festhalten, Standard-Installer, `--check` und erst danach `--activate` ausführen. Anschließend alle neun Nameserver-/Host-Kombinationen mit `dig +time=3 +tries=1 +noall +comments +answer` prüfen. HTTPS muss für Apex, `www` und `api` antworten; zusätzlich müssen `/api/health/live` am Apex und `/health/live` am API-Host erfolgreich sein.

## Fail-closed Kriterien

`SERVFAIL`, `REFUSED`, fehlende DNS-Statuszeilen, mehrere A-Records, eine abweichende Adresse, ein fehlgeschlagener Healthcheck oder eine direkte Portexposition lassen die Abnahme scheitern. Repository-Health-Berichte und Merge-Dumps ersetzen keinen dieser Runtime-Belege.

## Nachweisformat

Der Abschlussbericht enthält Zeitstempel, Heimserver-Commit, Dateivergleiche, Service- und Timerzustand, neun autoritative DNS-Prüfungen, drei HTTPS-Prüfungen, beide Healthchecks sowie die Expositionsprüfungen auf Heimberry und Heimserver.

## Rollback

Bei einem Fehler wird `weltgewebe-ddns.timer` deaktiviert. Programm und Units werden aus dem letzten freigegebenen Heimserver-Commit wiederhergestellt. Credentials werden weder gelöscht noch in Berichte kopiert. Eine statische WAN-IP in Git ist kein zulässiger Rollback.

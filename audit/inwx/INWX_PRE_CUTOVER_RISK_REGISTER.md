# INWX Pre-Cutover Risk Register

| Risiko                                       | Klasse                    | Folge                                | Minderung                                |
| -------------------------------------------- | ------------------------- | ------------------------------------ | ---------------------------------------- |
| Alte DNS-Dateien enthalten IONOS-Mailrecords | technisch/operativ        | falsche INWX-Zone                    | Source-Priority, frische Resolver        |
| `weltweberei.org` WordPress fällt aus        | technisch/organisatorisch | Website down                         | A/AAAA/www übernehmen, HTTP-Smoke        |
| Brevo-Records fehlen                         | Auth/Login                | Magic-Link kaputt                    | frische Subdomain-Abfrage                |
| mailbox.org DKIM fehlt                       | Mail/Reputation           | Spam/Auth-Fail                       | MBO-CNAME prüfen                         |
| Null-MX falsch eingetragen                   | Mail/Abuse                | Nebendomains empfangen/failen falsch | INWX Null-MX-Support prüfen              |
| Registrartransfer vor DNS-Stabilität         | Domain/Recovery           | schwerer Rollback                    | Nameserver-Cutover getrennt von Transfer |
| IONOS zu früh gekündigt                      | Domain/Web/Mail           | Recovery-Pfad weg                    | IONOS aktiv halten                       |

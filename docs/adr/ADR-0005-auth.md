# ADR-0005: Minimales Authentifizierungskonzept

## Status

Akzeptiert

## Kontext

Die Anwendung wird künftig Funktionen enthalten, die eine Benutzerauthentifizierung und -autorisierung
erfordern. Um zu vermeiden, dass das Fehlen eines Auth-Konzepts später größere Umbauten
erzwingt, wird jetzt ein minimales Gerüst geschaffen. Dieses dient als Platzhalter und konzeptionelle
Leitplanke für die spätere, vollständige Implementierung.

## Entscheidung

Wir führen ein serverseitig validiertes Session-Management mit einem Token im Cookie als primäres
Authentifizierungsmodell ein.

### Begründung

Dieses Modell bietet eine gute Balance zwischen Sicherheit und Einfachheit für eine moderne
Webanwendung:

* **Sicherheit**: Da die Session-Informationen serverseitig gespeichert werden, ist der
  Client-seitige Token (im Cookie) nur ein Verweis. Dies reduziert die Angriffsfläche im
  Vergleich zu reinen JWT-basierten Ansätzen, bei denen sicherheitsrelevante Daten im Token
  selbst gespeichert sein können.
* **Zustandslosigkeit auf dem Client**: Der Client muss keine Tokens oder Benutzerdaten aktiv
  verwalten. Das Cookie wird vom Browser automatisch bei jeder Anfrage mitgesendet.
* **CSRF-Schutz**: Durch `HttpOnly`, `Secure` und `SameSite=Strict` Attribute für das Cookie kann
  das Risiko von Cross-Site-Request-Forgery-Angriffen (CSRF) minimiert werden.

### Rollenmodell

Für den Anfang definieren wir ein einfaches, erweiterbares Rollenmodell:

1. **Gast**: Ein nicht authentifizierter Benutzer. Hat nur Lesezugriff auf öffentliche Inhalte.
2. **Weber**: Ein authentifizierter Benutzer. Kann eigene Inhalte erstellen und verwalten
   (z.B. Gewebekonto, Anträge).
3. **Admin**: Ein Benutzer mit erweiterten Rechten. Kann administrative Aufgaben durchführen
   (z.B. Inhalte moderieren, Systemkonfigurationen ändern).

### Betroffene Anwendungsbereiche

Folgende Bereiche der Anwendung werden in Zukunft eine Authentifizierung erfordern:

* **Gewebekonto**: Verwaltung des eigenen Profils und der persönlichen Daten.
* **Antragstellung**: Einreichen und Verfolgen von Anträgen.
* **Spendenaktionen**: Erstellen und Verwalten von Spendenkampagnen.
* **Interaktive Funktionen**: Teilnahme an Diskussionen, Abstimmungen oder anderen
  Community-Features.

## Konsequenzen

* **API**: Das API benötigt eine Middleware, die das Session-Cookie validiert und den
  Benutzerkontext für die Anfrage herstellt.
* **Frontend**: Das Frontend benötigt einen Mechanismus, um den Authentifizierungsstatus zu
  erkennen und die UI entsprechend anzupassen (z.B. Login/Logout, geschützte Routen).
* **Sicherheit**: Die Implementierung muss sorgfältig erfolgen, um gängige Sicherheitsrisiken
  (wie Session-Fixation, CSRF, XSS) zu vermeiden.
* **Keine sofortige Sicherheit**: Die Code-Platzhalter aus diesem ADR (insbesondere die
  API-Middleware) sind **bewusst nicht funktional und bieten keinerlei Sicherheit**. Sie dienen
  ausschließlich als strukturelle Einhängepunkte für die spätere, echte Implementierung.

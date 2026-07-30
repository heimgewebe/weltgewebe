---
id: specs.private-nachrichten
title: Private Nachrichten zwischen Konten
summary: Kanonischer Produkt-, Datenschutz- und Ausführungsvertrag für private 1:1-Unterhaltungen im Weltgewebe.
doc_type: specification
status: canonical
canonicality: normative
lifecycle_state: active
role: norm
organ: product
owner: product
last_reviewed: 2026-07-30
review_after: 2026-10-22
depends_on:
  - specs.garnrolle-knoten-faden
relations:
  - type: relates_to
    target: docs/specs/privacy-api.md
  - type: relates_to
    target: docs/specs/objektlebenszyklen-und-loeschwirkungen.md
verifies_with:
  - apps/api/tests/db_node_conversations.rs
  - apps/api/src/routes/conversations.rs
  - apps/web/src/lib/api/directMessages.ts
  - apps/web/src/routes/nachrichten/+page.svelte
---

# Private Nachrichten zwischen Konten

## Zweck

Angemeldete Konten können sich direkt austauschen, ohne den Inhalt in einem
öffentlichen Knoten- oder Antragsgespräch zu veröffentlichen. Eine private
Unterhaltung besitzt genau zwei Teilnehmer und ist nicht Teil der Karte, der
Suche, der Föderation oder der öffentlichen Fadenprojektion.

## Sichtbarkeit und Sicherheitsgrenze

Eine private Unterhaltung trägt den Typ `direct` und die Sichtbarkeit
`participants`.

- Nur die zwei live gebundenen Teilnehmer dürfen Metadaten und Nachrichten
  lesen oder verändern.
- Nicht angemeldete Besucher, fremde Konten und Administratoren erhalten für
  eine unbekannte oder fremde Unterhaltungs-ID dieselbe Antwort `404`.
- Administratorstatus allein hebt die Teilnehmergrenze nicht auf.
- Nachrichten werden verschlüsselt übertragen und serverseitig gespeichert,
  sind aber **nicht Ende-zu-Ende verschlüsselt**. Der Server muss den Klartext
  zur Zustellung und Darstellung verarbeiten können.
- Inhalte werden nicht in öffentliche Such-, Karten-, Faden- oder
  Föderationsprojektionen übernommen.

Diese Grenze schützt vor gewöhnlichem Zugriff anderer Nutzer. Sie ersetzt
keine Ende-zu-Ende-Verschlüsselung und keinen gesonderten rechtlichen
Aufbewahrungsvertrag.

## Gesprächsmodell

Pro ungeordnetem Kontopaar existiert höchstens eine aktive private
Unterhaltung. Gleichzeitige Anfragen `A → B` und `B → A` führen daher zu
demselben Gespräch statt zu Dubletten.

Jeder Teilnehmerdatensatz enthält:

- den live gebundenen Account, solange er besteht;
- einen unveränderlichen Anzeigenamen-Snapshot;
- den eigenen Gelesen-Zeitpunkt;
- den eigenen Blockierzustand.

Nachrichten verwenden den kanonischen Nachrichtenspeicher. Damit gelten auch
für private Nachrichten:

- 1 bis 4.000 Zeichen Klartext;
- idempotentes Senden über `Idempotency-Key`;
- optimistische Versionsprüfung bei Änderung oder Entfernung;
- Anzeigename-Snapshot für nachvollziehbare Historie.

## Bedienung

Eine angemeldete Person kann an einer fremden Garnrolle **Private Nachricht**
auswählen. Das Postfach unter `/nachrichten` zeigt:

- Gegenüber und letzte Nachricht;
- Zahl ungelesener Nachrichten;
- chronologische Unterhaltung;
- Nachrichteneingabe;
- Blockieren oder Freigeben.

Das eigene Konto wird nicht als Empfänger angeboten. Beim Öffnen einer
Unterhaltung sendet der Browser die Kennung der neuesten tatsächlich geladenen
Nachricht zurück. Der Server markiert nur bis zu genau dieser Nachricht als
gelesen; eine gleichzeitig eintreffende spätere Nachricht bleibt ungelesen.

## Blockieren

Jeder Teilnehmer kann die Unterhaltung für sich blockieren. Solange mindestens
einer der beiden Teilnehmer blockiert hat, dürfen beide Seiten keine neue
Nachricht senden. Bereits vorhandene Nachrichten bleiben für beide Teilnehmer
lesbar; ihr jeweiliger Autor darf sie weiterhin ändern oder entfernen. Die
Sperre gilt ausschließlich für neue Nachrichten. Ein Teilnehmer kann nur den
eigenen Blockierzustand aufheben.

Beide Seiten erfahren beim Laden der Unterhaltung, ob gesendet werden darf. Die
Unterhaltung führt dafür eine ausdrückliche Sendeerlaubnis, die genau dann gilt,
wenn beide Konten aktiv sind und keine Seite blockiert hat. Sie nennt nicht,
welche Seite blockiert hat: Der eigene Blockierzustand ist gesondert sichtbar,
eine Blockade des Gegenübers erscheint nur als fehlende Sendeerlaubnis. Damit
bietet die Oberfläche keine Eingabe an, die der Server anschließend ablehnt.

## Missbrauchsgrenzen

Die erste produktive Fassung begrenzt serverseitig:

- neue private Unterhaltungen eines Kontos auf 20 pro Stunde;
- private Nachrichten eines Kontos auf 30 pro Minute über alle Unterhaltungen;
- zusätzlich weiterhin auf 10 Nachrichten pro Minute innerhalb derselben
  Unterhaltung.

Die Zählung und Prüfung erfolgt unter PostgreSQL-Sperren, damit parallele
Anfragen die Grenzen nicht umgehen.

## Konto-Austritt und Identität

Wird ein Teilnehmerkonto gelöscht, wird seine live Accountbindung in der
Unterhaltung entfernt. Der Anzeigename-Snapshot und die bisherige Historie
bleiben für den noch vorhandenen Teilnehmer lesbar. Neue Nachrichten setzen
zwei weiterhin aktive Accountbindungen voraus und werden nach dem Austritt
eines Teilnehmers serverseitig abgelehnt.

Ein stillgelegtes Konto gilt dabei als ausgeschieden. Es kann sich nicht mehr
anmelden und deshalb weder lesen noch senden; für den verbleibenden Teilnehmer
verhält sich die Unterhaltung wie nach einer Löschung. Darstellung und
Sendeprüfung verwenden dieselbe Grenze, damit die Oberfläche keine Zustellung
anbietet, die der Server ablehnt. Wird das Konto später wieder aktiviert, lebt
die bestehende Unterhaltung unverändert weiter.

Wird dieselbe textuelle Account-ID später erneut vergeben, erhält das neue
Konto keinen Zugriff auf die alte Unterhaltung. Das frühere Kontopaar gilt als
beendet und kann nicht stillschweigend reaktiviert werden.

Für Unterhaltungen, bei denen beide Konten ausgeschieden sind, besteht in der
ersten Fassung noch keine automatische Löschfrist. Sie sind für Nutzer nicht
mehr erreichbar; eine verbindliche Aufbewahrungs- und Löschregel wird separat
festgelegt.

## Nicht Teil der ersten Fassung

- Ende-zu-Ende-Verschlüsselung und Schlüsselwiederherstellung;
- Echtzeit-Push oder E-Mail-Benachrichtigungen;
- Gruppenunterhaltungen;
- Anhänge;
- Meldungs- und Moderationsworkflow über das Blockieren hinaus;
- Paginierung sehr großer Postfächer und vollständiger Historien.

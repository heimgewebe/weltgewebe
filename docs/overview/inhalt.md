---
id: overview.inhalt
title: Inhalt (Übersicht)
doc_type: reference
status: active
summary: Überblicksdarstellung des Weltgewebe-Inhalts und der Projektstruktur.
relations:
  - type: relates_to
    target: docs/inhalt.md
  - type: relates_to
    target: docs/vision.md
---
# Einführung: Ethik- & UX-First-Startpunkt

Die Weltgewebe-Initiative stellt Menschen und ihre Lebensrealität in den Mittelpunkt. Die technische
Plattform – SvelteKit, Axum (Rust-API), Postgres und JetStream – ist Mittel zum Zweck: Sie schafft
Transparenz, Handlungssicherheit und nachhaltige Teilhabe. Dieses Dokument bietet Außenstehenden
einen klaren Einstieg in die inhaltliche Stoßrichtung des Projekts.

## Leitplanken & Prinzipien

- **Ethik vor Feature-Liste:** Entscheidungen werden entlang von Wirkungszielen und Schutzbedarfen
  priorisiert. UX-Entscheidungen orientieren sich an Barrierefreiheit, Datenschutz und
  erklärbaren Abläufen.
- **Partizipation sichern:** Stakeholder aus Zivilgesellschaft, Verwaltung und Forschung
  erhalten früh Zugang zu Prototypen, um Risiken zu erkennen und gemeinsam zu mitigieren.
- **Transparenz herstellen:** Dokumentation, Policies und öffentlich nachvollziehbare Entscheidungen
  haben Vorrang vor reinem Feature-Output.

## Projektumfang (aktiver Aufbau)

Das Repository enthält aktive Web-, API-, Auth-, Datenbank-, Karten-, CI- und
Deploymentpfade. Die historischen Gates A–D bleiben als Entwicklungsgeschichte
nützlich, sind aber kein aktuelles „Docs-only“-Statuslabel. Produktreife wird pro
vertikalem Nutzerweg und durch aktuelle Code-, CI- und Runtimebelege bewertet.

## Domänensprache

Das Weltgewebe verwendet eine präzise Domänensprache für Klarheit in Code, APIs und Dokumentation.
Die Kernelemente sind in `docs/domain/vocabulary.md` definiert und durch
[ADR-0043](../adr/0043-edge-vs-conversation.md) formalisiert.

## Weitere Orientierung

- **Systematik & Struktur:** Siehe `docs/overview/zusammenstellung.md`.
- **Architektur-Details:** `architekturstruktur.md` fasst Domänen, Boundaries und
  Kommunikationspfade zusammen.
- **Fahrplan & Prozesse:** `docs/process/fahrplan.md` beschreibt Freigaben, Gates und
  Quality-Gates.

> _Stand:_ Aktiver Aufbau; Ethik, UX und transparente Entscheidungen bleiben Leitplanken.
> Mit dem Startpunkt hier und der Systematik im Schwesterdokument erhalten Außenstehende in
> zwei Klicks den vollständigen Projektkontext.

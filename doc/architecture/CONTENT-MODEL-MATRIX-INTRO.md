---
title: "Content-Modell-Matrix: Theoretische Einführung"
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
purpose: "Erläutert Zweck, Dimensionen und ursprüngliche Annahmen der Content-Modell-Matrix."
created: "2026-09-03T02:22:07+02:00"
updated: "2026-11-07T22:27:24+01:00"
update_reason: "Dokumentationsstruktur und Verweise nach gemeinsamen Skills überarbeitet"
status: draft
semantic_blocks:
  - content-model
  - matrix-purpose
  - matrix-dimensions
  - mirroring-principle
  - migration-patterns
  - next-step
relations:
  - target: "CONTENT-MODEL-MATRIX-FROM-DOCS.md"
    type: reference
    reason: "Historische Auswertung"
  - target: "CONTENT-MODEL-MATRIX.md"
    type: reference
    reason: "Matrix als Fortsetzung der Einführung"
---

# Die Content-Modell-Matrix: Theoretische Einführung

> Historische Einführung: Die hier angekündigte Matrix liegt inzwischen vor;
> aktuelle Speichergrenzen stehen in der [Content-Modell-Matrix](CONTENT-MODEL-MATRIX.md).

> Diese Einführung erklärt, *was* eine Content-Modell-Matrix ist, *warum*
> sie benötigt wird und *welche Dimensionen* sie abdecken sollte. Die
> folgenden Aussagen bewahren den damaligen Entwurfsstand.

## 1. Was ist ein Content-Modell? [content-model]

Ein **Content-Modell** ist die strukturelle Beschreibung dessen, was eine
Anwendung an Inhalten verwaltet: welche Entitätstypen es gibt (z. B.
"Projekt", "Dokument", "Wissensblock"), welche Felder sie haben, wie sie
zueinander in Beziehung stehen (Eltern/Kind, Referenz, Tag), und welchen
Lebenszyklus sie durchlaufen (Entwurf → Review → veröffentlicht →
archiviert).

In ki-knowledge existieren aktuell **mehrere, teils überlappende**
Content-Modelle nebeneinander, die historisch aus unterschiedlichen
Projektphasen gewachsen sind:

- Die **InfoSite-Domäne** (`InfoSiteProject`, `SourceDocument`) — ursprünglich
  für den Import und die KI-gestützte Aufbereitung von Markdown-Wissen
  gebaut, mit CRUD- und Workflow-Logik direkt in Django-Views verankert.
- Die **kanonische Datenquellen-Abstraktion** (`DataSourceDescriptor`,
  `SourceDocumentRecord`, Phase 1–2 dieser Session) — ein
  quellenunabhängiges Modell, das InfoSite, aber potenziell auch PDFs,
  Jira, Notion oder andere Systeme beschreiben kann.
- Die **Wissens-Ebene** (`KnowledgeSource`, `KnowledgeBlockRecord`) — das
  Ergebnis der semantischen Zergliederung von Dokumenten in einzelne,
  referenzierbare Wissensblöcke.
- Die **Wagtail-Seiten** (`DataSourceIndexPage`, `DataSourceDetailPage`,
  Phase 3 dieser Session) — eine neue, editoriale Sicht auf dieselben
  Daten, mit CMS-typischen Eigenschaften wie Seitenbaum, Veröffentlichungs-
  Status und Rich-Text-Feldern.

Diese Modelle beschreiben teilweise **dieselbe fachliche Realität** (ein
InfoSite-Projekt *ist* im Kern eine Datenquelle, *ist* im Kern eine Menge
Wissensblöcke), aber aus verschiedenen technischen Blickwinkeln. Genau
diese Überlappung macht eine Matrix nötig: Wir brauchen eine explizite,
einsehbare Zuordnung, damit niemand (auch kein zukünftiger Agent) annehmen
muss, welches Modell "die Wahrheit" ist.

## 2. Warum eine Matrix und keine Prosa-Beschreibung? [matrix-purpose]

Eine Tabelle erzwingt Vollständigkeit auf eine Weise, die Fließtext nicht
kann: Jede Zeile (ein Legacy-Modell/-Feld) muss eine Spalte (Wagtail-
Äquivalent) haben — und wenn es keine gibt, wird die Lücke sichtbar,
statt stillschweigend unter den Tisch zu fallen. Für eine
Strangler-Migration (schrittweiser Ersatz eines Legacy-Systems durch ein
neues, bei dem beide Zeit lang parallel laufen) ist das entscheidend:

- **Vollständigkeit prüfen**: Deckt Wagtail wirklich jedes Feld ab, das
  heute in `InfoSiteProject`/`SourceDocument` gepflegt wird? Wo nicht,
  müssen wir bewusst entscheiden (Feld ergänzen, Feld bewusst fallen
  lassen, oder Feld dauerhaft im Legacy-Modell belassen).
- **Cutover-Reihenfolge ableiten**: Modelle/Felder ohne Wagtail-Äquivalent
  können nicht cutover-fähig sein, solange die Lücke besteht — die Matrix
  zeigt direkt, welche Views/Felder noch auf Legacy angewiesen sind (siehe
  z. B. den in Schritt 5 gesetzten Rückverweis von `DataSourceDetailPage`
  zur legacy Infosite-Verwaltung für Import/KI-Refinement/Wissensblock-
  Extraktion — genau solche Lücken macht die Matrix explizit).
- **Verantwortlichkeit klären**: Manche Daten sollten *nie* nach Wagtail
  wandern (z. B. Betriebsdaten wie Job-Historien, Sync-Zeitstempel) — die
  Matrix macht auch das explizit, statt es implizit über "wird halt nicht
  erwähnt" zu regeln.

## 3. Welche Dimensionen muss die Matrix abdecken? [matrix-dimensions]

Wenn wir die eigentliche Matrix bauen, sollte sie mindestens folgende
Spalten je Legacy-Entität/-Feld enthalten:

1. **Legacy-Modell & Feld** (z. B. `InfoSiteProject.domain`)
2. **Kanonisches Äquivalent** (z. B. `DataSourceDescriptor.metadata["domain"]`)
3. **Wagtail-Äquivalent** (z. B. `DataSourceIndexPage` liest es zur Laufzeit
   aus dem Adapter, statt es als eigenes Feld zu duplizieren — "gespiegelt"
   vs. "dupliziert" ist ein wichtiger Unterschied, den die Matrix markieren
   sollte)
4. **Migrationsstatus** (z. B. `parallel` / `wagtail-primär` /
   `nur-legacy` / `geplant`)
5. **Owning System** (welches System ist im Zweifel die Quelle der
   Wahrheit für dieses Feld, solange beide parallel laufen?)
6. **Offene Fragen / Risiken** (z. B. "Wagtail-Workflow-States decken nicht
   alle bisherigen `sync_status`-Werte ab")

## 4. Architektonisches Prinzip: Spiegeln statt Duplizieren [mirroring-principle]

Ein zentrales Designprinzip, das in dieser Session bereits umgesetzt wurde
und das die Matrix explizit dokumentieren sollte: Die Wagtail-Seiten
(`DataSourceIndexPage`, `DataSourceDetailPage`) **duplizieren keine**
Projekt-/Dokumentdaten in eigenen Datenbankfeldern. Stattdessen halten sie
nur eine schlanke Referenz (`infosite_project_id`) und lesen die
eigentlichen Inhalte zur Laufzeit über `InfoSiteSourceAdapter` aus dem
Legacy-Modell. Das bedeutet:

- Es gibt **keine Synchronisationslücke** zwischen Legacy-Daten und
  Wagtail-Anzeige — beide sind immer konsistent, weil es nur eine
  Datenquelle gibt.
- Wagtail fungiert (vorerst) als **editoriale Overlay-Schicht** (Notizen,
  Freigabe-Workflow), nicht als Ersatz-Datenspeicher.
- Ein echter Cutover würde bedeuten, dass die *Wagtail-Seite* zur
  primären Datenquelle wird und der Adapter in die andere Richtung liest
  (Legacy liest von Wagtail) — das ist der Zeitpunkt, an dem "gespiegelt"
  zu "migriert" wird. Die Matrix sollte pro Feld markieren, ob dieser
  Punkt schon erreicht ist.

## 5. Wie andere Systeme das lösen (Kurzeinordnung) [migration-patterns]

CMS-Migrationen dieser Art folgen typischerweise einem von zwei Mustern:

- **Content-Type-Mapping-Tabellen** (wie in Wagtail-, Drupal- oder
  Contentful-Migrationsguides üblich): eine explizite 1:1- oder 1:n-
  Zuordnung alter zu neuer Content-Typen, oft als Teil eines
  Migrationsskripts oder einer Konfigurationsdatei, nicht nur als Doku.
- **Adapter/Facade-Schicht** (wie hier mit `InfoSiteSourceAdapter`
  bereits umgesetzt): Statt Daten zu migrieren, wird eine Übersetzungs-
  schicht eingeführt, die neue Konsumenten (Wagtail-Seiten) auf alte
  Datenquellen zugreifen lässt, bis ein echter Cutover ansteht. Das ist
  das in dieser Session gewählte Muster und deckt sich mit dem, was z. B.
  Headless-CMS-Migrationen ("strangler fig pattern", Martin Fowler) für
  Systeme empfehlen, die nicht in einem großen Schritt migriert werden
  können oder sollen.

Die kommende Matrix ist damit kein reines Dokumentationsartefakt, sondern
das Bindeglied zwischen diesen beiden Mustern: Sie beschreibt den
aktuellen Adapter-Zustand vollständig und macht sichtbar, wo eine
zukünftige echte Migration (Content-Type-Mapping im engeren Sinn)
ansetzen müsste.

## 6. Nächster Schritt [next-step]

Auf Basis dieser Einführung entstand die eigentliche
Matrix: eine Tabelle mit den oben genannten Spalten für jedes relevante
Modell (`InfoSiteProject`, `SourceDocument`, `KnowledgeSource`,
`KnowledgeBlockRecord`, `DataSourceDescriptor`, `SourceDocumentRecord`)
und ihre jeweiligen Wagtail-Gegenstücke bzw. dokumentierten Lücken.

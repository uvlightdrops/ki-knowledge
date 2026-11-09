---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-10-29 09"
updated: "2026-11-08 03"
update_reason: "Werkstattentwurf semantisch gegliedert und fachlich abgegrenzt"
status: draft
semantic_blocks:
  - workspace
  - marking-workflow
  - ai-conversation
  - review-changes
  - error-states
  - reading-accessibility
  - scope-boundary
relations:
  - target: ../architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md
    type: reference
    reason: "Architektur und technisches Zielbild der Textwerkstatt"
  - target: ../architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md
    type: reference
    reason: "Fachliche Unterscheidung von Text- und Wissensblöcken"
  - target: ../guides/text-workbench.md
    type: reference
    reason: "Bedienung der vorhandenen Textwerkstatt"
---

# Textwerkstatt: Editor-Entwurf

**Status: Markdown-Zielbild und Wireframes.**
Alle Speicherstände, Texte, Blocknummern und KI-Antworten unten sind Beispiele.
Dieses Dokument ist ein Markdown-Wireframe, keine laufende Anwendung.
Die erste echte Umsetzung E0–E4 ist separat in der
[Bedienungs- und Betriebsanleitung](../guides/text-workbench.md) beschrieben;
die konkrete Oberfläche muss nicht wortgetreu diesen Wireframes entsprechen.

**Begriffsgrenze:** „Block“ und B-Nummern in den
Wireframes bezeichnen Werkstattmarkierungen an Textstellen, nicht automatisch
eigenständige Wissensblöcke im [neuen Konzept](../architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md).
Auch das vorgeschlagene Relationsvokabular ist dafür nicht entschieden.

**Agentenbearbeitung, 2026-11-08:** Die Abschnitts-IDs wurden anhand der
Wireframes ergänzt. Die Aussagen über den Implementierungsstand wurden dabei
nicht erneut gegen Code geprüft und benötigen weiterhin menschliche Prüfung.

**Umsetzungsstand 29.10.2026:** Die Quellenauswahl der ersten Oberfläche verwendet
jetzt das allgemeine Data-Sources-Inventar statt projektgebundener InfoSite-
Eingänge. Entdeckte lokale Markdown-Dateien sind bereits vor einem Import
erfassbar. Auswahl-IDs, Ausschlussdiagnostik, direkte Quellenlinks und der
nichtdestruktive Herkunftsnachweis sind umgesetzt und isoliert geprüft;
[Implementierungsbericht](../tracking/source-access-consolidation-2026-10-29.md).
Der Quellenzugriffsschritt war keine Umsetzung der E4–E6-Funktionen und kein
abgeschlossener InfoSite-Gesamtaudit. Inzwischen ist E4 als expliziter
Einzelpassagen-Vorschlag mit Vergleich, manuell bearbeitbarem Ersatztext,
Annahme/Verwerfen und erhaltenem Herkunftsnachweis ergänzt. E5/E6 bleiben offen.

[Architektur, Datenmodell und Etappen](../architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md)

<a id="1-die-arbeitsfläche"></a>
<a id="workspace"></a>
## 1. Die Arbeitsfläche [workspace]

Die Werkstatt verbindet Material, Text und Kontext. Sie ist kein zweites
Quelleninventar: Man öffnet sie aus der bestehenden Quellen- oder Output-Ansicht.

```text
KI Knowledge / Textwerkstatt
Domain: Simulation                 Projekt: Siedlungswissen
Arbeitskopie: Ufer und Versorgung.md       Revision 12 [Gespeichert]
Original bleibt unverändert

┌─────────────────────┬─────────────────────────────────┬──────────────────────────┐
│ MATERIAL            │ DOKUMENT                        │ KONTEXT                  │
│                     │                                 │ [Block] [KI-Gespräch]     │
│ Arbeitskopien       │ [Lesen & markieren] [Markdown]  │                          │
│ • Ufer/Versorgung   │ [Änderungsvorschläge]           │ B-17 Nahrungsversorgung  │
│                     │                                 │ Typ: Aussage             │
│ Quellen, nur lesen  │ # Ufer und Versorgung           │ Tags: Nahrung, Hypothese │
│ ☑ Flusslandschaft   │                                 │ Notiz: saisonalen Ertrag │
│ ☑ Versorgungsbericht│ Eine Siedlung am Fluss ...      │ noch prüfen              │
│                     │                                 │                          │
│ Markierungen        │ [Wildbeeren ergänzen die        │ Beziehung:               │
│ B-17 Versorgung     │ Versorgung ...]              17 │ B-17 → stützt → B-42      │
│ B-18 Transport      │                                 │ Ziel: Planungsnotiz.md   │
│ B-09 Prüfen!        │ {Kurze Transportwege können     │                          │
│                     │ Engpässe verringern ...}         │ [Relation hinzufügen]    │
│                     │                                 │ [Metadaten speichern]    │
│                     │ Auswahl:                        │                          │
│                     │ [Als Block markieren]           │ Stand 4 gespeichert      │
│                     │ [KI fragen] [Überarbeiten]      │                          │
└─────────────────────┴─────────────────────────────────┴──────────────────────────┘
```

`[...]` im Text steht für eine vorhandene Markierung, `{...}` für die aktuelle
Auswahl. In der späteren Oberfläche ergänzen Farben diese Kennzeichnung; sie
ersetzen weder Blocknamen noch Statusbeschriftungen. Das Blockpanel oben zeigt
bewusst B-17, nicht automatisch die neue Auswahl.

**Etappenhinweis:** Der Wireframe zeigt das Zielbild. Im ersten Lieferumfang ist
die Mitte ein schreibgeschützter, versionierter Markdown-Snapshot mit Markierungen.
Bearbeitbare Arbeitskopien und KI-Vorschläge kommen danach. Der Einstieg darf nicht
auf eine vollständige NotebookLM- oder IDE-Nachbildung warten.

<a id="2-der-erste-vollständige-bedienablauf"></a>
<a id="marking-workflow"></a>
## 2. Der erste vollständige Bedienablauf [marking-workflow]

1. In der bestehenden Quellenliste eine Markdown-Datei öffnen und
   **In Textwerkstatt markieren** wählen. Falls noch kein Snapshot existiert,
   wird seine Anlage ausdrücklich bestätigt; bloßes Anzeigen schreibt nichts.
2. Im unveränderlichen Snapshot eine Passage auswählen. Zunächst geschieht
   das im Markdown-Quelltext, nicht in einer beliebigen HTML-Vorschau.
3. **Als Block markieren** öffnet einen Inspektor mit dem exakten Zitat.
   Titel, Typ, Tags und eine eigene Notiz können ergänzt werden.
4. **Speichern** erzeugt eine dauerhafte Markierungs-ID und bestätigt den
   serverseitigen Stand. Nach Neuladen sind Markierung und Metadaten wieder da.
5. **Relation hinzufügen** öffnet die unten beschriebene Zielsuche.
6. Die Relation speichern, ein zweites Dokument öffnen und von dort zur
   Ausgangsstelle zurückspringen.

Eine Markierung kopiert den Absatz nicht in einen zweiten bearbeitbaren Inhalt.
Das gespeicherte Zitat dient der Identifikation und historischen Nachvollziehbarkeit.

### Metadatenpanel für eine neue Auswahl

```text
Neue Markierung                                  Noch nicht gespeichert

Zitat:
„Kurze Transportwege können Engpässe verringern,
ersetzen aber keine Vorratshaltung.“

Titel          [Transport und Vorratshaltung                 ]
Typ            [Aussage                                  v  ]
Tags           [Versorgung] [Transport] [+]
Eigene Notiz   [An Ergebnissen der Simulation prüfen.        ]

Verankert an: Ufer und Versorgung / Snapshot 12
Auswahl: exakt geprüft · Markdown-Quelltext

[Abbrechen]                                      [Speichern]
```

Der Texttyp ist eine Einordnung des Nutzers, keine automatisch bewiesene
Erkenntnis. Metadaten sind nicht mit der Dokumentfreigabe in Wagtail gleichzusetzen.

### Eine Relation setzen

```text
Relation hinzufügen

Von       B-17 · Nahrungsversorgung
Beziehung [stützt v]                     Richtung: B-17 → Ziel
Ziel      [Vorrat__________________________________________]

Treffer in dieser Domain:
  B-42 · Versorgungsplanung · Planungsnotiz.md · Snapshot 3
  B-58 · Vorratsbedarf      · Trockenperiode.md · Snapshot 1

Begründung [Beide Aussagen begründen eine saisonale Reserve. ]
Zielvorschau: „Vor der Trockenperiode ...“

[Abbrechen]                                [Relation speichern]
```

Auswahl erfolgt über eine stabile ID, nicht über einen frei eingegebenen Dateipfad.
Titel, Domain, Dokument und Snapshot müssen vor der Bestätigung sichtbar sein.
Das erste Relationsvokabular bleibt klein: **bezieht sich auf**, **stützt**,
**widerspricht**, **abgeleitet aus**. Gerichtete Verbindungen zeigen ihre Richtung
auch in der Rückansicht.

<a id="3-mit-der-ki-über-text-sprechen"></a>
<a id="ai-conversation"></a>
## 3. Mit der KI über Text sprechen [ai-conversation]

Die rechte Spalte wechselt zwischen Blockinspektor und Gespräch; auf breiten
Bildschirmen können beide übereinander sichtbar sein.

```text
KI-Gespräch
Modus: [Über Text sprechen v]
Kontext:
  ☑ B-17 / Snapshot 12
  ☑ Flusslandschaft / Snapshot 4
  ☑ Versorgungsbericht / Snapshot 2
  ☐ Weitere Domain-Inhalte
Provider / Modell: aus der Anwendungskonfiguration, sichtbar vor dem Senden

Du: Was ist hier noch nicht belegt?

KI: Die saisonale Ertragshöhe bleibt offen. Der Quellenabsatz
    nennt Pflege, aber keine Messreihe.
    [Flusslandschaft · Absatz 3 · Snapshot 4]

[Nachricht_______________________________________________]
[Fragen]                       [Überarbeitung vorschlagen]
```

**Gespräch verändert niemals den Text.** Quellenverweise öffnen den tatsächlich
verwendeten Snapshot und die zitierte Stelle. Nicht verwendete oder nicht mehr
zugängliche Quellen werden nicht als Beleg dargestellt.

Später kann der Kontext ausdrücklich den noch nicht gespeicherten Puffer einer
Arbeitskopie enthalten. Dann steht dort **Ungespeicherter Entwurf**, nicht
„Revision 12“. Vor einer dauerhaft annehmbaren Überarbeitung muss dieser Stand
als Basis gesichert sein.

<a id="4-überarbeitung-prüfen-statt-überschreiben"></a>
<a id="review-changes"></a>
## 4. Überarbeitung prüfen statt überschreiben [review-changes]

```text
Vorschlag P-08                       Basis: Arbeitskopie / Revision 12
Umfang: nur der ausgewählte Absatz   Status: noch nicht übernommen

ALT: Ihr Ertrag hängt von Jahreszeit und Pflege ab.
NEU: Ihr saisonaler Beitrag zur Versorgung muss anhand
     von Ertragsdaten geprüft werden.

Begründung der KI: unbelegte Sicherheit zurücknehmen.
Betroffene Markierungen: B-17 → Prüfung erforderlich

[Verwerfen]                  [Anpassen] [Geprüft annehmen]
```

Annehmen erzeugt eine neue Revision und dokumentiert Urheber, KI-Herkunft und
Basisstand. **Anpassen** erstellt einen eigenen bearbeitbaren Vorschlagsentwurf;
die ursprüngliche KI-Ausgabe bleibt historisch erhalten.

Der allgemeine Rückgängig-Befehl arbeitet im Editorpuffer. Ein bereits bestätigter
Serverstand wird durch eine neue Wiederherstellungsrevision rückgängig gemacht,
nicht aus dem Verlauf gelöscht.

<a id="5-fehlerzustände-gehören-zum-design"></a>
<a id="error-states"></a>
## 5. Fehlerzustände gehören zum Design [error-states]

| Zustand | Anzeige | Sichere Handlung |
|---|---|---|
| Speichern läuft | „Wird gespeichert …“ | Nicht vorzeitig „Gespeichert“ anzeigen. |
| Speichern fehlgeschlagen | Fehler und letzter bestätigter Stand; Puffer bleibt erhalten | Erneut versuchen oder eigenen Text exportieren. |
| Paralleländerung | „Auf dem Server liegt Revision 13 vor; du bearbeitest 12.“ | Vergleichen; kein Last-write-wins. |
| Passage entfernt | Historisches Zitat und Snapshot bleiben erreichbar | Markierung historisch belassen oder ausdrücklich neu zuordnen. |
| Mehrere passende Stellen | „Zuordnung nicht eindeutig“ | Kandidaten zeigen, Nutzer entscheidet. |
| Relationsziel gelöscht | „Historisches Ziel gelöscht“ | Verlauf erhalten; nicht heimlich anderes Ziel einsetzen. |
| Zugriff fehlt | „Ziel nicht verfügbar“ ohne geschützten Titel oder Text | Keine fremden Metadaten in Suche, Graph oder KI-Kontext ausgeben. |
| KI nicht erreichbar | Konkreter Anfragefehler | Text und Markierungen bleiben benutzbar. |
| Vorschlag veraltet | Basisrevision stimmt nicht mehr | Neu vergleichen oder neuen Vorschlag anfordern. |

Eine Ursprungsmarkierung auf Snapshot 12 bleibt dort gültig, auch wenn Snapshot
13 keinen passenden Absatz mehr hat. „Nicht zugeordnet“ betrifft dann die
Darstellung auf dem neueren Stand, nicht den Verlust des historischen Wissens.

<a id="6-lesemodus-markdown-und-zugänglichkeit"></a>
<a id="reading-accessibility"></a>
## 6. Lesemodus, Markdown und Zugänglichkeit [reading-accessibility]

**Erste Etappe:** Auswahl direkt im Markdown. Keine unsichtbare Konvertierung
von DOM-Positionen in Quelltextpositionen. Vorschau ohne vertrauenswürdige
Source-Map bleibt lesend und verlinkt zurück zum Quelltext.

**Zielbild:** Lesen und markieren auch in einer bereinigten Vorschau. Links,
Hervorhebungen, Tabellen und mehrteilige Auswahl brauchen dafür überprüfbare
Abbildungen auf den Markdown-Quelltext. Ungeeignete Auswahl wird erklärt, nicht
scheinbar erfolgreich gespeichert.

Alle Aktionen sind ohne Maus erreichbar: Auswahl im Editor, Kontextaktion,
Metadatenformular, Zielsuche und Bestätigung. Konkrete Tastaturkürzel werden
gegen Browser- und Assist-Belegungen geprüft; keine globalen IDE-Kürzel blind
übernehmen. Fokus kehrt nach dem Schließen des Panels an die Textstelle zurück.

Auf kleinen Bildschirmen wechseln **Material / Text / Kontext** als Ansichten.
Kein Zusammendrücken dreier Spalten zu unlesbarem Text. Auswahl und ungespeicherte
Formulardaten bleiben beim Ansichtswechsel erhalten.

<a id="7-was-dieser-entwurf-bewusst-nicht-ist"></a>
<a id="scope-boundary"></a>
## 7. Was dieser Entwurf bewusst nicht ist [scope-boundary]

Kein zweites Quelleninventar, keine Wagtail-Inhaltskopie, kein neuer Graph-Store,
keine automatisch laufende KI und keine Aussage, dass Assist bereits alle diese
Funktionen fertig besitzt. Der konkrete technische Weg und seine Grenzen stehen
im [Architekturkonzept](../architecture/KNOWLEDGE-WORKBENCH-CONCEPT.md).

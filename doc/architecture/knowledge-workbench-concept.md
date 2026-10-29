# Textwerkstatt: Markdown, Wissensblöcke und KI-Gespräch

**Status: Architektur- und Zielbildentwurf. E0–E3 sind inzwischen als erste
Implementierung ergänzt; E4 und folgende bleiben Planung.**

Aktuelle Bedienung, Einführungsrechte, Grenzen und Aktualisierungsschritte:
[Betriebs- und Entwicklungsanleitung](../guides/text-workbench.md).
Die Tabellen und Schemanamen unten beschreiben teilweise das weitergehende
Zielbild, nicht wortgetreu die erste Implementierung.

Seit 29.10.2026 nutzt die erste Umsetzung für die Quellenauswahl das bestehende
Data-Sources-Inventar einschließlich noch nicht importierter Markdown-Dateien.
Ein InfoSite-Projekt ist keine Eingangsvoraussetzung. Der
[Quellenzugriffsbericht](../tracking/source-access-consolidation-2026-10-29.md)
beschreibt die implementierte Grenze, Migrationsverträglichkeit und offenen
InfoSite-/UI-Fragen; E4–E6 bleiben ausdrücklich unberührt.

Das Dokument beantwortet drei Fragen: Wo bearbeitet man Wissen mit der KI?
Wie werden markierte Textstellen zu dauerhaft nutzbaren Wissensobjekten?
Wie wächst das mit dem React-Editor von kicli-code-assist zusammen, ohne
ki-knowledge erneut mit konkurrierenden Oberflächen und Speichern zu überladen?

| Weiterführendes Dokument | Zweck |
|---|---|
| [Editor-Entwurf mit Markdown-Wireframes](../features/knowledge-workbench-design.md) | Konkrete Oberfläche und Bedienabläufe |
| [Gemeinsame Ökosystem-Architektur](../../../../dev_doc/architecture/ki-ecosystem-workbench.md) | Projektübergreifende Stack-, Paket- und Editorstrategie |
| [Bestehender Quellen-/Workspace-Prozess](source-workspace-and-workflow-concept.md) | Weiterhin führend für Aufnahme und Vorbereitung von Quellen |
| [Content-Modell-Matrix](content-model-matrix.md) | Bestehende Speicher- und Wagtail-Verantwortung |

Der externe Link setzt das bekannte Workspace-Layout voraus. Dieses
Projektkonzept und die Wireframes bleiben auch ohne `~/dev_doc` verständlich.

## 1. Empfehlung in einem Satz

**Eine Textwerkstatt mit React-Oberfläche innerhalb der bestehenden
Django-Anwendung: zuerst versionierte Markdown-Passagen markieren, mit Metadaten
versehen und verbinden; anschließend eigene Arbeitskopien und ein KI-Gespräch
mit ausdrücklich anzunehmenden Änderungsvorschlägen ergänzen.**

Django, Wagtail und die bestehenden Pipeline-Speicher bleiben. Ein gemeinsames
Frontend mit Assist ist eine mögliche Entwicklung, kein Grund für einen
sofortigen Backend-Neubau. Der erste Erfolg ist kein Chat-Demo, sondern:
**Markierung und Relation überleben Neuladen und Änderungen der Quelldatei.**

## 2. Fachliche Vision: mehr als Chat neben einer Datei

NotebookLM ist eine hilfreiche Orientierung für die Nähe von Quellen, Notizen
und Gespräch. Wir streben hier keine Funktionskopie und keine Abhängigkeit von
einem Cloudprodukt an. Das eigene Profil ist ein nachvollziehbarer Kreislauf:

```text
Material aufnehmen
    ↓
Quelle verstehen und Textstellen markieren
    ↓
Beobachtungen, Aussagen und Fragen miteinander verbinden
    ↓
Mit KI vergleichen, hinterfragen und neue Entwürfe entwickeln
    ↓
Änderungen prüfen und bewusst annehmen
    ↓
Als neuen Inhalt bereitstellen / indexieren / redaktionell freigeben
```

Die Werkstatt hat daher vier fachliche Tätigkeiten, aber nur einen Einstieg:

| Tätigkeit | Ergebnis | Was dabei nicht automatisch passiert |
|---|---|---|
| Lesen und markieren | Historisch nachvollziehbare Textstellen mit Metadaten | Kein Import, keine KI-Anfrage |
| Verbinden | Gerichtete, vom Nutzer begründete Relationen | Keine automatisch bewiesene Wahrheit |
| Schreiben | Eigener versionierter Entwurf | Kein Überschreiben des Originals |
| Mit KI arbeiten | Antwort oder prüfbarer Vorschlag | Kein stilles Übernehmen, Veröffentlichen oder Indexieren |

Ein späterer Anwendungsfall ist das Übernehmen von Simulationsergebnissen:
Beobachtung aus einer Simulation → markierte Evidenz → Hypothese →
Entwurf einer neuen Spielregel. Das ist zunächst ein Beispiel für Herkunft und
Relationen, kein Auftrag, Simulationsschnittstellen schon jetzt einzubauen.

## 3. Was heute vorhanden ist

Die folgende Bestandsaufnahme trennt verifizierte Implementierung von Zielbild.
Codeverweise beziehen sich auf den untersuchten Arbeitsstand; Zeilen können
durch weitere Umbauten wandern.

| Vorhandene Fläche | Tatsächliche Funktion | Fehlende Brücke |
|---|---|---|
| `/knowledge/chat/support/` | Quellenbezogener Domain-Chat über Retrieval | Kein gemeinsamer Editorstand, keine Vorschlagsannahme |
| InfoSite `project/<id>/refine/` unter `/output/infosite/` | Dateiauswahl und vordefinierte KI-Verfeinerung | Kein Dialog; bestehender Schreibweg überschreibt Markdown |
| Wagtail | Redaktion, Metadaten und Workflow auf bestehenden Registerzeilen | Keine versionierte Markdown-Koautorenwerkstatt |
| Assist-Editor | React, TypeScript, Vite, Monaco; Tabs und Diff-Oberfläche | Noch kein Knowledge-Annotationsmodell |

Wichtige Belege:

- Aktueller Refinement-Schreibweg:
  [`infosite_views.py`](../../ki_knowledge/django_site/infosite_views.py#L879),
  insbesondere direktes Schreiben und anschließende Registeraktualisierung.
- Aktuelle Quelle/Output-Modelle:
  [`infosite_models.py`](../../ki_knowledge/django_site/infosite_models.py#L387).
  Wagtail-Revisionsrelationen sind kein Beweis, dass externe Dateiinhalte
  vollständig und atomar versioniert werden.
- Assist:
  [`CodePreview.tsx`](../../../kicli-code-assist/web/frontend/src/components/CodePreview.tsx#L59),
  [`EditorTabs.tsx`](../../../kicli-code-assist/web/frontend/src/components/EditorTabs.tsx#L9),
  [`DiffViewer.tsx`](../../../kicli-code-assist/web/frontend/src/components/DiffViewer.tsx#L11).
  Der untersuchte Editor ist Monaco-Quelltextbearbeitung, keine fertige
  Markdown-Leseansicht mit dauerhaft gespeicherten Markierungen.

Die Assist-Arbeit ist ein wertvoller Ausgangspunkt, aber kein bereits fertiges
Speicherprodukt: Der untersuchte Client ruft Save-/Create-Endpunkte auf, für die
im untersuchten Backend keine passende Route nachgewiesen wurde. Außerdem
verwenden Eltern- und Editorzustand den Inhalt nicht durchgehend als getrennten
gespeicherten Basisstand und Entwurf. Deshalb **Tabs und Diff-Bedienung übernehmen,
nicht ungeprüft Save/Autosave als gelöst voraussetzen**.

## 4. Einordnung in die bestehende Anwendung

Die Werkstatt ist eine neue Bearbeitungsfläche, kein neues Inventar.

```text
Bestehende Quellenliste ── „In Textwerkstatt öffnen“ ─┐
                                                   ├─ Werkstatt
Bestehendes Outputregister ─ „Arbeitskopie anlegen“ ─┘
                                                      ↓
                               Markierungen / Relationen / Arbeitskopien
                                                      ↓ ausdrücklich
                            Ausgabeadapter → Datei + Register → Index/CMS
```

Die bisherige Source Workspace bleibt die Vorbereitung vor dem Import.
Die Textwerkstatt bearbeitet Erkenntnisse und Entwürfe rund um ausgewähltes
Material; sie kann auch nach dem Import verwendet werden. UI-Bezeichnungen
müssen diese beiden Bedeutungen von „Workspace“ auseinanderhalten.

Vorgeschlagener neuer Bereich: `/knowledge/workbench/`.
Das ist ein Routenvorschlag, noch kein vorhandener Endpunkt.

Aus bestehendem Chat kann später „Mit diesem Kontext in der Werkstatt öffnen“
führen. Der ältere Refinement-Dialog bleibt bis zur fachlich vollständigen
Ablösung erreichbar und weist dann auf den prüfbaren neuen Arbeitsweg hin.
Er wird nicht in diesem Konzept heimlich umgedeutet oder entfernt.

## 5. Drei Spalten, ein nachvollziehbarer Arbeitsstand

**Links: Material.** Gewählte Quellen und deren Snapshot, Arbeitskopien,
vorhandene Markierungen. Kein zweiter Discovery-/Importbrowser.

**Mitte: Text.** Zuerst schreibgeschützter Markdown-Snapshot mit Markierungen.
Später bearbeitbare Arbeitskopie, optionale Vorschau und Vorschlagsvergleich.
Dokumentidentität, Revision und Speicherzustand bleiben sichtbar.

**Rechts: Kontext.** Metadaten und Relationen der ausgewählten Markierung oder
KI-Gespräch mit expliziter Kontextliste. Auf großen Bildschirmen können beide
Panels übereinander sichtbar sein, auf kleinen werden sie umgeschaltet.

Die detaillierten Zustände, Relationensuche und Fehleranzeigen stehen im
[Markdown-Design](../features/knowledge-workbench-design.md). Besonders wichtig:
**Gespeicherter Text**, **gespeicherte Metadaten**, **aktueller Auswahlzustand**
und **noch nicht angenommener Vorschlag** sind verschiedene Zustände.

## 6. Stack: Django und React müssen sich nicht ersetzen

### Empfohlener erster Integrationsweg

Django liefert eine authentifizierte Werkstattseite, darin wird ein begrenztes
React-Bundle montiert. Session, Benutzer, Domain-Zugriff und Schreibrechte bleiben
serverseitig geprüft. Wagtail und die übrigen Django-Seiten funktionieren weiter.

Die Werkstatt muss ihre konkrete Rechteprüfung ergänzen, nicht nur den
Loginstatus übernehmen: mindestens getrennte Fähigkeiten für Lesen, Markieren,
Metadatenbearbeitung, Entwurfsschreiben und Ausgabe. Referenzdokumente übernehmen
die zugelassene Domain-/Projektzuordnung ihres Ursprungs; das Anlegen eines
Snapshots darf Leserechte nicht erweitern. Ein entzogener Quellenzugriff macht
gespeicherte Snapshots nicht automatisch allgemein zugänglich. Die genaue
Zuordnung zu vorhandenen Rollen ist vor Einführung festzulegen.

```text
Browser, dieselbe Origin
  Django-Navigation / Login / Wagtail
       └─ Werkstattseite mit React
                └─ versionierte Workbench-API
                       ├─ Django-Service-Layer
                       ├─ neue Authoring-Objekte in der Anwendungs-DB
                       ├─ vorhandene Quellen-/Outputadapter
                       └─ vorhandener LLM-Adapter
```

React ist für Auswahl, ungespeicherten Zustand, Panels, Diff und Gespräch sinnvoll.
Django bleibt für Rechte, Transaktionen, bestehende Datenmodelle und Redaktion
sinnvoll. Keines davon verlangt eine zweite Anmeldung oder einen Flask-Proxy.

### Technische Leitplanken

- Produktionsbundle mit Build-Manifest, versionierten Assets und lokalen
  Editor-Workern ausliefern; kein CDN-Zwang und kein Vite-Devserver zur Laufzeit.
  Paket-/Wheel- und Staticfiles-Auslieferung müssen das Bundle tatsächlich enthalten.
- Entwicklung mit klarer API-Weiterleitung und CSRF-Konfiguration. Der normale
  Browserzugriff bleibt möglichst same-origin; keine pauschale CORS-Freigabe.
- Schreibende Requests benötigen Django-Session und CSRF-Token. Auch jeder
  Dokument-, Revisions-, Relations- und Streamingzugriff prüft Objektrechte.
- API-Adressen relativ zum Hostadapter, kein kopiertes `localhost:8000`.
- In der ersten Etappe normale HTTP-Requests. KI-Streaming später per geeignetem
  authentifiziertem HTTP-Stream; WebSocket nur bei einem tatsächlichen Bedarf.
- Markdown-Vorschau ohne ausführbare Scripts oder ungeprüftes Raw HTML.
  URL-Schemata und eingebettete Ressourcen restriktiv behandeln; keine
  unbemerkten externen Bild-/Trackingabrufe.
- Zustände und Fehler typisieren. Eine JSON-Antwort mit Erfolgscode ersetzt
  keine erfolgreich bestätigte Transaktion.

Ein umfassender React-Shell-Wechsel bleibt möglich. Er ist eine eigenständige
Produktentscheidung nach Bewährung der Werkstatt, keine Vorbedingung.

## 7. Editorentscheidung: Quelltext zuerst, nicht zwei Engines sofort

**Empfehlung:** Für den ersten Integrationsversuch Monaco verwenden, weil Assist
damit tatsächlich arbeitet. Nicht die gesamte Assist-App einbetten, sondern
eine kleine kontrollierte Editoroberfläche. CodeMirror 6 ist die bewusste
Alternative, falls Messungen und Auswahl-/Mobile-Tests dafür sprechen.

Eine zweite Rich-Text-Engine wird anfangs nicht eingebaut. Tiptap/ProseMirror,
Lexical und Milkdown sind interessante Optionen für spätere strukturierte
Autorenschaft, aber keine kostenlose Lösung für dauerhafte Textanker.

| Option | Stärken | Wesentliche Grenze für uns |
|---|---|---|
| Monaco | Assist-Vorerfahrung, Markdown-Quelltext, Auswahl, Decorations, Diff | Keine dauerhaften Annotationen; Worker-/Bundle- und Mobile-Verhalten prüfen |
| CodeMirror 6 | Modulare Texteditor-Architektur, Range-/Change-Mapping, Markdown-Erweiterung | Integration neu; ebenfalls eigene dauerhafte Anker und Vorschau nötig |
| Tiptap / ProseMirror | Strukturierte Nodes/Marks, erweiterbare Metadaten, React-Anbindung | Markdown wird in einen Dokumentbaum und zurück übersetzt; Roundtrip testen |
| Lexical | Erweiterbare Editorzustände/Nodes, React- und Markdown-Pakete | Eigene Transformer-/Serialisierungs- und Reviewarbeit |
| Milkdown | Markdown-orientierte Oberfläche auf ProseMirror | Ebenfalls strukturelle Transformation; Plugin-/Schema-Verhalten prüfen |

Die untersuchten Kerne sind MIT-lizenziert. Das ist **keine** Aussage, dass
sämtliche Erweiterungen, Vorlagen oder Cloudangebote frei sind. Insbesondere:
`@tiptap/markdown` ist als MIT-Paket vorhanden; „Tiptap-Markdown geht nur bezahlt“
wäre falsch. Auch Kollaboration ist nicht grundsätzlich kostenpflichtig:
Open-Source-Bausteine wie Yjs/Hocuspocus und kommerzielle Produkte sind zu
unterscheiden. Preise werden nicht als dauerhafte Architekturannahme festgeschrieben.

Quelltexteditoren vermeiden eine automatische Rich-Text-Reserialisierung.
Trotzdem garantieren sie nicht von sich aus byteidentische Dateispeicherung:
Zeilenenden, Encoding und Normalisierung müssen wir kontrollieren.
Barrierefreiheit, Startzeit und Bundlegröße werden an der konkreten Integration
gemessen; hier wird kein unbelegter Sieger oder Kilobyte-Wert behauptet.

**Entscheidungstor vor Umsetzung:** Kleine Probe mit echten Markdown-Fixtures,
Auswahl-API, Offline-Assets, Fokus/Screenreader und schmalem Bildschirm.
Wenn Monaco diese Anforderungen nicht erfüllt, CodeMirror 6 wählen, ohne das
fachliche Datenmodell oder die API zu ändern. Keine dauerhafte Mehrfachengine
nur zur Absicherung einer noch nicht getroffenen Entscheidung.

Offizielle Belege und die projektübergreifende Einordnung stehen im
[gemeinsamen Konzept](../../../../dev_doc/architecture/ki-ecosystem-workbench.md).

## 8. Das entscheidende Modell: fünf Dinge nicht vermischen

| Begriff | Bedeutung | Führende Ablage im Vorschlag |
|---|---|---|
| Quelldatei | Bestehender Input, weiterhin durch Discovery/Import verwaltet | Bisheriger Dateipfad / bestehender Prozess |
| Dokumentrevision | Unveränderlicher Textstand eines Snapshots oder einer eigenen Arbeitskopie | Neue Authoring-Objekte in der Django-Anwendungs-DB |
| Markierung / Annotation | Eigene ID, Metadaten und Verweis auf eine Passage einer Revision | Neue Annotationen; kein bearbeitbarer Textduplikat |
| Eigener Textblock | Selbst verfasste Notiz oder eigener Dokumententwurf | Eigenes Authoring-Dokument mit Revisionen |
| `KnowledgeBlockRecord` | Extrahierter/indexierbarer Record | Bestehender zuständiger Store; später mögliche Projektion |

Im UI darf „Block“ die verständliche Kurzform für eine markierte Wissensstelle
sein. Im Modell werden Annotation und extrahierter Record ausdrücklich getrennt.

Warum nicht einfach die existierende Block-ID verwenden?
Der Markdown-Parser bildet Paragraphen um und berechnet IDs aus Pfad, Inhalt,
Typ und Reihenfolge:
[`markdown_blocks.py:53–91,213–220`](../../ki_knowledge/integrations/markdown_blocks.py#L53).
Eine Umbenennung oder Textänderung kann diese Identität verändern. Im
[`KnowledgeStore`](../../ki_knowledge/integrations/knowledge_store.py#L658)
können Record-Löschungen zudem Relationen und Embeddings entfernen. Das ist
für eine reproduzierbare Extraktion verständlich, aber keine stabile
Autorenidentität.

Wagtail-Snippetrevisionen sind ebenfalls kein Ersatz für dieses Modell:
Die Quelldatei liegt außerhalb ihres Textinhalts. Wir hängen neue Markdown-
Arbeitskopien deshalb nicht als angeblich identischen Inhalt in CMS-Seiten.

## 9. Vorgeschlagenes additives Datenmodell

Namen sind Arbeitsnamen, keine bereits angelegten Django-Modelle.

```text
WorkDocument
  id: UUID
  domain_ref, optional project_ref
  kind: reference | draft | note
  title, owner, created_at, state, version
  origin_ref: typisierter Verweis auf bestehende Quelle / Ausgabe, optional
  head_revision_id

TextRevision
  id: UUID
  document_id
  parent_revision_id, optional derived_from_revision_id
  text: kanonischer Markdown-Quelltext
  content_sha256
  created_by, created_at
  cause: capture | manual_edit | ai_accept | restore
  optional proposal_id

Annotation
  id: UUID
  document_id
  title, category, tags, note
  created_by, created_at, updated_at, version, state

AnnotationAnchor
  id: UUID
  annotation_id, revision_id
  representation: markdown-source-v1
  offset_unit: unicode-codepoint
  start, end, exact, prefix, suffix
  mapped_from_anchor_id: optional
  assignment: original | user_confirmed | transaction_verified

AnnotationRelation
  id: UUID
  domain_ref
  from_annotation_id, to_annotation_id
  kind, rationale, created_by, created_at, version, state
```

Im ersten Lieferumfang werden nur Referenzdokumente, unveränderliche Snapshots,
Annotationen, ihre Anker und Annotation-zu-Annotation-Relationen benötigt.
Eigene Notizen/Entwürfe können später dieselbe Dokument-/Revisionsstruktur
verwenden. Ein separater, frei editierbarer Text in jeder Annotation ist nicht
vorgesehen; eine Notiz als Metadatum darf kurz sein und hat eine andere Rolle.

**UUID identifiziert ein Objekt; SHA-256 identifiziert einen Inhalt.** Derselbe
Text in zwei Dokumenten ist nicht dasselbe Dokument. Eine neue Revision kann
denselben Inhalt wie eine ältere haben, beispielsweise bei einer Wiederherstellung.
Historie wird deshalb nicht allein über Content-Hashes adressiert.

`origin_ref` enthält den bestehenden Registerbezug und den beim Erfassen
bekannten Locator. Ein Dateipfad ist kein öffentliches Universalobjekt und
kein Anrecht auf beliebigen Dateizugriff. Bestehende Quell-IDs werden weder
umbenannt noch still migriert. Bei unklarer Zuordnung nach einem Dateiumzug
ist eine ausdrückliche Wiederzuordnung nötig.

### Was „Snapshot“ hier bedeutet

Die heutige Importpipeline macht Quellen **nicht** automatisch unveränderlich.
Wir schlagen eine zusätzliche, ausdrücklich angelegte Referenzrevision vor:
Den ausgewählten UTF-8-Markdown-Inhalt in einem konsistenten Lesevorgang erfassen,
auf die dokumentierte Textrepräsentation bringen und unveränderlich speichern.
Ein Dateiwechel während der Erfassung führt zur erneuten Prüfung bzw. Fehlermeldung,
nicht zu einem unklaren Mischstand.

Ein GET legt diesen Snapshot nicht nebenbei an. Der Nutzer bestätigt
**Snapshot zum Markieren anlegen**; ein späterer Stand wird mit
**Aktuellen Quellenstand übernehmen** als neue Revision hinzugefügt.
Alte Annotationen bleiben am alten Snapshot gültig.

### Textrepräsentation und Originaltreue

Für neue Authoring-Revisionen: Unicode-Text, Zeilenenden LF, UTF-8 für Hash und
Export, keine automatische NFC-/NFKC-Normalisierung, keine automatische Änderung
von Markdown-Whitespace. Das Eingabe-Encoding wird geprüft; nicht unterstützte
Dateien melden einen Fehler.

Der kanonische Snapshot ist ein versionierter Arbeits-/Referenztext, keine
Behauptung, alle Originalbytes zu archivieren. Der ursprüngliche Datei-Hash
kann zusätzlich als Herkunftsmetadatum gespeichert werden. Bytegenaue
Originalarchivierung wäre ein gesondertes Artefakt mit eigener Aufbewahrung.
Die vorhandene Quelldatei wird in der ersten Etappe nie zurückgeschrieben.

## 10. Dauerhafte Auswahl: mehr als Start- und Endposition

Eine Auswahl bezieht sich immer auf **eine konkrete Revision in einer konkreten
Repräsentation**. Beispiel mit zur Erklärung gekürzten IDs:

```json
{
  "document_id": "doc-example",
  "revision_id": "rev-example",
  "representation": "markdown-source-v1",
  "offset_unit": "unicode-codepoint",
  "start": 0,
  "end": 18,
  "exact": "Kurze Wege helfen.",
  "prefix": "",
  "suffix": "\n\n"
}
```

Hier ist die Beispielsatzlänge tatsächlich **18** Unicode-Codepoints; das
Intervall ist halboffen `[start, end)`. Der Server prüft:
Revision gehört zum Dokument, Inhalt ist zugänglich, Bereich ist nicht leer
und liegt im Text, `text[start:end] == exact`, Kontext und Repräsentation passen.
Ein Hash allein ersetzt die Prüfung des tatsächlich adressierten Textes nicht.

JavaScript-Editoren arbeiten häufig mit UTF-16-Positionen, Python mit Unicode-
Codepoints. Der UI-Adapter konvertiert explizit und darf keine Position mitten
in einem Surrogatpaar erzeugen. Emoji, kombinierende Zeichen, CRLF-Eingaben und
mehrzeilige Auswahl sind Pflichtfälle. Sichtbare Grapheme sind nicht automatisch
ein einzelner Codepoint.

Die erste Etappe erlaubt eine zusammenhängende Auswahl im Markdown-Quelltext,
auch über Absatzgrenzen. Mehrfachauswahl, Tabellenzellen in gerenderter Ansicht
und visuelle Auswahl über versteckte Markdown-Syntax sind zunächst nicht umfasst.
DOM-Ranges oder Zeilennummern werden nicht als dauerhafte IDs gespeichert.

### Veränderung des Textes

Ein Anker auf einer alten Revision bleibt unverändert. Für eine neue Revision
gibt es eine gesonderte Zuordnung:

| Situation | Verhalten |
|---|---|
| Alter Snapshot wird geöffnet | Originalanker gegen exakt diesen Text prüfen und anzeigen |
| Vollständig bekannte Editortransaktion verschiebt eine unberührte Auswahl | Später: neue Zuordnung berechnen, Zitat prüfen und zusammen mit der Revision sichern |
| Auswahl selbst wurde überschrieben oder neue Quelle extern übernommen | Neue Zuordnung benötigt Prüfung |
| Eindeutiges Zitat an anderer Stelle | Kandidat anzeigen; nicht ohne Bestätigung den Bedeutungsbezug wechseln |
| Mehrere Kandidaten | `ambiguous`, Auswahl erforderlich |
| Keine passende Stelle | `orphaned` für diesen neuen Stand; historischer Anker bleibt erhalten |

Unscharfe Suche darf später Vorschläge machen, niemals automatisch Relationen
an eine ähnlich klingende Aussage umhängen. Editorinterne Mapping-Funktionen
sind hilfreich, aber keine selbstständige dauerhafte Historie über Reload,
Dateiumbau und parallele Sitzungen hinweg.

Stabile eigene Abschnitts-IDs können später die Zuordnung unterstützen.
Bestehende extrahierte IDs sind dafür nicht geeignet. Wir müssen nicht zuerst
alle Parser umbauen oder unsichtbare Marker in jede Quelldatei schreiben.

## 11. Metadaten und Relationen

Erste Metadaten: Titel, kleiner Kategorie-Satz, Tags, freie Notiz, Ersteller,
Zeitstempel und Versionsnummer. Kategorien etwa **Aussage**, **Frage**,
**Beobachtung**, **Begriff**, **Idee**. Ein Ontologieeditor oder frei ausführbare
Metadatenschemata wären für den Anfang unnötig.

Erste Relationen verbinden zwei Annotationen derselben Domain, auch über
Dokumente hinweg. Vokabular: `related_to`, `supports`, `contradicts`,
`derived_from`. Labels werden lokalisiert; gespeicherte Schlüssel sind stabil.
`supports` und `contradicts` sind redaktionelle Aussagen, kein Beweisverfahren.

Die Relation hat eine eigene ID, Richtung und optionale Begründung.
Der Server prüft Typ, beide Endpunkte, Domain, aktuelle Sicht-/Schreibrechte,
gelöschte Ziele und die vorgesehene Duplikatregel. Anfangs: kein Selbstlink,
keine doppelte aktive Verbindung desselben Typs in derselben Richtung;
inverse/symmetrische Darstellung erfolgt nach expliziter Typdefinition.

Die Identität eines Endpunkts ist die Annotation, nicht ihre derzeitige Position.
Ändert sich eine aktuelle Zuordnung, ist der historische Bezug weiterhin
erreichbar. Für revisionsgenaue Beweisaussagen kann später eine Relation zusätzlich
die verwendeten Anker-/Revisions-IDs fixieren. Das ist vom „aktuellen Block“
zu unterscheiden.

Löschen erfolgt zunächst als nachvollziehbarer Tombstone. Referenzen werden
nicht lautlos kaskadiert entfernt. Ein tatsächlich unzugängliches Ziel darf
auch nicht über Titel, Suchvorschlag, Graph oder KI-Kontext offengelegt werden.
Aufbewahrungs-/Löschregeln für endgültiges Entfernen sind vor Produktivbetrieb
festzulegen; Tombstones sind keine unbegrenzte Aufbewahrungsgarantie.

## 12. Speicherhoheit und vorhandene Knowledge Stores

Die zusätzliche Ablage ist kein zweiter Schreibmaster für bestehende Quellen:

| Inhalt | Führend |
|---|---|
| Bestehender Quell-/Outputinhalt | Weiterhin bestehende Datei und Pipeline |
| Erfasster Referenzsnapshot | Neue unveränderliche Authoring-Revision |
| Eigener Entwurf / eigene Notiz | Neue Authoring-Revision; Datei später nur Export/Publikationsziel |
| Annotationen, Metadaten, Relationen | Neue Authoring-Tabellen |
| Extraktion, Suche, Embeddings | Abgeleitete Records in ihrem bestehenden Store |
| Redaktionelle Veröffentlichung | Bestehender Workflow, nicht das Speichern einer Annotation |

Die Django-Anwendungs-DB ist die Empfehlung für die neuen transaktionalen
Objekte. Eine neue isolierte SQLite-Datei für Editorzustand würde Rechte,
Backups und atomare Relationserstellung unnötig erschweren.

Der allgemeine `KnowledgeStore` und der InfoSite-Blockspeicher werden nicht
zusammengelegt. Im ersten Lieferumfang wird in **keinen** dieser Stores
geschrieben. Ein späterer expliziter Publikationsadapter projiziert freigegebene
Authoring-Revisionen und Herkunft in den jeweils zuständigen Store.

Vorhandene Contribution-Verträge sind ein möglicher Ansatz für revisionsgebundene
Exports und kollisionssichere Übernahme:
[`contributions.py`](../../ki_knowledge/knowledge/contributions.py#L26).
Sie müssen fachlich auf diesen Anwendungsfall geprüft werden, statt ein neues,
fast gleiches Austauschformat zu erfinden.

Es gibt keine atomare Transaktion über Anwendungs-DB, Datei und externen Store.
Für spätere Ausgabe daher: Publikationsauftrag in DB-Transaktion vormerken,
Datei kontrolliert schreiben/ersetzen, Register/Index nachführen, Ergebnis
bestätigen und Fehler wiederaufnehmbar speichern. Ein „teilweise exportiert“
darf nicht „veröffentlicht“ heißen. Bestehende Refinement-Schreibwege bleiben
bis zu ihrer expliziten Migration gesondert kenntlich.

## 13. API-Entwurf und Konfliktverhalten

Alle Pfade sind Vorschläge unter `/api/workbench/v1/`.
IDs sind opak; Dateipfade werden nicht vom Browser als Schreibziel vorgegeben.

| Operation | Vorgeschlagener Vertrag |
|---|---|
| Referenzsnapshot erfassen | `POST /documents/capture` mit zugelassenem Quellregisterbezug |
| Dokument und Fähigkeiten lesen | `GET /documents/{id}` mit Revision und erlaubten Aktionen |
| Historischen Text lesen | `GET /documents/{id}/revisions/{revision}` |
| Annotation anlegen | `POST /documents/{id}/annotations` mit geprüfter Revisionsauswahl |
| Metadaten ändern | `PATCH /annotations/{id}` mit `If-Match` auf Metadatenstand |
| Relation anlegen | `POST /relations` mit typisierten Endpunkten |
| Neue Entwurfsrevision speichern | Später `POST /documents/{id}/revisions` mit erwartetem Head |
| KI-Vorschlag anfordern | Später `POST /proposals` mit festem Basisstand und Kontext |
| Vorschlag annehmen | Später `POST /proposals/{id}/accept` mit erwartetem Head |

Beispiel für eine Annotation, IDs nur verkürzt zur Lesbarkeit:

```json
{
  "revision_id": "rev-example",
  "anchor": {
    "representation": "markdown-source-v1",
    "offset_unit": "unicode-codepoint",
    "start": 0,
    "end": 18,
    "exact": "Kurze Wege helfen.",
    "prefix": "",
    "suffix": "\n\n"
  },
  "metadata": {
    "title": "Transportwege",
    "category": "claim",
    "tags": ["Versorgung"],
    "note": "Noch mit Ergebnissen prüfen."
  }
}
```

Erfolgreiche Anlage liefert `201`, die tatsächliche Objekt-ID, bestätigte Version
und eine abrufbare Ressource. Transportwiederholungen für erzeugende Operationen
sollten über benutzer-/operationsgebundene Idempotenzschlüssel abgesichert
werden. Ein erneut verwendeter Schlüssel mit anderem Inhalt ergibt einen Fehler.

Metadaten und Relationen werden serverseitig validiert. Rechte, Zielzustände und
Versionsvergleich werden mit dem Schreiben konsistent transaktional geprüft.
Ein bloßes Vorab-GET gefolgt von ungeschütztem Speichern genügt nicht.

Für Metadatenänderungen gilt ein opaker, starker ETag:

```http
PATCH /api/workbench/v1/annotations/annotation-example
If-Match: "annotation-version-4"
X-CSRFToken: <Django-CSRF-Token>
Content-Type: application/json

{"note": "Saisonale Messung ergänzen."}
```

Abweichender ETag: `412 Precondition Failed`; fehlende nötige Vorbedingung:
`428 Precondition Required`. Ungültige Auswahl: `422` mit Feldfehler.
Ein gespeicherter Vorschlag mit nicht mehr passender Basis oder bereits
abgearbeiteter Zustandsänderung kann `409 Conflict` liefern.
Nicht vorhandene und nicht zugängliche Objekte werden entsprechend der
Hostpolicy behandelt, ohne fremde Inhalte zu verraten.

Eine Annotation darf ausdrücklich an einer zugänglichen historischen Revision
angelegt werden. Dafür muss nicht der aktuelle Dokument-Head identisch sein.
Das Bearbeiten eines Entwurfs oder Annehmen eines Vorschlags benötigt dagegen
den erwarteten aktuellen Head.

Für den ersten Lieferumfang kein Autosave. Explizites Speichern und korrektes
Fehlerverhalten sind wichtiger. Späteres Autosave verwendet denselben
Konfliktvertrag und einen getrennten bestätigten Basisstand.

## 14. KI-Kontext und Änderungsprotokoll

Zwei getrennte Aktionen:

**Fragen:** Antwort auf Basis ausgewählten Materials. Kein Schreibrecht auf
Dokumente durch die bloße Chat-Aktion.

**Überarbeitung vorschlagen:** Vorschlag auf einem eindeutig gesicherten
Basisstand. Noch keine neue aktive Dokumentrevision.

Der Kontext ist sichtbar und reproduzierbar:
Dokument-/Revisions-IDs, Auswahl, zugelassene Quellen, tatsächlich abgerufene
Passagen, Prompt-/Vorlagenstand, Provider/Modell und gegebenenfalls Kürzungen.
Kein stiller Wechsel von „diesem Absatz“ zu „gesamter Domain“.

Für Gespräch über einen ungespeicherten Puffer wird dessen Hash und flüchtiger
Charakter kenntlich gemacht; er muss nicht vorab extrahiert oder eingebettet
werden. Für einen dauerhaft annehmbaren Änderungsvorschlag wird der relevante
Entwurfsstand zuvor ausdrücklich als Basisrevision gesichert. Nachfolgende
Änderungen machen den Vorschlag gegebenenfalls veraltet.

Ein Vorschlag enthält mindestens:

```text
id, document_id, base_revision_id
target_range + exact original text
replacement_markdown
context_manifest, prompt_version, provider/model
created_by, created_at
state: pending | accepted | rejected | superseded
accepted_revision_id: optional
```

Anfangs genau ein zusammenhängender Zielbereich. Kein freies Anwenden beliebiger
Dateipatches, keine mehrdeutige Suche-und-Ersetze-Aktion über alle Quellen.
Der Server prüft Basisrevision, ursprünglichen Text und Rechte erneut beim
Annehmen. Doppelte Annahme erzeugt nicht zwei Revisionen.

KI-Text ist untrusted: weder Browsercode noch auszuführender Agentenauftrag.
Anweisungen in Quellen ersetzen nicht System-/Nutzerabsicht. Modellantworten
werden nicht als belegte Tatsachen gespeichert, nur weil sie Quellenmarker
enthalten. Zitate müssen zu tatsächlich verwendeten Passagen passen.

Providerzugang bleibt über `ki_knowledge.llm_provider` und die gemeinsame
ki-core-Linie. Die Werkstatt eröffnet keinen direkten, zweiten Ollama-/OpenAI-
Client. Embeddings bleiben ein getrennter Prozess; sie sind für manuelles
Markieren und direktes Gespräch über ausgewählten Text nicht erforderlich.

Aufbewahrung von Chat, Promptkontext und Modellantworten ist vor Implementierung
festzulegen. Geheimnisse gehören weder in Browserzustand noch in Exporte/Logs.
Lokale und interne Provider müssen ohne Cloud-Zwang funktionieren.

## 15. Wiederverwendung mit Assist: mechanisch gemeinsam, fachlich getrennt

Gute erste Kandidaten sind Editor-Tabs, Auswahlereignisse, Dirty-State-Anzeige
und Diff-/Annehmen-/Verwerfen-Bedienung. Die Mechanik braucht Hostcallbacks statt
fest verdrahteter Flask-Dateipfade, Projektlisten oder Knowledge-ORM-Annahmen.

Nicht als gemeinsame Komponente behandeln: Quelleninventar, Importworkflow,
Domain-Rechte, redaktionelle Freigabe und Knowledge-Retrieval. Assist hat
seinerseits Projektdateien und Agentenaufträge, nicht dasselbe Fachmodell.

Paketnamen wie `ki-document-contracts` oder `ki-workbench-ui` sind **Vorschläge**,
keine jetzt anzulegenden Repositories. Erst eine lokale vertikale Strecke
bewähren, dann dieselbe kleine Schnittstelle in beiden Hosts verwenden,
dann auslagern. Sonst entsteht eine spekulative Plattform, bevor die erste
dauerhafte Markierung funktioniert.

Python-ki-core bleibt Python-Infrastruktur. React-/TypeScript-Komponenten werden
nicht dort hineingesteckt. widgetkit/widgetkit-django bleiben nützlich für
Registry, Layout und Django-Flächen, sind aber keine vorhandene React-Bibliothek.
Die gemeinsame [Ökosystemstrategie](../../../../dev_doc/architecture/ki-ecosystem-workbench.md)
vertieft diese Grenzen.

## 16. Etappen mit klaren Ausstiegskriterien

| Etappe | Umfang | Fertig, wenn |
|---|---|---|
| E0: technische Probe | Eine React-Fläche in Django, Engineprobe, lokale Assets, Rechte/CSRF | Auswahl und abgesicherter API-Roundtrip funktionieren; kein Stackwechsel nötig |
| E1: manuelles Wissen festhalten | Snapshot, Passage, Metadaten, Relation zu zweiter Annotation | Neuladen, Domain-Grenze und geänderte Ursprungsdatei sind korrekt behandelt |
| E2: eigene Texte | Arbeitskopien/Notizen, Revisionen, explizites Speichern, Konflikte, Prüfzuordnungen | Zwei Browser überschreiben sich nicht; historische Bezüge bleiben erhalten |
| E3: KI-Gespräch | Expliziter Kontext, direktes Textgespräch, überprüfbare Quellenverweise | Ausgewählter Text ist der tatsächliche Kontext; Fehler lassen Arbeit unangetastet |
| E4: KI-Überarbeitung | Vorschlag, Diff, Annehmen/Verwerfen, Herkunft | Veraltete Basis wird abgelehnt; Annahme erzeugt genau eine Revision |
| E5: explizite Ausgabe und Extraktion | Datei-/Registeradapter, Projektion, redaktioneller Übergang | Wiederholbare Ausgabe ohne zwei Schreibmaster und ohne vorgetäuschte Gesamttransaktion |
| E6: gemeinsame UI-Bausteine | Kleiner Schnittvertrag in Assist und Knowledge | Beide Hosts nutzen ihn ohne gegenseitige Backendimporte |

E1 enthält bewusst dokumentübergreifende Relationen, nicht nur eine lokale
Markierungsdemo. Ein vollständig frei editierbarer Markdown-Text ist das Ziel,
aber nicht Voraussetzung dafür, den konkreten Wunsch nach persistenten
Textstellen schnell und verlässlich zu erfüllen.

Nicht im ersten Umfang: Echtzeit-Mehrbenutzerbearbeitung/CRDT, Graphdatenbank,
vollständiger React-Neubau, Ontologieeditor, automatische semantische Wahrheit,
beliebige PDF-/Bildbereiche, gemeinsamer Login über alle Anwendungen oder
automatisches Publizieren im Hintergrund.

## 17. Abnahmefälle, an denen die Entscheidung geprüft wird

1. Zwei Quellen derselben Domain erfassen, je eine Passage markieren, Metadaten
   speichern, Relation setzen, Anwendung neu öffnen: alles vollständig wiederfinden.
2. Ursprungsdatei ändern oder verschieben: alter Snapshot/Zitat bleibt korrekt;
   neue Zuordnung ist explizit, kein zufälliger neuer Absatz wird hervorgehoben.
3. Emoji, kombinierte Akzente, CRLF, Codeblock und mehrzeilige Passage:
   UI-Auswahl entspricht exakt der serverseitig bestätigten Auswahl.
4. Gleicher Satz zweimal im Dokument: keine stille Entscheidung für eine Stelle.
5. Zwei Browser ändern dieselben Metadaten bzw. denselben Entwurf:
   ein bestätigter Stand, ein sichtbarer Konflikt, kein Datenverlust.
6. Quelle, Annotation oder Relationsziel außerhalb der Rechte:
   weder Direkt-URL noch Suche, Graph, Export oder KI-Anfrage leakt Inhalt.
7. Datenbank-/Netzfehler beim Speichern: kein falsches „Gespeichert“;
   Entwurf bleibt sichtbar. Wiederholung erzeugt keine Duplikate.
8. Rein lesende Zugriffe erzeugen keine Snapshots, Revisionen, KI-Jobs oder Stores.
9. Vorschlag nach Änderung des Basistextes annehmen: serverseitig blockiert.
10. Ausfall des KI-Providers: Markieren, Speichern und manuelles Schreiben funktionieren.
11. Tastatur/Fokus, Screenreader und schmale Ansicht: Hauptabläufe ohne Maus
    und ohne unsichtbaren Verlust des bearbeiteten Zustands.
12. Wheel-/Staticfiles-Auslieferung enthält Editorbundle und Worker; keine
    stillen CDN-/Devserverabhängigkeiten im Zielbetrieb.

## 18. Was vor der Implementierung noch entschieden werden muss

| Frage | Empfehlung dieses Entwurfs |
|---|---|
| Sofortiger kompletter Frontendwechsel? | Nein; begrenzte React-Werkstatt in Django |
| Erster Editor? | Monaco-Probe wegen Assist; CodeMirror 6 als geprüfte Alternative |
| Markdown oder Rich-Text-JSON führend? | Markdown-Quelltext für die ersten Etappen |
| Zuerst Quellen markieren oder frei editierte Anker nachführen? | Unveränderliche neue Referenzsnapshots zuerst |
| Neue Authoring-Daten in KnowledgeStore oder Django? | Django-Anwendungs-DB; Stores später als explizite Projektion |
| Erste Beziehungstiefe? | Annotation ↔ Annotation innerhalb einer Domain, dokumentübergreifend |
| Eigene Texte überschreiben Originale? | Nein; unabhängige Arbeitskopien |
| Neue Pakete sofort? | Nein; erst nach zwei tatsächlichen Verbrauchern |
| Vorschau mit beliebigem HTML? | Nein; bereinigte, begrenzte Markdown-Vorschau |
| Chat-Aufbewahrung und endgültiges Löschen? | Eigene Produktentscheidung vor Einführung |

E0–E3 wurden anschließend als Implementierung beauftragt. Die verbleibenden
Empfehlungen sind keine pauschale Freigabe für E4–E6 oder einen vollständigen
Frontendwechsel. Migrationen und Einführungsgrenzen der ersten Umsetzung stehen
in der [Betriebsanleitung](../guides/text-workbench.md).

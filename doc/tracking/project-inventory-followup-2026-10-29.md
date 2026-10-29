# Kurzinventur: Ist ki-knowledge besser beherrschbar?

Stand: **2026-10-29**, nach den Strukturarbeiten und der E4-Ergänzung.
Vergleichsbasis ist die [Bestandsaufnahme vom 28.10.2026](project-inventory-2026-10-28.md),
insbesondere deren ursprüngliche Zahlen, nicht deren spätere Nachträge.
Dies ist eine begrenzte Strukturaufnahme, kein vollständiger Funktionstest,
keine Coverage-Messung und keine Sicherheitsprüfung.

## Kurzantwort

**Ja: Zuständigkeiten und Einstiegspfade sind deutlich klarer. Die fachliche
Gesamtkomplexität ist aber nicht verschwunden.** Es gibt weniger unklare
Doppelwege und kleinere Änderungseinheiten. Eine durchgehend bewährte
Benutzerreise von der Quelle bis zur veröffentlichten Ausgabe ist noch nicht
nachgewiesen.

| Bereich | Gegenüber der ersten Aufnahme | Verbleibende Grenze |
|---|---|---|
| Betrieb | Zentraler `stackctl`; lokale Launcher delegieren statt einen eigenen Lifecycle zu implementieren | Mehrere kompatible Befehlsnamen bleiben sichtbar |
| Paketstruktur | Kanonisches Hauptpaket, kein zweiter `src/ki_knowledge`-Baum; Paket-/Asset-Vertrag explizit | Editable-Installation allein bleibt kein Distributionsnachweis |
| Große Sammeldateien | Service- und Quellenview-Aufgaben fachlich verteilt; alte Importpfade bleiben Fassaden | Die Implementierung ist nicht verschwunden; ein Teil liegt weiterhin im Django-Paket |
| Wiederverwendung | Jira-Retrieval, Domainpfade und Importorchestrierung besitzen explizite fachliche Schnitte | Nicht sämtliche Services sind Django-unabhängig |
| Quellenzugriff | Textwerkstatt verwendet das allgemeine Quelleninventar; kein InfoSite-Projekt als Voraussetzung | Discovery, Importstatus und Autorenobjekte bleiben verschiedene Begriffe und Speicher |
| Speicherverantwortung | Dateiinhalte, Register und Wagtail-Verantwortung dokumentiert; keine stille CMS-Erzeugung beim Lesen | Keine storeübergreifende Gesamttransaktion |
| Textarbeit | Eigene Revisionen, expliziter Kontext und annehmbare KI-Vorschläge statt stiller Änderungen | Neue React-/Build-/Vorschlagslogik erhöht den absoluten Wartungsumfang |
| Dokumentation | Ein Projektbaum `doc/`, Index, getrennte Iststände, Entwürfe und Archive | Konzepte müssen weiterhin gegen die Betriebsanleitung gelesen werden |

## Was tatsächlich leichter geworden ist

### Umfang: kaum weniger Code, aber besser verteilt

Gezählt wurden die existierenden getrackten Python-Dateien im aktuellen
Arbeitsbaum sowie die neu hinzugefügten E4-Backend-/Migrations-/Testdateien und
der neue Admin-Kontexttest. Unabhängige lokale Dateien, virtuelle Umgebungen,
generierte JavaScript-Bundles und Laufzeitdaten sind nicht enthalten.
Gezählt werden physische Zeilen einschließlich Leerzeilen und Kommentare.

| Größe | Ausgangsbestand 28.10. | Arbeitsstand 29.10. |
|---|---:|---:|
| Python-Dateien | 266 | 310 |
| Python-Zeilen insgesamt | 53.059 | 56.290 |
| Python-Zeilen unter `tests/` | 10.027 | 12.868 |
| Python-Zeilen außerhalb `tests/` | 43.032 | 43.422 |
| Python-Zeilen im zweiten `src/`-Baum | 1.700 | 0 |

Trotz neuer Werkstattfunktionen liegt der Nicht-Test-Code damit nur rund
**0,9 % über dem alten Gesamtumfang**. Das ist keine Produktivitäts- oder
Qualitätskennzahl: entfernte Duplikate, neue Funktionen und umverteilte Logik
wirken gleichzeitig. Mehr Testcode bedeutet ebenfalls nicht automatisch mehr
Coverage. Der Django-Unterbaum ist von 18.517 auf 20.114 Python-Zeilen gewachsen;
eine schrumpfende Servicefassade bedeutet also nicht, dass Django insgesamt
entsprechend kleiner geworden wäre.

### Weniger Suchraum pro Änderung

Die frühere `django_site/services.py` hatte ursprünglich **2.434 Zeilen**,
vor der letzten Aufteilung noch 2.328. Die heutige Fassade hat **382 Zeilen**.
`views_data_sources.py` ging von **1.977 auf 69 Zeilen** zurück.
Zusammen sind diese beiden Einstiegsmodule gegenüber dem Ausgangsbestand
um rund **90 % kleiner**.

Das ist kein entsprechender Rückgang der fachlichen Komplexität. Die Verbesserung
liegt darin, dass etwa PDF-Jobs, Jira-Sichten, Quellenansichten und Chat nun
eigene benannte Module besitzen. Kompatible Exporte vermeiden einen gleichzeitigen
Umbau sämtlicher Aufrufer.

Beispiele für echte, nicht bloß optische Grenzen:

- [`services/jira_retrieval.py`](../../ki_knowledge/services/jira_retrieval.py)
  bündelt die fachliche Retrieval-Logik; die API-Suche verwendet diesen Service
  statt der früheren Django-Sammelimplementierung.
- [`services/document_import.py`](../../ki_knowledge/services/document_import.py)
  trennt Importorchestrierung vom Django-Repository-Adapter.
- [`services/domain_paths.py`](../../ki_knowledge/services/domain_paths.py)
  enthält die gemeinsame Pfadlogik.
- [`django_site/source_access.py`](../../ki_knowledge/django_site/source_access.py)
  adaptiert das vorhandene Quelleninventar für die Werkstatt. Dies ist ein
  gemeinsamer Zugriffsweg, kein zusätzlicher unabhängiger Quellenkatalog.

### Weniger versteckte Schreibentscheidungen

Quellsnapshot, Arbeitskopie, Textrevision, Annotation und KI-Vorschlag sind
ausdrückliche verschiedene Objekte. Lesen startet keine Publikation.
Ein Gespräch schreibt nicht in den Text. Ein Vorschlag wird erst durch
bewusste Annahme zu einer neuen Revision, mit Konfliktprüfung gegen die Basis.

Diese Regeln machen Fehler lokalisierbarer, sind aber kein Nachweis fachlicher
Richtigkeit von KI-Antworten. Die ursprüngliche Buchaussage, eine Interpretation
und eine eigene Ergänzung müssen weiterhin menschlich unterschieden werden.

## Wo die Beherrschbarkeit noch leidet

**1. InfoSite bleibt die wichtigste offene Workflow-Baustelle.**
`infosite_views.py` umfasst weiterhin rund 1.210 Zeilen. Der durchgängige Ablauf
Eingangsauswahl, Projekt, Generierung/Refinement, Ausgabe, Register und
Wagtail-Redaktion wurde noch nicht vollständig geprüft. Die Speichergrenzen
sind besser beschrieben, nicht sämtliche UI-Inkonsistenzen behoben.

**2. Der Django-Bereich ist weiterhin mehr als ein HTTP-Adapter.**
In `services/` gibt es weiterhin Django-/ORM-Bezüge, beispielsweise bei
Blockextraktion/-speicherung, Outputregistrierung, Pipeline und Sync.
Der Import-Runner verwendet bewusst einen Django-Adapter als Zusammensetzungsstelle;
das ist von fachlicher ORM-Kopplung zu unterscheiden. Es wäre falsch, den
gesamten Servicebereich bereits als vollständig entkoppelten Kern zu bezeichnen.

**3. Konfigurierbare Widgets besitzen noch empfindliche Kontextverträge.**
Der am 29.10. im Debugger bestätigte Systemstatus-Fehler ist ein konkretes Beispiel:
Ein auswählbares Sync-Widget erhielt keinen Runtime-Node. Die fehlende Übergabe
und der falsche Unterseiten-Fallback sind korrigiert und gezielt abgesichert.
Das zeigt aber auch, weshalb bloßes Aufteilen großer Dateien keine vollständige
Integrationsabsicherung ersetzt.

**4. Langläufer hängen weiterhin an HTTP-Aufrufen.**
Importstatusübernahme ist ausdrücklich synchron mit Jobprotokoll, kein neuer
Hintergrundworker. KI-Gespräch und Vorschlagserzeugung antworten ebenfalls ohne
Streaming. Idempotente Requests und gespeicherte Fehler helfen bei Unterbrechungen,
ersetzen aber keine robuste Worker-/Fortschrittsarchitektur für lange Aufgaben.

**5. Die neue Werkstatt hat einen realen eigenen Wartungspreis.**
React, TypeScript, Monaco, Asset-Build, API und Datenbankmigrationen sind zusätzliche
Flächen. Der lokale Monaco-Build bleibt groß. Neue Vorschlagslogik liegt in einem
eigenen Service und einer eigenen Oberfläche; sie wurde nicht einfach an das
bestehende große Gesprächs-/Dokumentmodul angehängt. Eine gemeinsame Bibliothek
mit Code-Assist gibt es dennoch noch nicht und wäre jetzt verfrüht.

## Nächste drei Schritte

1. **Einen Buchabschnitt real durch E4 führen.** Auftrag, Vergleich, eigene
   Korrektur, Annahme und historischen Ursprung prüfen. Bedienhindernisse vor
   weiterer Funktionsbreite beheben; Markdown-Vorschau bleibt eine kleine,
   getrennte Ergänzung.
2. **Den vereinbarten InfoSite-Ende-zu-Ende-Audit durchführen.** Eine echte
   Quelle bis zur wiederauffindbaren Ausgabe verfolgen und dabei bestätigte
   Fehler von historischen Erwartungen und neuen Wünschen trennen.
3. **Die resultierenden Status- und Kontextverträge vereinheitlichen.**
   Danach gezielt den nächsten fachlichen Schnitt wählen, statt alle großen
   Dateien nur wegen ihrer Zeilenzahl zu teilen. E5-Veröffentlichungsbrücke und
   E6-Paketauslagerung bleiben nachgeordnet.

**Fazit:** Das Projekt ist strukturell besser navigierbar und lokale Änderungen
sind weniger riskant geworden. Noch nicht erreicht ist eine durchgehend
überschaubare, konsistente Gesamtpipeline. Der nächste Hebel ist deshalb ein
abgesicherter echter Arbeitsablauf, nicht ein weiteres großes Framework.

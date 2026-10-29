# Textwerkstatt betreiben und entwickeln

Einstieg: `/knowledge/workbench/`, außerdem über **Internal Knowledge →
Textwerkstatt**, die Quellenübersicht oder ein InfoSite-Projekt.

Die Werkstatt ergänzt die vorhandenen Quellen- und Outputprozesse. Sie ersetzt
weder Discovery/Import noch Wagtail. Ein Snapshot verändert die Quelldatei nicht.

## Anmeldung und erste Quellen

Angemeldete Staff-Benutzer dürfen lokale Markdown-Quellen aus dem allgemeinen
**Data-Sources-Inventar ihrer aktiven Domain** ausdrücklich erfassen. Dazu zählen
entdeckte Dateien **vor dem Import** und im KnowledgeStore registrierte Quellen.
Ein InfoSite-Projekt oder ein `SourceDocument`-Eintrag ist nicht erforderlich.
Das ist eine konservative Einführungsregel, keine allgemeine Freigabe sämtlicher
Dateien für jeden angemeldeten Benutzer.

Die so angelegten Snapshots, Markierungen und Relationen sind **privat für ihren
Ersteller** und zusätzlich auf die aktive Domain beschränkt. Ein anderer
Staff-Benutzer erhält nicht automatisch Zugriff auf diese Arbeitsobjekte.
Eine gemeinsame Domain-Arbeitsgruppe mit feineren Rollen ist noch nicht
eingeführt.

1. Eine Markdown-Datei in einem konfigurierten Quellordner der Domain bereitstellen
   oder eine bereits vorhandene Datei unter **Data Sources → Quellen** wählen.
2. Die Textwerkstatt in derselben Domain öffnen.
3. Eine Quelle wählen und **Snapshot ausdrücklich erfassen** bestätigen.
4. Text auswählen, **Als Block markieren**, Metadaten eingeben und speichern.
5. Eine zweite Stelle, auch in einem anderen Dokument, markieren.
6. Im Blockinspektor eine gerichtete Relation zum Zielblock speichern.

Die Auswahl verwendet dasselbe Discovery-Inventar und dieselben Domain-Quellordner
wie Data Sources, auch Markdown-Dateien in gemischten Ordnern. Konfigurierte
verlinkte Wurzeln und die von Data Sources erkannten verlinkten Unterverzeichnisse
bleiben nutzbar. Beliebige Browser-Dateipfade, Traversal und Datei-Links auf Ziele
außerhalb dieser vertrauenswürdigen Wurzeln sind nicht erlaubt. Wer diese
serverseitigen Ordner/Verzeichnislinks verwalten darf, bestimmt damit auch deren
Vertrauensgrenze.

Die Dropdown-Beschriftung zeigt Titel, Ordner/Pfad und Importstatus.
**Nicht erfassbare Quellen** nennt Ausschlussgründe, etwa fehlende Dateien,
andere Formate oder entfernte Quellen ohne kontrollierte lokale Markdown-Datei.
Die maximale Snapshotgröße beträgt 2 MiB; UTF-8- und Leseprobleme werden bei der
ausdrücklichen Erfassung sichtbar angezeigt.

Staff-Benutzer können eine Quelle aus Quellenliste und Quellendetail direkt
mit **Textwerkstatt öffnen** vorwählen. Der Link erfasst noch keinen Snapshot.
Die Domain muss im allgemeinen Domainregister existieren; ein Projekt wird
dadurch nicht angelegt. Discovery, Öffnen und Capture starten keinen Import,
keine Generierung und keinen Embeddinglauf.

Die API liefert serverseitig erzeugte opake Auswahl-IDs statt beliebiger
Dateipfade. `POST …/api/documents` übernimmt diese Zeichenfolge unverändert als
`source_id`. Alte ganzzahlige InfoSite-IDs bleiben ausschließlich als
Kompatibilitätseingang erhalten, nicht als neues Dropdown-Inventar.

Markierungen referenzieren einen unveränderlichen Snapshot. Externes Ändern
der Originaldatei verschiebt keine bestehende Markierung. Erneutes Erfassen
eines anderen Inhalts erzeugt einen anderen Snapshot; der ältere bleibt
erreichbar. Die Oberfläche speichert nicht automatisch im Hintergrund.

## Eigene Texte und Revisionsverlauf (E2)

**Eigene Arbeitskopie anlegen** erzeugt aus einem Quellsnapshot einen getrennten,
bearbeitbaren Text. **Leere Notiz anlegen** startet ohne Quelldatei. Beide liegen
in der Anwendungsdatenbank; die ursprüngliche Quelle bleibt unverändert.

Änderungen werden mit **Textrevision speichern** ausdrücklich gesichert.
**Revision anzeigen** öffnet ältere Textstände nur lesend. Bei parallelen
Änderungen wird ein veralteter Schreibversuch abgewiesen. Die eigene Fassung
bleibt im Editor, der Serverstand wird daneben zum Vergleich lesbar angezeigt,
und die eigene Fassung kann als Markdown heruntergeladen werden.

Markierungen werden nicht still an ähnliche Formulierungen umgehängt:
Nach einer Textrevision erscheinen bisherige Markierungen als **Historische
Markierungen**, sofern sie auf dem neuen Stand nicht ausdrücklich zugeordnet
sind. Die ursprüngliche Stelle bleibt erreichbar. Einen neuen Bereich auswählen
und **Dieser Auswahl zuordnen** bestätigt eine neue Zuordnung derselben
Markierungsidentität; der historische Anker bleibt bestehen. Das gilt auch
für unverändert gebliebene Passagen: Die erste Umsetzung bevorzugt eine
explizite Prüfung gegenüber automatischer Neuverankerung.

Eine bereits gespeicherte Revision wird nicht aus der Historie gelöscht.
Für eine Wiederherstellung kann ihr Text in eine neue aktuelle Revision
übernommen werden; ein eigener automatischer Restore-Workflow ist noch nicht
Bestandteil dieser ersten Oberfläche.

## Über Text sprechen (E3)

Im Kontextpanel stehen Provider und Modell vor dem Senden. Die Werkstatt
verwendet die bestehende Konfiguration über `ki_knowledge.llm_provider`.
Fehlende Modell-/Providerkonfiguration wird als Fehler angezeigt; die manuelle
Textarbeit bleibt unabhängig davon möglich.

Ein neues Gespräch bezieht sich ausdrücklich auf das angezeigte Dokument und
seine Revision oder die ausgewählte gespeicherte Markierung. Zusätzliche eigene
Dokumentrevisionen müssen einzeln ausgewählt werden. Es gibt keinen stillen
Zugriff auf weitere Domain-Inhalte und keinen automatischen Retrieval-/Embeddinglauf.

Ein Dokumentgespräch kann den **ungespeicherten Puffer** übertragen; die Anzeige
weist darauf hin. Das Senden speichert diesen Kontext beim Gespräch, aber
erzeugt keine Textrevision. Die nachträgliche Überprüfbarkeit des Gesprächs
benötigt diese Speicherung: Ungespeichert als Dokument bedeutet nicht „nirgendwo
persistiert“. Vor dem Senden daher sensible Inhalte aus dem Kontext entfernen.
Bei einem Gespräch über eine gespeicherte Markierung muss für einen geänderten
Puffer ausdrücklich ein neues Dokumentgespräch begonnen werden.

Gespräche und Antworten bleiben mit ihrem tatsächlichen Kontext erhalten.
Unter **Tatsächlich übermittelter Kontext** sind die übergebenen Textstände
nachlesbar. Das sind Herkunftsnachweise der Anfrage, keine automatisch
verifizierten Antwortzitate. Eine KI-Antwort ist keine belegte Erkenntnis.

Providerfehler werden beim betreffenden Gespräch sichtbar dokumentiert.
Nach einer unklaren Netzwerkantwort lässt sich dieselbe Anfrage unter derselben
ID erneut prüfen, ohne sie still doppelt auszuführen. Eine bewusst neue Anfrage
ist gesondert möglich.

**Nicht enthalten:** automatisches Überarbeiten, Diff-Annahme oder Schreibrechte
für die KI. Das wäre E4. Die erste Oberfläche arbeitet mit vollständigen
HTTP-Antworten, noch nicht mit Token-Streaming.

## Installation und Aktualisierung

Die neuen Tabellen werden über normale Django-Migrationen angelegt. Vor dem
Aktualisieren die Anwendungsdatenbank nach dem üblichen Betriebsverfahren sichern.
Im Projektverzeichnis mit dem Projektinterpreter:

```bash
.venv/bin/python manage.py migrate
```

Diese Dokumentation führt den Befehl nicht automatisch gegen eine laufende
Anwendungsdatenbank aus.

Die additive Migration `0022_workbench_generic_origin` ergänzt generische
Herkunftsmetadaten und eine eindeutige Capture-Identität. Bestehende
SourceDocument-FKs, Dokument-/Revisions-IDs und Markierungen bleiben erhalten.
Gleiche kanonische Datei und gleicher normalisierter Inhalt werden pro
Eigentümer/Domain wiederverwendet, auch wenn eine entdeckte Datei später im
KnowledgeStore registriert wird. Die ursprüngliche Herkunft des Snapshots wird
dabei nicht nachträglich umgeschrieben.

Die gebauten React-/Monaco-Assets sind Bestandteil des Python-Pakets und des
Repositories. Ein Zielhost braucht zum normalen Start **kein Node.js, npm,
Vite oder CDN**. Wenn der Zielbetrieb `collectstatic` verwendet, die normalen
Staticfiles-Aktualisierungsschritte mit ausführen. Anwendung über den bestehenden
stackctl-Lebenszyklus neu starten, nicht zusätzlich einen zweiten Editorserver
starten.

## Frontend ändern

Node.js 20.19+ und npm werden nur zum Entwickeln/Bauen benötigt:

```bash
cd frontend/workbench
npm ci
npm run build
npm test
npm run test:browser
```

`npm run build` prüft TypeScript und erstellt den lokalen Vite-Build unter
`ki_knowledge/django_site/static/django_site/workbench/`, einschließlich
Editorworker, Markdown-Sprachchunk, Manifest und Lizenzhinweisen.
Quelländerungen und den dazugehörigen Build gemeinsam weitergeben. Das Manifest
enthält gehashte Assetnamen; Django bindet genau diese Dateien ein.

Der Monaco-Entry ist derzeit ein bewusst noch relativ großes Bundle. Das
Buildwerkzeug weist darauf hin. Das ist keine versteckte CDN-Abhängigkeit;
weitere Aufteilung oder ein CodeMirror-Vergleich bleiben eigenständige
Optimierungen nach Messung.

## Isolierte Prüfung

```bash
.venv/bin/python -m pytest -q --basetemp=.pytest-workbench tests/test_workbench_backend.py tests/test_sources_browser.py tests/test_workbench_assets.py tests/test_django_module_boundaries.py
```

Die Backendintegration migriert ausschließlich isolierte Testdatenbanken.
Die Browserprüfung startet einen eigenen Django-Testserver mit isolierter
Datenbank, Quellen und Testbenutzer in einem kurzlebigen Verzeichnis im Projekt.
Sie benötigt keine InfoSite-Projekte. Sie verwendet weder vorhandene
Benutzerkonten noch die Anwendungsdatenbank. Browserbinärdateien müssen für
Playwright verfügbar sein; bei einer entsprechenden Fehlermeldung im
Frontendverzeichnis einmal `npx playwright install chromium` ausführen.

Die Browsertests prüfen tatsächliche Serverpersistenz, nicht nur gemockte
Fetch-Antworten. Die Backendtests decken zusätzlich CSRF, Eigentümer-/Domain-
Grenzen, Unicode-Koordinaten, Pfadgrenzen und konkurrierende Metadatenstände ab.

## Konzepte und Grenzen

- [Architekturentwurf](../architecture/knowledge-workbench-concept.md).
- [Editor-Wireframes](../features/knowledge-workbench-design.md).
- [Quellenzugriff: Umsetzung und geprüfter Befund vom 29.10.2026](../tracking/source-access-consolidation-2026-10-29.md).
- Die Authoring-Objekte liegen in der Django-Anwendungsdatenbank, nicht in
  einem zusätzlichen Editor-SQLite-Store.
- Bestehende KnowledgeStore-Records und InfoSite-Blockstores werden durch das
  manuelle Markieren nicht beschrieben oder zusammengelegt.
- Eine gespeicherte Markierung ist keine redaktionelle Freigabe und kein
  automatisch bewiesener Zusammenhang.
- Gespräche und ihr Kontext sind Eigentümer-/Domain-gebunden in der
  Anwendungsdatenbank gespeichert. Eine automatische Aufbewahrungsfrist,
  gemeinsames Team-Sharing und ein Endnutzer-Löschworkflow sind noch nicht
  eingeführt; vor Einsatz mit aufbewahrungspflichtigen oder besonders sensiblen
  Daten ist diese Betriebsregelung zu ergänzen.

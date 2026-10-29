# Quellenzugriff: Data Sources und Textwerkstatt

**Stand: 29.10.2026. Priorität 1 implementiert und isoliert geprüft.**

Dieser Bericht betrifft den allgemeinen Dokumentzugriff der Textwerkstatt.
Er ist **kein abgeschlossener InfoSite-Gesamtaudit**. E4–E6 wurden nicht
implementiert. Der bereits umfangreich veränderte Arbeitsbaum wurde nicht
zurückgesetzt, bereinigt, committed oder mit einem weiteren Refactoring überzogen.

## 1. Verifizierter Fehler und tatsächlicher Bestand

Vor der Änderung las `workbench_service.capture_candidates()` ausschließlich
`SourceDocument.objects.filter(project__domain=...)`. Diese Tabelle enthält
projektgebundene InfoSite-Eingänge, nicht das allgemeine Quelleninventar.
Zusätzlich wurden ungültige, fehlende oder verlinkte Eingänge still übersprungen.
Eine normale Markdown-Datei ohne InfoSite-Projekt konnte daher fehlen, obwohl
sie unter Data Sources bereits sichtbar war.

Der tatsächliche allgemeine Weg ist:

1. `sources_browser.domain_folders()` bestimmt die konfigurierten Domain-Ordner.
2. `discover_domain_files()` entdeckt Dateien über die vorhandene Mixed-Discovery.
3. `knowledge_summary._domain_scoped_sources()` liefert die registrierten
   KnowledgeStore-Quellen nach der bestehenden Domain-Policy.
4. `source_inventory()` führt beide Mengen zusammen und unterdrückt bereits
   registrierte Dateipfade anhand logischer und aufgelöster Pfade.
5. Import bleibt eine ausdrückliche, getrennte Aktion. Ein InfoSite-Eingang ist
   weder für Discovery noch für den neuen Snapshotzugriff erforderlich.

### Read-only-Befund am vorhandenen System

Es wurden keine Produktionsmigrationen, Importläufe oder Serverneustarts
ausgeführt. Vorhandene Inhalte wurden nicht geändert. Geprüft wurden
Dateisystem-Metadaten und Zählungen, keine Dokumenttexte oder Zugangsdaten:

- Konfiguriertes Datenlayout: **Version 3**, Root `~/dev_data/ki-knowledge`.
- Vorhandene Markdown-Dateien in den durchlaufenen Markdown-Ordnern:
  `anthro` 85, `engineering` 1, `knowledge-ops` 52, `loadtest` 45,
  `psycare` 8, `web` 15 — zusammen **206**. Das ist eine Dateisystemzählung,
  keine Behauptung, alle Dateien seien importiert oder sämtliche Domains
  besäßen bereits dieselben Anwendungsdatenbankeinträge.
- Die aktuelle Konfiguration verwendet **PostgreSQL** für Django und
  KnowledgeStore. Eine explizit schreibgeschützte Verbindung meldete
  `transaction_read_only = on`.
- Dort zum Prüfzeitpunkt: **8 InfoSite-Projekte**, **142 SourceDocument-Eingänge**,
  **0 Workbench-Dokumente**, **3.950 KnowledgeStore-Quellen** und
  **139.381 KnowledgeStore-Blöcke**.
- KnowledgeStore-Quellentypen: `ia3_observation` 3.601, `pdf` 330, `tei` 10,
  `markdown` 5, `iasem_quiz` 3, `nextcloud_markdown` 1.
  Daraus folgt ausdrücklich nicht, dass 3.950 lokale Markdown-Dateien vorhanden
  oder direkt als Textsnapshot erfassbar wären.
- Die InfoSite-Eingänge verteilen sich auf `anthro` 96, `human-design` 1 und
  `loadtest` 45. Es existieren also allgemeine Markdown-Domains ohne einen
  entsprechenden InfoSite-Projektbestand.
- Die aktive Datenbank enthielt bereits Migration `0021`; **`0022` wurde dort
  nicht angewendet**.

Zusätzlich wurden vorhandene SQLite-Dateien ausschließlich mit
`mode=ro&immutable=1` und `PRAGMA query_only=ON` gelesen, ohne Store-Konstruktoren,
Schemaeinrichtung oder WAL-/Shared-Memory-Erzeugung. Sie enthielten ältere,
abweichende Bestände: 7 Projekte/141 Eingänge sowie 335 Quellen/125.092 Blöcke.
Diese Dateien sind **nicht** der aktuelle PostgreSQL-Bestand; sie dürfen nicht
als Beleg für dessen Vollständigkeit verwendet werden. Immutable-Lesen ist
zudem kein Ersatz für die Auswertung eventuell ausstehender WAL-Inhalte.

## 2. Implementierte Grenze: ein Adapter, kein zweites Register

`django_site/source_access.py` verwendet die bestehende Discovery,
`source_inventory()`, Domainabgrenzung und Ordnerauflösung. Es schreibt weder ein
neues Quellenregister noch erzeugt es SourceDocument-Eingänge.

Die Quelle wird beim Listen und erneut beim Erfassen aus dem aktuellen Inventar
bestimmt. Das Frontend sendet keine frei eingegebenen absoluten Pfade:

```text
GET  /knowledge/workbench/api/sources?domain=...
POST /knowledge/workbench/api/documents?domain=...
     {"source_id": "src_<64 hex characters>"}
```

Die Auswahl-ID ist ein deterministischer serverseitiger HMAC über Domain und
vorhandene Quellenreferenz: registrierte Store-ID oder kontrolliertes
Ordner-/Relativpfad-Paar. Sie ist kein Pfad-Encoding, kein zusätzlicher
Datenbankeintrag und keine Berechtigungsfreigabe. Unveränderte Referenzen bleiben
über Listenaufrufe und Prozessneustarts mit demselben `SECRET_KEY` stabil.
Ein Schlüsselwechsel invalidiert solche Auswahl-Links. Wird aus einer
entdeckten Datei eine registrierte Quelle, ändert sich ihre Inventarreferenz;
die **Snapshotidentität derselben Datei bleibt** über den kanonischen Dateipfad
und Inhalt erhalten. Alte, nicht mehr vorhandene Auswahlreferenzen werden
abgewiesen, nicht als freie Pfade interpretiert.

Die Quellenantwort enthält:

- `sources`: auswählbare lokale Markdown-Quellen mit opaker `id`, Titel,
  Ordner, Relativpfad, Importstatus und gegebenenfalls KnowledgeStore-ID.
- `excluded`: die übrigen Inventareinträge mit nachvollziehbarem `reason`.
  Mehrfachregistrierungen desselben kanonischen Pfads werden hier ausdrücklich
  als Dubletten benannt; `canonical_id` verweist auf die auswählbare Referenz.
  Direkte Links auf solche Aliasreferenzen wählen im Frontend die kanonische
  Referenz vor.

PDFs, Beobachtungen, TEI, entfernte Quellen, fehlende Dateien und nicht
vertrauenswürdige Dateilinks verschwinden daher nicht kommentarlos aus der
Workbench-Antwort. Die UI zeigt sie unter **Nicht erfassbare Quellen**.
Größen-, UTF-8- und während des Lesens auftretende Fehler werden beim Capture
gemeldet; die reine Quellenliste liest keine Markdown-Inhalte.

## 3. Pfad-, Link- und Sicherheitsverhalten

- Die gemeinsame `resolve_folder_file()`-Prüfung verwirft absolute Eingaben,
  Traversal und Pfade außerhalb des jeweiligen Ordners.
- Vertrauenswürdig sind die konfigurierten Domain-Wurzeln einschließlich ihrer
  aufgelösten Ziele sowie verlinkte Verzeichniswurzeln, die der vorhandene
  `linked_subdirectories()`-Mechanismus von Data Sources erkennt.
- Ein `mix/`-Wurzellink oder ein erkannter verlinkter Markdown-Unterordner bleibt
  nutzbar. Eine beliebige Datei-Symlink-Abkürzung auf ein sonst nicht vertrautes
  Ziel bleibt gesperrt. Die gemeinsame Auflösung gilt damit auch für bestehende
  Data-Sources-Dateiaktionen, nicht nur für den neuen Editor.
- Der vorhandene Linkscanner hat eine begrenzte Suchtiefe und einen Cache;
  diese Policy wurde nicht durch einen unbeschränkten zweiten Scanner ersetzt.
  Ein außerhalb dieser Vertrauensmenge entdeckter Pfad erhält einen expliziten
  Ausschlussgrund.
- Der Capture-Leser öffnet den überprüften kanonischen Dateipfad über
  Dateideskriptoren mit `O_NOFOLLOW`, prüft reguläre Datei, 2-MiB-Limit,
  Vorher-/Nachher-Signaturen und erneut aufgelöste Herkunft. UTF-8 und
  normalisierte LF-Zeilenenden bleiben der Snapshotvertrag.
- Die vorhandene Domain-Policy wird wiederverwendet, nicht durch eine neue
  globale Suche ersetzt. Auswahl-IDs einer anderen Domain funktionieren nicht.
- Quellenliste und neue Captures bleiben **Staff-only**; Arbeitsdokumente,
  Markierungen, Relationen und Gespräche bleiben eigentümer- und domainprivat.
  Ein Staff-Status gibt keinen Zugriff auf die privaten Snapshots anderer.
- Die allgemeine `Domain` muss weiterhin registriert sein. Das ist kein
  InfoSite-Projektzwang und führt nicht zu einer automatischen Projektanlage.

Die Verwaltung der serverseitigen Quellordner und Verzeichnislinks ist eine
administrative Vertrauensgrenze. Diese Änderung macht daraus keine neue
Dateisystem-ACL oder Mehrbenutzer-Sandbox.

## 4. Persistenz und Legacy-Verträglichkeit

`0022_workbench_generic_origin` ergänzt ausschließlich:

- `WorkbenchDocument.origin_key`, leer für unangetastete Altbestände;
- `origin_metadata` mit Herkunftstyp, Store-ID bzw. Ordner/Relativpfad;
- eine bedingte Unique-Constraint für Referenz-Captures nach Eigentümer, Domain,
  kanonischer Herkunftsidentität und normalisiertem Inhaltshash.

Die nullable SourceDocument-FK bleibt erhalten. Neue allgemeine Captures benötigen
sie nicht; alte und neue über den Legacy-API-Eingang erzeugte Referenzen dürfen
sie weiter besitzen. Dokument-, Revisions-, Markierungs- und Ankeridentitäten
werden nicht ersetzt. Es gibt keine Lösch-, Zusammenführungs- oder
Inhaltsmigration und kein nachträgliches Umschreiben historischer Herkunft.

Der neue und der alte Capture-Eingang verwenden dieselbe Persistenzroutine.
Unveränderter Inhalt derselben kanonischen Datei wird wiederverwendet; ein neuer
Inhalt ergibt einen neuen historischen Snapshot. Eine identische alte Referenz
mit bekanntem Locator bzw. ihrer alten FK wird wiederverwendet, ohne ihren
Herkunftsnachweis umzuschreiben. Beliebige historische, rein relative Locator-
Varianten werden nicht nachträglich durch eine destruktive Datenmigration
vereinheitlicht.

## 5. Geänderte Dateigrenzen

| Bereich | Dateien / Verantwortung |
|---|---|
| Gemeinsamer Zugriff | `django_site/source_access.py`: Inventaradapter, Auswahlreferenzen, Ausschlüsse, kontrollierte Herkunft |
| Bestehende Data Sources | `sources_browser.py`: gemeinsamer aufgelöster Pfadschutz; vorhandene Discovery und Zusammenführung bleiben führend |
| Workbench-Backend | `workbench_service.py`: gemeinsame Capture-Lese-/Persistenzroutine, generische Herkunft, Legacy-Kompatibilität; `views_workbench.py`: vollständige Quellenantwort |
| Modell | `workbench_models.py`, `migrations/0022_workbench_generic_origin.py`: additive Herkunft und Unique-Constraint |
| Direkte Einstiege | `views_source_browser.py`, `views_source_detail.py`, `widgetkit_templates/sources_list.html`, `templates/kicli_django/source_detail.html`: Staff-Links und Ausschlussgründe |
| Frontend | `frontend/workbench/src/main.tsx`, `types.ts`: String-IDs, reale Quellenlabels, Diagnostik, Vorwahl ohne Auto-Capture |
| Gebaute Auslieferung | `static/django_site/workbench/`: aktualisiertes Vite-Manifest, Bundle und Lizenzhinweise |
| Python-Prüfung | `tests/test_workbench_backend.py`, `tests/test_sources_browser.py`: echte isolierte ORM- und Inventar-/Viewprüfung |
| Browserprüfung | `frontend/workbench/tests/server.py`, `tests/browser/workbench.spec.ts`: isoliertes Projektverzeichnis, allgemeine Quellen ohne InfoSite-Projekte, echte Persistenz |
| Dokumentation | dieser Bericht, `doc/INDEX.md`, Workbench-Anleitung, Architektur- und Designstatus |

Der frühere Testserver verwendete ein Betriebssystem-Tempverzeichnis. Er benutzt
jetzt ein eigenes, abschließend entferntes Verzeichnis im Projekt. Die
Browserfixture enthält **null InfoSite-Projekte**, registrierte Markdown-Dateien,
eine nicht importierte Markdown-Datei und einen sichtbar ausgeschlossenen PDF.

## 6. Nachweise und Grenzen der Validierung

Ausgeführt:

```bash
.venv/bin/python -m pytest -q --basetemp=.pytest-source-access \
  tests/test_sources_browser.py tests/test_workbench_backend.py \
  tests/test_workbench_assets.py tests/test_django_module_boundaries.py

cd frontend/workbench
npm run build
npm test
TMPDIR="$PWD/../../.source-access-runtime" npm run test:browser
```

Das projektlokale Laufzeitverzeichnis für `TMPDIR` muss vor dem Browseraufruf
existieren. Testdatenbanken und Quellen werden dort bzw. in eigenen isolierten
Projektverzeichnissen angelegt und nicht aus dem Livebestand übernommen.
Der Build verwendet die bereits installierten npm-Abhängigkeiten; es war kein
neuer Installationslauf erforderlich.

Geprüfte Fälle:

- Allgemeines Inventar mit **null InfoSite-Projekten und null SourceDocuments**:
  normale entdeckte Markdown-Datei erscheint und lässt sich erfassen.
- Registrierte KnowledgeStore-Markdown-Quelle erscheint und lässt sich erfassen.
- Discovery/Listen/Capture erzeugen keine SourceDocuments, Projekte,
  KnowledgeStore-Records oder impliziten Importe.
- Wiederholter Capture, kanonischer Pfad, Aliasregistrierung sowie Übergang
  entdeckte → registrierte Datei erzeugen keinen identischen zweiten Snapshot.
- Konfigurierte verlinkte Wurzel und erkannter verlinkter Unterordner sind nutzbar;
  Traversal, freie Pfade und beliebige außerhalb liegende Datei-Linkziele werden
  abgewehrt. Austausch einer Quelle gegen einen Außenlink gibt keinen Zugriff.
- Falsche Domain, nicht angemeldete Benutzer, Nicht-Staff und fremde Eigentümer
  werden abgewehrt; bestehende eigene Snapshots bleiben unabhängig vom aktuellen
  Quellenzugriff lesbar.
- Migration vom alten Workbench-Schema bis einschließlich `0022` erhält FK,
  Locator, Dokument-/Revisions-IDs, Text, Markierung und Anker.
- Staff-Links aus Quellenliste und Detail, Vorwahl im Browser, opake String-
  Übertragung, sichtbarer PDF-Ausschluss und Capture vor Import funktionieren.
- Bestehende Unicode-/Koordinaten-, CSRF-, Transaktions-, Revisions-, Konflikt-,
  Relations- und Gesprächsprüfungen bleiben grün.

Der erste kombinierte Python-Aufruf zeigte vier schon beim isolierten Aufruf
der Inventartests vorhandene Django-Bootstrapfehler. Die betreffende
No-Database-Fixture initialisiert Django nun selbst mit einer In-Memory-
Datenbank und sperrt anschließend SQL-Zugriffe; der gezielte Aufruf ist damit
selbstständig reproduzierbar.

Die verbindlichen Abschlusszahlen stehen am Ende dieses Berichts.
Die Python-Integration verwendet echte migrierte **SQLite-In-Memory-Datenbanken**,
die Browserprüfung eine eigene isolierte SQLite-Datei. Ein schreibender
PostgreSQL-Migrationstest gegen den Livebestand wurde bewusst nicht durchgeführt.
Der Produktionsbuild meldet weiterhin den bekannten großen Monaco-Chunk
(etwa 2,47 MB vor gzip); das ist eine Warnung, kein Buildfehler.

## 7. Ehrlich offen: nächste InfoSite-/UI-Phase

1. InfoSite weiter als Projekt-/Generierungsworkflow behandeln und dessen eigene
   Input-, Record-, Blockstore-, Output- und Wagtail-Grenzen separat prüfen.
   Dieser Schritt hat deren Gesamtkonsistenz nicht nachgewiesen.
2. Die bestehende Brücke „InfoSite-Projekt aus Records anlegen“ in der
   Quellendetailansicht bleibt erhalten. Ihre Benennung, Wiederverwendung
   generierter Markdown-Eingänge und Abgrenzung zur allgemeinen Quellenansicht
   sind Themen des folgenden Audits.
3. Generierte Outputs sind durch diese Änderung nicht pauschal neue
   Data-Sources-Eingänge. Ein universeller Output-/Artefakt-Dokumentadapter,
   Remote-Download, PDF-Textprojektion und Nextcloud-Snapshotzugriff sind nicht
   heimlich ergänzt worden.
4. Teamfreigaben, feinere Rollen, Aufbewahrung/Löschen und eine gemeinsame
   Rechtestruktur für Quelle, Projekt, Record und Werkstatt bleiben eigene
   Produktentscheidungen; die private Staff-Capture-Policy bleibt bestehen.
5. Sehr große Inventare werden derzeit vollständig nach der vorhandenen
   Discovery-Policy durchlaufen. API-Paginierung, Suchauswahl und weitere
   Performancearbeit sind noch kein Bestandteil dieses Schritts.
6. Auswahl-Links sind keine dauerhaften, von Quellregistrierung, Umzug oder
   Schlüsselrotation unabhängigen Dokument-IDs. Bereits angelegte Snapshots
   haben davon getrennte dauerhafte UUIDs und bleiben erreichbar.
7. E4 (KI-Änderungsvorschläge), E5 und E6 wurden nicht begonnen.

**Betriebliche Übernahme steht noch aus:** Anwendung der additiven Migration
`0022` und Auslieferung der gebauten Assets erfolgen später im normalen
Betriebsverfahren nach Sicherung. Kein Liveprozess wurde für diese Prüfung
neu gestartet.

## 8. Abschlussergebnis

- Python-Regressionskommando aus Abschnitt 6: **90 bestanden**.
- `npm run build`: **erfolgreich**, TypeScript-Prüfung und gebaute Auslieferung
  einschließlich Manifest/Lizenzhinweisen aktualisiert; bekannte Chunkwarnung.
- `npm test`: **3 bestanden**.
- Playwright gegen den isolierten echten Django-Testserver: **4 bestanden**.
  Der absichtliche Mock-Providerfehler wird dabei als HTTP 502 geprüft und ist
  kein fehlgeschlagener Test.
- Keine neuen Abhängigkeiten installiert; keine Produktionsmigration, kein
  Live-DB-Schreibzugriff und kein Neustart eines vorhandenen Servers.
- Priorität 1 ist abgeschlossen; breiterer InfoSite-Audit und E4–E6 sind
  ausdrücklich nicht als erledigt markiert.

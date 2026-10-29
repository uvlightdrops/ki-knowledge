# Bestandsaufnahme und Bereinigungsreihenfolge

Stand: **2026-10-28**. Dies ist eine Quellcode- und Strukturaufnahme, kein
vollstaendiger Funktionstest, keine Sicherheitspruefung und kein Deploymentbericht.

**Nachtrag, erster Bereinigungsschritt:** Der Packaging-Vertrag wurde
inzwischen korrigiert und der zweite Jira-Quellbaum nach Inhaltsvergleich
entfernt. Die Ausgangszahlen und Befunde unten bleiben als Bestandsaufnahme
erhalten. Umsetzung und Grenzen stehen im
[Paket-Build-Leitfaden](../guides/packaging.md).

**Nachtrag, P1 Retrieval/Jira:** Suche, Timeline, Graph-Explorer und
Domainanalyse nutzen jetzt einen gemeinsamen fachlichen Service ausserhalb
von Django; bestehende Django-Imports bleiben kompatibel. Der neue Schnitt
und die verbleibenden Grenzen sind im
[Service-/Views-Refactoring](../refactorings/views-module-architecture.md#p1-shared-jira-retrieval-service-2026-10-28)
beschrieben.

**Nachtrag, P1 Import/Jobs:** Auch die synchrone Importstatus-Uebernahme ist
jetzt in fachliche Job-Orchestrierung und einen Django-Repository-Adapter
getrennt. Der [Importvertrag](../features/INFOSITE.md#import-control-current-execution-contract)
unterscheidet Statusuebernahme, Inhaltsimport und Hintergrundausfuehrung
explizit. ORM-Batchfehler rollen die Dokumentaenderungen zurueck; Jobjournal
und ORM bleiben getrennte Transaktionsgrenzen. Es wurde kein Worker eingefuehrt.

**Nachtrag, erster P2-Schnitt:** Die Dateisystem-/Domainpfadlogik liegt jetzt
in `services/domain_paths.py`, Django behaelt Cache und kompatible Exporte.
Layoutversionen, Namensregeln und bestehende Pfadnebenwirkungen sind
unveraendert. Die zwei historischen Domain-Default-/Slug-Politiken bleiben
explizit getrennt; Einzelheiten und verbleibende Aufgaben stehen im
[P2-Refactoring](../refactorings/views-module-architecture.md#p2-domainfilesystem-boundary-2026-10-28).

**Nachtrag, zweiter P2-Schnitt:** InfoSite-/Wagtail-Zustaendigkeiten und
fuehrende Speicher sind in der
[Content-Matrix](../architecture/content-model-matrix.md#0-verbindliche-speicher--und-adaptergrenze-p2)
festgehalten. CMS-Kataloge lesen gespeicherte Blocksätze schreibgeschuetzt;
fehlende CMS-Seiten werden nur explizit per `setup_wagtail_cms` angelegt
und veroeffentlicht. Dateiinhalte, gemeinsames ORM-Register und
Redaktionsmetadaten bleiben getrennte Verantwortungen ohne Datenkopien,
ID-Migration oder Zusammenlegung der Stores.

## Kurzbefund

**Nachtrag, grosse Sammelmodule:** Die im spaeteren Arbeitsstand noch
2.328 Zeilen grosse `django_site/services.py` und die 1.977 Zeilen grosse
`views_data_sources.py` wurden nach fachlichen Aufgaben aufgeteilt.
Beide bleiben als kompatible Fassaden erhalten; ueberschriebene
Service-Altimplementierungen sind entfernt. Die neuen Modulzustaendigkeiten
und unveraenderten Schnittstellen stehen im
[Service-/Views-Refactoring](../refactorings/views-module-architecture.md#responsibility-split-of-services-and-source-views-2026-10-28).
Die Ausgangszahlen unten dokumentieren weiterhin den urspruenglichen Befund.

**Nachtrag, P3 Einstiegspfade:** Der globale `stackctl` ist jetzt auch hier
der dokumentierte Lifecycle-Einstieg wie in der aktuellen Assist-Anbindung.
Der lokale `kistack`-Alias installiert keine zweite Toolkopie mehr; alte
Python-Launcher bleiben reine Weiterleitungen. Details und bewusst
erhaltene Kompatibilität stehen im
[P3-Refactoring](../refactorings/views-module-architecture.md#p3-lifecycle-entry-points-2026-10-28).

Das Projekt ist fachlich breit, aber nicht allein wegen seiner Groesse
"zu gross". Schwer beherrschbar wird es durch **vermischte Verantwortlichkeiten,
mehrere Praesentations-/Einstiegsschichten und uneindeutige Altbestaende**.
Die naechste sinnvolle Massnahme ist keine Neuentwicklung und kein pauschales
Loeschen von Features, sondern eine schrittweise Trennung hinter stabilen
Schnittstellen.

Der fachliche Kern bleibt nachvollziehbar:
**Quellen aufnehmen -> Inhalte/Knowledge Blocks speichern -> suchen und
analysieren -> aufbereitete Ausgaben praesentieren.** Django, FastAPI und CLI
sind unterschiedliche Zugaenge dazu; Wagtail ergaenzt eine editoriale Sicht.
Problematisch ist nicht schon ihre Existenz, sondern dass die fachliche
Orchestrierung teilweise im Django-Webpaket liegt.

## Umfang und Zaehlbasis

Erfasst wurden mit `git ls-files` die zu Beginn der Aufnahme getrackten
Dateipfade und deren Arbeitskopie-Inhalte. Laufzeitdaten, virtuelle Umgebungen,
Secrets, ungetrackte Dateien und externe Daten-Symlinks wurden nicht gezaehlt.
Die anschliessende Dokumentationsumsortierung ist in den folgenden
Ausgangszahlen noch nicht enthalten.

| Groesse | Ausgangsbestand |
|---|---:|
| Getrackte Dateien insgesamt | 476 |
| Davon Dokumente unter `doc/` und `docs/` | 46 |
| Dateien ausserhalb dieser Dokumentationsbaeume | 430 |
| Python-Dateien, einschliesslich Tests, Examples und `src/` | 266 |
| Python-Zeilen insgesamt | 53.059 |
| Testdateien / Testzeilen | 58 / 10.027 |
| Python-Zeilen ausserhalb der Tests | 43.032 |
| HTML-/Jinja-Templates | 116 |
| JavaScript-Dateien / CSS-Dateien | 14 / 12 |
| Django-Migrationsdateien | 23 |

Zeilenzahlen beschreiben Umfang, nicht Komplexitaet, Qualitaet oder
Testabdeckung. Die Testdateizahl ist **keine Coverage-Messung**.

### Verteilung des Python-Codes

| Pfad | Python-Dateien | Zeilen | Schwerpunkt |
|---|---:|---:|---|
| `ki_knowledge/` insgesamt | 188 | 39.234 | Gesamtes Hauptpaket |
| `ki_knowledge/django_site/` | 81 | 18.517 | Web, ORM, Administration, Workflow-Orchestrierung |
| `ki_knowledge/integrations/` | 29 | 9.733 | Quellen, Persistenz, Suche und externe Dienste |
| `ki_knowledge/services/` | 12 | 2.642 | Discovery, Import und Generierung |
| `ki_knowledge/knowledge/` | 10 | 1.965 | Wissensmodelle, Ingestion und Artefakte |
| `ki_knowledge/cli/` | 10 | 1.098 | Kommandozugang |
| `ki_knowledge/api/` | 3 | 613 | FastAPI-Zugaenge |
| `ki_knowledge/infosite/` | 4 | 583 | Praesentationsgenerierung |
| `ki_knowledge/wagtail_cms/` | 10 | 567 | Editorial-/CMS-Adapter |
| `ki_knowledge/ui/` | 4 | 537 | UI-nahe Clients |
| `ki_knowledge/node_sync/` | 6 | 380 | Sync-Vertraege und Adapter |
| `src/ki_knowledge/` | 6 | 1.700 | Zweiter, ungeklaerter Jira-Quellpfad |

Unterpakete sind bereits in der Gesamtzeile des Hauptpakets enthalten und
duerfen nicht nochmals dazuaddiert werden.

## Was die Beherrschbarkeit erschwert

### 1. Fachliche Schaltzentrale im Webpaket

[`django_site/services.py`](../../ki_knowledge/django_site/services.py) hat
**2.434 Zeilen**. Es vereint unter anderem Pfad-/Domainfragen, Quellen,
Semantic-/Job-Ablauf, Jira, Graph und Zusammenfassungen. Bereits vorhandene
Auslagerungen sind ein guter Anfang, aber noch keine vollstaendige fachliche
Trennung.

Weitere grosse Module:

| Modul | Zeilen |
|---|---:|
| `django_site/views_data_sources.py` | 1.977 |
| `integrations/semantic_terms.py` | 1.522 |
| `django_site/infosite_views.py` | 1.209 |
| `integrations/knowledge_store.py` | 1.101 |
| `services/generator.py` | 1.034 |
| `django_site/views_dashboard.py` | 1.024 |
| `integrations/pdf_batch.py` | 846 |
| `django_site/dashboard_registry.py` | 809 |

Die acht Dateien `django_site/views*.py` haben zusammen 4.165 Zeilen und
94 Top-Level-Funktions-/Klassendefinitionen. `infosite_views.py` liegt neben
dieser `views*`-Gruppe und ist darin nicht mitgezaehlt.

**Konkreter Pfad:** Die Jira-Suche im
[`views_data_sources.py:1469-1477`](../../ki_knowledge/django_site/views_data_sources.py#L1469-L1477)
ruft `jira_hybrid_search(...)` auf. Die Umsetzung in
[`services.py:1785-1798`](../../ki_knowledge/django_site/services.py#L1785-L1798)
laedt Cache/Assistant, initialisiert gegebenenfalls Embeddings und fuehrt die
Suche aus. Auch
[`api/app.py:53-65`](../../ki_knowledge/api/app.py#L53-L65)
ruft dieselbe Django-Servicefassade auf. Damit haengt ein API-Pfad an einer
UI-nahen Schaltzentrale.

### 2. Jobbegriff und Ausfuehrungsmodell sind nicht ueberall deckungsgleich

[`infosite_views.py:769-787`](../../ki_knowledge/django_site/infosite_views.py#L769-L787)
liest ausgewaehlte Dokumente aus dem Request und ruft
`enqueue_and_run_import(...)` auf. Der Runner erzeugt einen Job und fuehrt ihn
direkt synchron aus:
[`services/import_runner.py:64-70`](../../ki_knowledge/services/import_runner.py#L64-L70).
Er greift dabei auf Django-`SourceDocument` zu und aktualisiert dessen Status
([Zeilen 34-54](../../ki_knowledge/services/import_runner.py#L34-L54)).

Das ist nicht automatisch falsch, muss aber als synchroner Import mit
Jobprotokoll verstanden werden, nicht als unabhaengiger Hintergrundworker.
Eine spaetere Entkopplung muss Request-Verhalten, Fehlermeldungen und
Statusfortschreibung explizit erhalten oder bewusst migrieren.

### 3. Mehrere Sichten auf denselben Inhalt

InfoSite-/Quellmodelle, KnowledgeStore und Wagtail sind unterschiedliche
technische Sichten. Wagtail ist als additive Editorial-Schicht angelegt und
liest aus `InfoSiteProject`/`InfoSiteSourceAdapter`
([`wagtail_cms/models.py:64-94`](../../ki_knowledge/wagtail_cms/models.py#L64-L94)).

Die Einfuehrung eines weiteren Modells oder einer weiteren UI ist daher nicht
die erste Bereinigung. Zuerst muss fuer Quelle, Importstatus, Wissensblock und
editoriale Ausgabe jeweils klar sein, **welcher Speicher fuehrend ist**.
Die [Content-Matrix](../architecture/content-model-matrix.md) und das
[Workspace-Konzept](../architecture/source-workspace-and-workflow-concept.md)
liefern dafuer bereits fachliche Vorarbeit.

### 4. Ungeklaerter zweiter Quellpfad und Packaging-Vertrag

Unter `src/ki_knowledge/integrations/` liegen sechs getrackte Python-Dateien
mit 1.700 Zeilen. Fuenf Jira-Module existieren ebenfalls im Hauptpaket.
Vier davon sind byte-identisch (`jira_cache`, `jira_client`, `jira_csv`,
`jira_graph`), `jira_assistant` weicht ab.

Die Paketkonfiguration verwendet dagegen explizit
`packages = ["ki_knowledge"]`
([`pyproject.toml`](../../pyproject.toml)), keine `src`-Discovery.
Eine Repository-Referenz, die diesen zweiten Paketbaum aktiviert, wurde bei
der Aufnahme nicht gefunden. Das ist ein **Klaerungsbedarf**, kein Beweis,
dass er gefahrlos geloescht werden darf. Ebenso muss der Bau eines
nicht-editierbaren Pakets die tatsaechlichen Unterpakete und Assets erfassen;
ein funktionierender Editable-Checkout allein bestaetigt das nicht.

### 5. Dokumentation beschrieb mehrere Zeitstaende als scheinbar einen

Es gab 44 Dokumente unter `doc/` und zwei unter `docs/`, ohne gemeinsamen
Einstieg. Historische Extraktionsplaene, Betriebsanleitungen und
Ist-/Soll-Architektur lagen nebeneinander. Das Root-README verwies unter
anderem noch auf ein nicht mehr lokales `ki_knowledge/widgetkit_django/`.
Eine gemeinsame YAML-Betriebsanleitung lag als identische Vollkopie vor.

Das erzeugt reale Fehlentscheidungsrisiken: ein alter Plan kann fuer eine
aktuelle Schnittstelle gehalten werden, ein anderes Paket fuer lokalen Code.

## Empfohlene Zielgliederung

Keine sofortige Aufteilung in weitere Repositories:

| Schicht | Verantwortung | Grenze |
|---|---|---|
| Knowledge-Kern | Quellen-/Block-/Artefaktvertraege und fachliche Operationen | Keine HTTP-Requests oder Template-Kontexte |
| Fachliche Services | Import, Retrieval, Semantic-/Job-Ablauf, Generierung | Definierte Store-/ORM-Adapter statt UI-Sammelmodul |
| Integrationen/Persistenz | PDF, Jira, Nextcloud, Embeddings und Datenbanken | Kein Seitenaufbau |
| Adapter | CLI, FastAPI, Django, Wagtail | Validieren, aufrufen, Ergebnis darstellen |
| Betrieb | Stack-Spec und gemeinsame Werkzeuge | Keine zweite Lifecycle-Implementierung in der Anwendung |

Vorhandene Verzeichnisse schrittweise auf diese Verantwortung ausrichten.
Neue Unterpakete nur dann einfuehren, wenn ein konkreter, getesteter Schnitt
entsteht; Ordner allein sind keine Entkopplung.

## Priorisierte Bereinigung in kleinen Schritten

| Prioritaet | Begrenzter Schritt | Fertigkriterium |
|---|---|---|
| P0 | Paket-/Build-Vertrag und zweiten `src/`-Baum klaeren | Wheel in sauberer Umgebung enthaelt benoetigte Module/Assets; kanonischer Importpfad dokumentiert; abweichende Jira-Datei bewertet |
| P1 | Ein fachliches Teilgebiet aus `django_site.services` herausziehen, zuerst z.B. Retrieval/Jira | HTML- und API-Aufruf nutzen dieselbe fachliche Implementierung; alte Imports bleiben als Fassade kompatibel |
| P1 | Source-Import und Jobausfuehrung getrennt beschreiben und kapseln | Synchron/async eindeutig; Job-/Dokumentstatus und Fehlerpfade durch gezielte Tests abgesichert |
| P2 | Uebrige Service-Cluster einzeln auslagern | Domain/Pfade, Quellen, Semantik/Jobs und Knowledge getrennt; keine neue Sammeldatei |
| P2 | Wagtail-/InfoSite-Adaptergrenze und fuehrende Speicher festlegen | Kein ungeprueftes Doppelpflegen derselben fachlichen Wahrheit |
| P3 | Erst danach Altmodule und weitere Einstiegspfade entfernen | Import-/URL-/Persistenz-Kompatibilitaet explizit geprueft |

Bei jeder Extraktion bestehende Re-Exports erhalten, gezielte Tests fuer
beide Verbraucher ausfuehren und keine Datenmodellmigration mit einem reinen
Modulumbau vermischen. Die alten
[Services-Refactor-Notizen](../archive/developer/services-refactor-plan.md)
sind historischer Kontext, kein Nachweis bereits vollendeter Trennung.

## In dieser Bestandsaufnahme bereits bereinigt

- `doc/` in `architecture`, `guides`, `features`, `integration`,
  `refactorings`, `tracking` und `archive` gegliedert.
- [Einstieg](../README.md) und [vollstaendigen Index](../INDEX.md) hinzugefuegt.
- Historische Jira-Namensweiterleitungen und abgeschlossene/aeltere Berichte
  ins Archiv eingeordnet, ohne ihren fachlichen Inhalt zu verwerfen.
- Die beiden projektuebergreifenden CLI-Entwuerfe aus `docs/` nach
  `~/dev_doc/cli-management/archive/` verschoben und dort als historisch markiert.
- Die identische YAML-Vollkopie durch einen projektspezifischen Einstieg mit
  Verweis auf die kanonische Quelle ersetzt.
- Relative Dokumentlinks, Root-README, Codekommentare und den
  dokumentlesenden Widget-Katalog-Test auf die neuen Pfade umgestellt.
- Den lokalen `doc/link`-Daten-Symlink, ungetrackte Dateien und bestehende
  Laufzeitkonfiguration unveraendert gelassen.

**Nicht umgesetzt:** kein grosser Code-Refactor, keine Modul-/Featureloeschung,
keine Datenmigration, keine Aenderung von URLs oder Laufzeitdiensten.

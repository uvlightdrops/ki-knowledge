---
project: ki-knowledge
agent_project: ki-knowledge
scope: architecture
created: null
updated: "2026-11-09 11"
update_reason: "wissenswiki-core als eigenes Paket mit schlanker Web-App"
status: draft
semantic_blocks:
  - starting-point
  - bridge-findings
  - options
  - recommendation
  - fresh-django
  - target-architecture
  - migration-path
  - legacy-exit
  - risks-and-decisions
relations:
  - target: KI-KNOWLEDGE-KONZEPT.md
    type: references
    reason: "Fachlicher Gesamtentwurf, an dem sich die Weiterentwicklung ausrichtet"
  - target: WISSENSWIKI-TECHNIK.md
    type: references
    reason: "Technischer Weg des Wissenswikis"
  - target: SYSTEM_OVERVIEW.md#product-direction
    type: references
    reason: "Produktausrichtung"
  - target: KNOWLEDGE-WORKBENCH-CONCEPT.md
    type: references
    reason: "Textwerkstatt mit Revisionen, Ankern und Vorschlägen"
---

# Weiterentwicklung von ki-knowledge

Entwurf für eine gesunde Weiterentwicklung, nachdem zwei Werkzeuge mit
ähnlichem Zweck nebeneinander entstanden sind. Er beschreibt Optionen und eine
Empfehlung, keine beschlossene Planung.

<a id="starting-point"></a>
## Ausgangslage [starting-point]

| | Django-App ki-knowledge | Wissenswiki (doc_viewer) |
|---|---|---|
| Umfang | ca. 19 000 Zeilen in `django_site`, dazu ca. 15 000 in services, integrations, knowledge, api, wagtail_cms; 26 Migrationen, 77 Templates | ca. 1 000 Zeilen Python und 1 000 Zeilen JS/CSS/HTML |
| Technik | Django, Wagtail, Widgetkit, ORM (SQLite/PostgreSQL), KnowledgeStore, Jobs, verteilte Synchronisation | Standardbibliothek: `http.server`, Markdown-Dateien, JSON-Beziehungen, SVG/JS |
| Datenwahrheit | gemischt: Quelldateien, Ausgabeordner, ORM-Modelle (`Workbench*`, `InfoSite*`), `block_store.db` | Dateien: ein Block je Markdown-Datei, Beziehungen als JSON mit Revision und Sperre |
| Stärken | Import vieler Formate, InfoSite-Ausgabe, Textwerkstatt mit Revisionen, Ankern, Gesprächen und KI-Vorschlägen, Retrieval, Suche, Chat, Betrieb über stackctl | klares Blockmodell, typisierte gerichtete Beziehungen, sichtbares Wissensnetz, Metadatenvergleich, schnell änderbar |
| Schwächen | viele Altpfade (Jira, Kompatibilitätsfassaden, mehrere Speicher), hohe Änderungskosten | keine Versionen, keine KI, keine Anmeldung, keine Importformate |

Das Wiki ist in wenigen Tagen entstanden und deckt den Kern der
[Produktausrichtung](SYSTEM_OVERVIEW.md#product-direction) – Blöcke,
anpassbare Metadaten und domänenspezifische Relationen – sichtbarer ab als die
Django-App.

<a id="bridge-findings"></a>
## Erkenntnisse aus der Brücke [bridge-findings]

Die temporäre Brücke (`ki_knowledge/wiki_bridge.py`, Option `--ki-domains`)
lässt beide Werkzeuge auf den Daten des anderen arbeiten:

- Die Wiki-Ansicht liest alle Django-Markdowns ohne Anpassung, sobald sie
  Dateien ohne YAML-Header tolerant behandelt. Erste Probe: anthro 15,
  anthro/sstk 98, web 48, loadtest 215, psycare 31 Blöcke, keine Fehler.
- Die Django-Discovery erkennt das Wiki-Verzeichnis per Symlink als Domäne
  `dev-wiki` mit Arbeitstitel `bloecke`.
- **Identität ist die eigentliche Grenze.** Django-Markdowns haben selten
  Block-IDs; abgeleitete IDs aus Überschriften (`auto-…`) brechen beim
  Umbenennen. Das Wiki vergibt stabile IDs, Django arbeitet mit Pfaden und
  ORM-Schlüsseln.
- Metadaten sind in Django überwiegend nicht in den Dateien, sondern in
  Modellen. Das Wiki sieht sie daher nicht.
- Die Dateiebene ist ein tragfähiger gemeinsamer Nenner: Beide Werkzeuge
  verstehen Markdown in Domänenordnern ohne Konvertierung.

<a id="options"></a>
## Optionen [options]

**A – Wiki in Django integrieren.** Netzansicht und Blockmodell werden als
Django-App nachgebaut, Speicherung im ORM. Vorteil: ein System, Anmeldung und
Betrieb vorhanden. Nachteil: Das neue Modell erbt die Komplexität und die
mehrfachen Speicher; jede Änderung wird teurer.

**B – Neuer Kern, schrittweise Ablösung („Strangler“).** Ein kleiner,
eigenständiger Wissenskern (Blöcke, Metadaten, Relationen, Versionen) wird
Datenwahrheit. Django bleibt vorerst als Oberfläche für Import, InfoSite,
Textwerkstatt und Chat und greift über eine Schnittstelle auf den Kern zu.
Altteile werden einzeln abgeschaltet, sobald der Kern sie ersetzt.

**C – Radikale Neuentwicklung.** Neues Projekt mit eigener Oberfläche;
Django wird eingefroren und nur noch als Steinbruch genutzt. Vorteil: kein
Altballast, klare Architektur. Nachteil: lange Phase ohne Import, Retrieval
und Chat; Gefahr, Bewährtes (Textwerkstatt, Importer, Betrieb) neu zu
verlieren oder doppelt zu bauen.

<a id="recommendation"></a>
## Empfehlung [recommendation]

**Option B mit dem Ergebnis von C:** einen neuen, kleinen Kern bauen, der im
Endzustand einer Neuentwicklung entspricht, aber von Anfang an mit den
vorhandenen Daten und Werkzeugen läuft.

Begründung:

- Das Wiki hat gezeigt, dass der Kern klein sein kann. Er gehört nicht in die
  Django-Modelle, sondern in ein eigenes Paket ohne Web-Abhängigkeit.
- Wertvolle Teile der Django-App – Importer, Textwerkstatt-Konzepte
  (Revision, Anker, Vorschlag), Retrieval, `llm_provider`, stackctl-Betrieb –
  lassen sich als Adapter oder Module übernehmen, statt sie neu zu erfinden.
- Jeder Schritt ist für sich nutzbar und umkehrbar; es gibt keine lange
  Phase ohne funktionierendes Werkzeug.
- Altteile verschwinden nicht durch Umbau, sondern durch Nichtmehrbenutzung
  und anschließendes Löschen.

Ob die Oberfläche langfristig Django bleibt oder ein schlanker Server wie im
Wiki genügt, kann spät entschieden werden, weil der Kern davon unabhängig ist.

<a id="fresh-django"></a>
## Variante: frisches Django mit Wiki-App [fresh-django]

Geprüft am 2026-11-09: Lässt sich B mit dem Ergebnis von C auch erreichen,
wenn direkt ein neues Django-Projekt aufgesetzt und das Wiki als eigene
Django-App (eigenes pip-Paket) nachgebaut wird? **Ja – unter einer Bedingung:
Der Kern bleibt innerhalb des Pakets frei von Django.**

Befund am Code:

- Der Kern (`wiki_workspace.py`, `wiki_documents.py`, Teile von
  `doc_viewer.py`) umfasst rund 500 Zeilen und nutzt nur Standardbibliothek
  und PyYAML. Er lässt sich unverändert in ein Unterpaket übernehmen.
- Die Web-Schicht (`wiki_web.py`, 133 Zeilen) ist dünn. Ihre Eigenbauten –
  Host-Prüfung, Token, Sicherheitsheader, Asset-Auslieferung – ersetzt Django
  durch `ALLOWED_HOSTS`, CSRF, die eingebaute CSP-Middleware (Django 6) und
  `staticfiles`.
- Die JS-Dateien kennen feste Pfade (`/workspace/api`, `/assets/`). Diese
  werden durch Template-Angaben ersetzt; die Oberfläche bleibt gleich.
- Django ergänzt, was dem Wiki fehlt: Anmeldung, Admin, Systemprüfungen der
  Konfiguration, Testrahmen und Migrationen für spätere abgeleitete Indizes.

Aufbau in drei Paketen:

- **`wissenswiki-core`** (Repo `~/dev_flow/wissenswiki-core`, Modul
  `wissenswiki_core`): Kern, Konfigurations-Registry, JSON-API, HTML-Seiten,
  CSS/JS und eine schlanke Web-App (`wissenswiki serve`, nur
  Standardbibliothek). Ohne Django installierbar und nutzbar.
- **`wissenswiki-django`** (Repo `~/dev_flow/wissenswiki-django`, Modul
  `wissenswiki`): dünne Schicht für Login, CSRF, URLs und
  `settings.WISSENSWIKI`; macht das Wiki per `INSTALLED_APPS` in jeder
  Django-Site verfügbar. Seiten und Statics kommen aus dem Core, die
  Oberfläche existiert also nur einmal. Konfigurationsfehler meldet eine
  Systemprüfung statt stiller Ersatzwerte.
- **Neues Host-Projekt** (Repo `~/dev_flow/ki-knowledge-next`, Arbeitstitel):
  frisches Django, bindet die App ein. Weitere Fachbereiche folgen als eigene
  Apps (Import, Versionen, KI-Vorschläge, Ausgabe), jeweils mit Kern und
  dünner Django-Schicht.
- **Strangler bleibt möglich:** Die bestehende Django-App kann dieselbe
  Wiki-App über `INSTALLED_APPS` einbinden; beide Projekte nutzen so denselben
  Code und dieselben Dateien.

Grenzen und Regeln:

- Dateien bleiben die Wahrheit. ORM-Modelle nur für Abgeleitetes (Index,
  Nutzer, Einstellungen), nie als zweite Kopie der Blöcke.
- Keine Übernahme alter Module per Kopie; Übernahme nur als neue App mit Test.
- Der alte `doc_viewer` bleibt bis zur Ablösung unverändert in Betrieb.
- Konfiguration über ki-core und Betrieb über stackctl werden im
  Host-Projekt nachgezogen, nicht im Paket.

Damit ändert sich der [Migrationspfad](#migration-path): Schritt 2 („Kern
herauslösen“) und 7 („Oberfläche entscheiden“) sind vorweggenommen –
Oberfläche ist Django, der Kern liegt in `wissenswiki-core`.

Stand der Umsetzung (2026-11-09): Alle drei Repos sind angelegt, aber noch nicht
unter git.
- Bereits portiert: Arbeitsraum, beide Netzansichten, Einstellungsseite, JSON-API
  mit CSRF und Domänen-Erkennung.
- Absicherung: Unit-Tests und Browsertests (Django und schlanke Web-App) laufen
  grün.
- Noch offen:
  - lesende Dokumentationsansicht
  - ki-core-Konfiguration
  - stackctl-Spec
  - Einbindung in die alte App
  - die Apps für Versionen und KI-Vorschläge

<a id="target-architecture"></a>
## Zielarchitektur [target-architecture]

```text
Quellen ──▶ Import-Adapter ──▶ Wissenskern ◀── KI-Dienste (llm_provider)
(md, pdf, epub, jira)          │  Blöcke, Metadaten,      │
                               │  Relationen, Versionen   ▼
                               ├──▶ Suche / Retrieval / Chat
                               ├──▶ Ausgabe (InfoSite, Export)
                               └──▶ Oberflächen (Netz, Editor, Django)
```

- **Wissenskern** (`ki_knowledge/core/` o. ä.): Datenwahrheit sind Dateien je
  Domäne – ein Block als Markdown mit YAML-Header (stabile ID, Titel,
  Herkunft, Metadaten, Teile), Relationen als typisierte gerichtete Kanten.
  Ein Index (SQLite) ist nur abgeleitet und jederzeit neu erzeugbar.
- **Metadaten-Schema je Domäne:** sinnvolle Vorgaben, erweiterbar;
  Relationstypen pro Domäne konfigurierbar statt fest auf sieben Typen.
- **Versionierung:** jede Änderung als Revision mit Herkunft (Mensch, Import,
  KI); naheliegend über git im Domänenordner oder ein Append-Log neben den
  Dateien. Die Textwerkstatt-Revisionen dienen als Vorlage.
- **KI-Bearbeitung** als Vorschlag, nie als stilles Überschreiben: KI erzeugt
  Proposals, ein Mensch übernimmt. Chat ausschließlich über
  `ki_knowledge.llm_provider`; Embeddings weiter über Ollama.
- **Import-Adapter** erzeugen Blöcke mit Herkunft und stabilen IDs. Jira ist
  ein Adapter unter mehreren.
- **Ausgabe:** InfoSite wird ein Ausgabe-Adapter, der aus Blöcken Seiten
  erzeugt, und schreibt nie in Quellen.
- **Konfiguration und Betrieb** bleiben bei ki-core und stackctl.

<a id="migration-path"></a>
## Migrationspfad [migration-path]

1. **Brücke nutzen (jetzt).** Beide Werkzeuge auf beiden Datenbasen
   ausprobieren; Erfahrungen festhalten. Keine Datenmigration.
2. **Kern herauslösen.** Blockmodell, Dateispeicher und Relationen aus
   `wiki_documents.py`/`wiki_*` in ein eigenes, getestetes Paket ohne
   HTTP-Bezug verschieben. Das Wiki nutzt danach nur noch den Kern.
3. **Stabile IDs für Bestandsdaten.** Ein Werkzeug schreibt einmalig IDs in
   Django-Markdowns (Vorschau, dann bestätigen), damit `auto-`-IDs entfallen.
4. **Versionen und Vorschläge im Kern.** Revisionen und KI-Proposals nach dem
   Vorbild der Textwerkstatt; erste KI-Funktion im Wiki („Block
   umformulieren“, „Beziehung vorschlagen“).
5. **Django an den Kern anschließen.** Textwerkstatt, InfoSite und Retrieval
   lesen Blöcke über den Kern; neue Funktionen entstehen nur noch dort.
6. **Altteile abschalten** gemäß [Rückbau](#legacy-exit).
7. **Oberfläche entscheiden:** Django behalten oder durch den schlanken
   Server ersetzen, je nach Bedarf an Anmeldung, Mehrbenutzerbetrieb und Admin.

<a id="legacy-exit"></a>
## Rückbau von Altteilen [legacy-exit]

Ein Teil wird entfernt, wenn alle Bedingungen erfüllt sind: Ersatz im Kern
vorhanden, keine Nutzung in den letzten Wochen, Daten exportiert oder
überführt, Tests angepasst. Kandidaten in dieser Reihenfolge:

- Kompatibilitätsfassaden (`django_site/services.py`,
  `views_data_sources.py`) nach Umstellung der Aufrufer;
- Jira-spezifische Workflows, sobald der Jira-Import-Adapter läuft;
- doppelte Blockspeicher (`block_store.db`, Teile des KnowledgeStore), sobald
  der Kern-Index sie ersetzt;
- Wagtail, Widgetkit und verteilte Synchronisation nach gesonderter Prüfung
  ihres tatsächlichen Nutzens.

<a id="risks-and-decisions"></a>
## Risiken und offene Entscheidungen [risks-and-decisions]

Risiken:

- Zwei Systeme schreiben gleichzeitig in dieselben Dateien (Brücke,
  Übergangsphase). Abhilfe: Sperrdatei des Kerns respektieren, KI-Ausgaben
  nur in Ausgabeordner.
- Abgeleitete IDs machen Beziehungen bei Umbenennungen unauflösbar.
- Der neue Kern wächst wieder zu groß. Abhilfe: Kern ohne Web, ohne KI,
  ohne Import; alles andere als Adapter.
- Wissen über bewährte Django-Lösungen geht verloren, wenn zu früh gelöscht
  wird.

Offene Entscheidungen:

- Versionierung über git oder eigenes Revisionsformat?
- Ein Block je Datei oder mehrere Blöcke je Dokument als gleichwertige Form?
- Verhältnis von Textblock und Wissensblock (siehe
  [TEXT-AND-KNOWLEDGE-BLOCKS.md](TEXT-AND-KNOWLEDGE-BLOCKS.md)).
- Mehrbenutzerbetrieb und Anmeldung: nötig, und wenn ja, wann?
- Langfristige Oberfläche: Django oder schlanker Server?

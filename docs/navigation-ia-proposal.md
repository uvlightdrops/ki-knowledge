# Navigation-IA-Neuordnung — Vorschlag

Status: **Entwurf zur Diskussion** (noch nicht umgesetzt)
Datum: 2026-09-03

## 1. Ausgangslage: Ist-Zustand der Navigation

`base.html` zeigt aktuell 6 gleichrangige Top-Level-Einträge plus eine
separate "Quicklinks"-Leiste mit 7 weiteren Links. Insgesamt gibt es
~40 registrierte URL-Routen (`urls.py`), die sich grob so gruppieren:

| Heutiger Nav-Eintrag | Ziel-URL | Enthält (Views/Routen) |
|---|---|---|
| Dashboard | `/` | Domain-Übersicht, Task-Monitor |
| 📚 Infosite | `/infosite/dashboard/` | Projekte, Discovery, Import-Jobs, AI-Refine, Preview |
| Data Sources | `/data-sources/` | Markdown/PDF/OWL/Jira-Übersicht |
| 🗂️ CMS Catalog | `/cms/data-sources/` | Wagtail-Spiegel (read-only, Schritt 3+6) |
| Knowledge | `/knowledge/` | Knowledge-API, Sources, Records, Artifacts, Jobs |
| Semantic | `/semantic/` | Semantic Terms, Domain-Analyse |
| ⚙️ Settings | `/settings/` | nur "Layout"-Untermenü — **keine Config/YAML-Edit-Fläche** |
| *(Quicklinks, ohne eigenen Nav-Slot)* | `/jira/*` (6 Routen), `/pdf-import/*` (4 Routen), `/ollama-chat/`, `/prompt-backlog/`, `/support-chat/`, `/workspace/` | Jira-Spezialansichten, PDF-Batch-Jobs, Chat, Backlog |

**Probleme, die das rechtfertigt, was Sie ansprechen:**
- Jira-Funktionen (6 Routen: domain-terms, exclusions, domain-analysis,
  hybrid-search, graph-explorer, daily-timeline, support-chat) hängen
  ohne Nav-Eintrag im Quicklink-Bereich — de facto eine unsichtbare siebte
  Sektion.
- "Data Sources" (Discovery/Import) und "Knowledge" (Records/Artifacts,
  also das *Ergebnis* der Extraktion) sind beide vorhanden, aber die
  Grenze zwischen "Rohdaten" und "verarbeitetes Wissen" ist in der Nav
  nicht sichtbar — genau die Trennung, die Sie mit "Data sources area" vs.
  "Internal knowledge" ansprechen.
- Es gibt keine Fläche für Config/YAML — `ki_core.Config` (aus ki-core)
  lädt `ki.yaml`/`config.yaml`/`creds.yaml`, aber es gibt aktuell **keine
  GUI**, um das anzuzeigen oder zu bearbeiten. Config-Änderungen laufen
  heute nur über manuelles YAML-Editieren + Server-Neustart.
- "Infosite" (Markdown-Präsentationen) ist heute ihre eigene Top-Level-
  Sektion, obwohl sie konzeptionell nur *ein* "Output"-Format unter
  mehreren ist (Sie erwähnen Quiz als Beispiel für ein weiteres Format).

## 2. Vorgeschlagene neue IA (4 Hauptbereiche + Dashboard + Settings)

**Entscheidungen (bestätigt):**
- Reihenfolge in der Nav: `Dashboard | Data Sources | Internal Knowledge |
  Info Output | CMS Catalog | Settings` (Data Sources links, Internal
  Knowledge zentral, Info Output rechts davon, Settings ganz rechts als
  Systembereich; CMS Catalog bleibt eigenständig, direkt vor Settings).
- Settings-Formulare zeigen Secrets (API-Keys/Tokens) **nur als
  "gesetzt"/"nicht gesetzt"**, nie im Klartext.
- `/output/quiz/` wird zunächst nur als **Platzhalter-Seite** angelegt
  (kein Datenmodell, kein Generator) — Konzept folgt später.
- Settings-Formulare sind in Phase 1 **read-only** (Anzeige der aktiven
  Config-Werte); Schreibzugriff mit Backup+Diff-Vorschau folgt als
  separate Phase 2, erst nach Rückmeldung.
- ~~Alte URLs bekommen 301-Redirects~~ — **Revidiert**: Ein-User-
  Development ohne Bookmarks/externe Links, daher **harter Cutover ohne
  Redirects** (siehe Abschnitt 5).

```
🏠 Dashboard
📥 Data Sources       — alles was Rohdaten reinbringt (Markdown, PDF, OWL, Jira)
🧠 Internal Knowledge — alles was Rohdaten zu Wissen verarbeitet (Semantic, KI-Workflows)
📤 Info Output        — alles was Wissen nach außen präsentiert (Infosite, künftig Quiz, ...)
🗂️ CMS Catalog        — Wagtail-Editorial-Layer (Schritt 3+6), bleibt separat
⚙️ Settings          — Konfiguration anzeigen (read-only Phase 1), später editierbar
```

### 2.1 ⚙️ Settings (neu, umfassend)

Ziel: **Config-Werte aus `ki_core.Config` sichtbar und editierbar machen**,
gruppiert nach den bestehenden YAML-Sektionen (`ki`, `ollama`, `openai`,
`knowledge`, `infosite`, `jira`, `http`, `kicli`, `context`, `diff`):

| Unterseite | Inhalt |
|---|---|
| `/settings/` | Übersichts-Dashboard: welche Config-Datei ist aktiv (Pfad), welche Sektionen sind gesetzt/leer |
| `/settings/llm/` | KI-Server, Ollama, OpenAI (Base-URL, Modell) — **API-Keys maskiert**, kommen separat aus `creds.yaml` |
| `/settings/knowledge/` | `knowledge_data_root`, Cache/Graph-DB-Pfade, Embed-Modell |
| `/settings/infosite/` | `infosite_enabled`, `infosite_title`, `infosite_output_base_dir`, `infosite_domain` |
| `/settings/jira/` | Jira-URL/Username (Token maskiert) |
| `/settings/http-context-diff/` | Request-Timeout, Context-/Diff-Engine-Parameter |
| `/settings/layout/` | *(bestehend, bleibt)* GUI-Panel-Layout |
| `/settings/raw-yaml/` | Rohansicht der aktiven YAML-Datei (read-only oder mit Diff-Vorschau vor dem Schreiben) |

**Wichtige Design-Entscheidung, die ich vorher klären möchte** (siehe
Abschnitt 4): Soll das Formular **direkt in die YAML-Datei zurückschreiben**
(mit Backup + Diff-Anzeige vor dem Speichern), oder zunächst nur
**read-only** sein, bis wir Validierung/Locking/Mehrbenutzer-Fragen geklärt
haben? Ich empfehle read-only zuerst, dann Schreibzugriff als Schritt 2.

### 2.2 📥 Data Sources (konsolidiert)

Bündelt alles, was *Rohdaten hereinbringt*, unabhängig vom Format:

```
/data-sources/                     Übersicht (bisheriges data_sources_view)
  /data-sources/markdown/          Discovery + Import-Control (heutiges infosite import_control)
  /data-sources/pdf/               PDF-Batch-Jobs (heutiges /pdf-import/*)
  /data-sources/owl/                OWL-Ontologie-Import
  /data-sources/jira/               Jira-Import + Domain-Terms + Exclusions
                                     (heutige /jira/domain-terms/, /jira/exclusions/)
  /data-sources/jobs/               Vereinheitlichte Job-Historie über alle Importquellen
                                     (heutige /jobs/, /pdf-import/, Import-Jobs aus infosite)
```

### 2.3 📤 Info Output (neu benannt/erweitert, ersetzt "📚 Infosite")

```
/output/                          Übersicht: welche Ausgabeformate existieren
  /output/infosite/                heutiges /infosite/dashboard/ (Projekte, Generate, AI-Refine)
  /output/quiz/                    (Platzhalter für zukünftiges Quiz-Format)
```

### 2.4 🧠 Internal Knowledge (neu, ersetzt "Knowledge" + "Semantic")

Bündelt die *Verarbeitung* (nicht die Rohdaten, nicht die Ausgabe):

```
/knowledge/                       Übersicht (Records, Artifacts, Sources — heutiges knowledge_landing_view)
  /knowledge/semantic/             Semantic Terms, Domain-Analyse, Hybrid-Search, Graph-Explorer
                                     (heutiges /semantic/, /semantic/terms/, /jira/hybrid-search/,
                                     /jira/graph-explorer/, /jira/daily-timeline/)
  /knowledge/pipeline/             KI-Workflow: Knowledge-Extraction-Jobs, Pipeline-Runner-Status
                                     (heutiges knowledge_extraction_jobs, run_knowledge_extraction)
  /knowledge/chat/                 Support-Chat, Ollama-Chat, Prompt-Backlog
                                     (heutiges /support-chat/, /ollama-chat/, /prompt-backlog/,
                                     /jira/support-chat/)
  /knowledge/records/               Records-Browser (heutiges /records/)
  /knowledge/artifacts/             Artifacts-Browser (heutiges /artifacts/)
```

### 2.5 🗂️ CMS Catalog (unverändert)

Bleibt separat, da es explizit der *editoriale Wagtail-Spiegel* ist
(Schritt 3+6) — konzeptionell eine Beobachtungs-/Kuratierungs-Ebene über
allen anderen Bereichen, kein eigener Datenfluss.

## 3. URL-Mapping

**Revidiert nach Rückmeldung**: Da es sich um Ein-User-Development ohne
externe Bookmarks handelt, wurde auf 301-Redirects verzichtet — **harter
Cutover** aller Pfade in einem Zug (siehe Abschnitt 5 für die finale
Struktur). Beispiel: `/jira/domain-terms/` → `/data-sources/jira/domain-terms/`
(alter Pfad existiert nicht mehr, kein Redirect).

## 4. Entscheidungen (vormals offene Fragen)

1. ✅ Struktur bestätigt (siehe Reihenfolge in Abschnitt 2), CMS Catalog bleibt separat.
2. ✅ Settings-Formulare sind Phase 1 read-only; Schreibzugriff (Backup+Diff) folgt später.
3. ✅ Secrets (API-Keys/Tokens) werden nur als "gesetzt"/"nicht gesetzt" angezeigt, nie im Klartext.
4. ✅ Umsetzungsreihenfolge: siehe Abschnitt 5 (Nav zuerst, dann Settings read-only, dann URL-Reorganisation je Bereich).
5. ✅ **Revidiert**: keine 301-Redirects, sondern harter Cutover aller URLs
   (Ein-User-Development, keine Bookmarks) — abgeschlossen.
6. ✅ `/output/quiz/` ist zunächst nur ein Platzhalter, kein Datenmodell/Generator.

## 5. Vorgeschlagene Umsetzungsreihenfolge (nach Rückmeldung)

1. ✅ Neue Top-Nav-Struktur in `base.html` (6 Haupteinträge, aktiver
   Zustand hervorgehoben), CSS angepasst.
2. ✅ Neue `/settings/config/`-Seite (read-only Config-Anzeige).
3. ✅ Dynamisches Submenü: Die Zeile unter den Hauptpunkten
   (`.nav-quicklinks`) ist keine statische globale Linkliste mehr, sondern
   zeigt je aktivem Hauptbereich sein eigenes Submenü. Umgesetzt über
   einen neuen Context-Prozessor `ki_knowledge/django_site/context_processors.py:nav_areas`,
   der anhand des längsten passenden URL-Präfixes (`NAV_AREAS`) den
   aktiven Bereich bestimmt und dessen Submenü-Einträge bereitstellt.
   `base.html` rendert daraus sowohl die `active`-Markierung im Hauptnav
   als auch die dynamische Submenü-Zeile. Placeholder-Einträge ohne URL
   (z. B. "Quiz (geplant)") werden als deaktiviertes `<span>` statt Link
   gerendert.
4. ✅ **URL-Reorganisation abgeschlossen** (harter Cutover, keine
   Redirects — Ein-User-Development-Projekt ohne Bookmarks). Alle
   View-Namen (`name=` in `urls.py`) blieben unverändert, nur die
   URL-*Pfade* wurden verschoben; dadurch mussten `reverse()`/`{% url %}`-
   Aufrufe in Python/Templates nicht angefasst werden. Neue Struktur:
   - `/data-sources/` — `workspace/`, `sources/`, `sources/<id>/`, `pdf/`
     (+ `report/`, `jobs/<id>/`, `jobs.json`), `jira/domain-terms/`,
     `jira/exclusions/`, `import/`
   - `/knowledge/` — `api/`, `records/`, `artifacts/`, `generate/`,
     `jobs/` (+ `<id>/`), `graphs/<id>/` (+ `3d/`), `prompt-backlog/`,
     `chat/support/`, `chat/jira-support/`, `chat/ollama/`,
     `semantic/` (+ `terms/`, `terms/<id>/`, `domain-analysis/`,
     `hybrid-search/`, `graph-explorer/`, `daily-timeline/`)
   - `/output/` (neu, ersetzt `/infosite/` als Top-Level-Präfix) —
     `/output/` (neue Übersichtsseite `output_landing_view`),
     `/output/quiz/` (Platzhalter, `output_quiz_view`),
     `/output/infosite/...` (unverändertes `infosite_urls.py`-Include,
     nutzt durchgehend `{% url 'infosite:...' %}`, daher ohne
     Template-Änderungen verschiebbar)
   - `/cms/`, `/cms-admin/`, `/cms-documents/`, `/settings/` — unverändert
   - Alle hartcodierten `href="/…"`-Links in Templates (`data_sources.html`,
     `dashboard.html`, `semantic_landing.html`, `prompt_backlog.html`,
     `knowledge_landing.html`, `sources.html`, `ollama_chat.html`,
     `pdf_import_jobs.html`) sowie 2 hartcodierte Links in
     `wagtail_cms`-Templates auf die neuen Pfade aktualisiert.
   - `NAV_AREAS` in `context_processors.py` auf die neuen (jetzt sauber
     hierarchischen) Präfixe vereinfacht.
5. ✅ Tests/Smoke-Checks: `manage.py check`, `reverse()` für alle
   Parametrisierten Routen, `pytest tests/` (95 passed / 1 bekannter
   Vorbestand), Live-Smoke-Test aller neuen Seiten via Django-Test-Client.

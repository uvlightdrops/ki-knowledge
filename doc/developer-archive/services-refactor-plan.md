# Services-Modularisierung: Plan und Phase 1

## Problem

`ki_knowledge/django_site/services.py` ist zu groß und verbindet zu viele Konzepte:

- Domain-/Pfad-Setup
- Cache- und Summary-Logik
- Source-Imports und PDF/Markdown Handling
- Semantic jobs und Cancellations
- Knowledge graph und artifact erzeugung
- UI-Orchestrierung

## Ziel

Die Verteilung soll sauberer werden, ohne das Projekt in einem großen Bruch zu verändern.

## Aufteilungsplan

### Phase 1: Domain-/Pfad-Logik extrahieren

Ziel:
- Domain-Root-Klassen und Pfad-Resolver in eigenes Modul verschieben
- Cache-Keys und caching helpers trennen
- `services.py` als Übergang fortführen

Erledigt:
- `ki_knowledge/django_site/domain_paths.py` angelegt
- relevante Funktionen aus `services.py` in neues Modul verschoben bzw. dort als Fassade vorbereitet

### Phase 2: Source-Import und preprocessing trennen

Ziel:
- Datensammlungen aus `services.py` in `ki_knowledge/django_site/source_imports.py` oder `ki_knowledge/services/...`
- Import, Validation, Discovery, PDF/CSV-Vorbereitung isolieren
- `services.py` nur noch als Adapter / facade

### Phase 3: Semantic jobs und Domain-Stats trennen

Ziel:
- Jobs-Logik, cancellation, retry-status, summary stats in separate Module
- Daten-Overview und Purge-Mechaniken isolieren

Erledigt:
- `ki_knowledge/django_site/knowledge_summary.py` angelegt
- domain summary, reset/clear logic, semantic job queries dort ausgelagert

### Phase 4: Jira-Workflow und Dashboard-Task-Orchestrierung trennen

Ziel:
- Jira-Import-, Graph- und Domain-Analyse-Pipelines separat halten
- Dashboard-Tasks (domain switch, kafka/semantic actions) aus dem Sammelmodul herausziehen

Erledigt:
- `ki_knowledge/django_site/jira_workflow.py` angelegt
- Jira-CSV/Cache/Domain-Analysen als eigenständige fachliche Gruppe organisiert

## Guardrails

- Keine feature-breaking Umbauten im selben Schritt wie UI-Änderungen
- Schrittweise import-stable Fassade in `services.py` behalten
- Nach jeder Phase: `python manage.py check`
- Erst danach weitere Module refactoren

## Status

- Phase 1: umgesetzt — `ki_knowledge/django_site/domain_paths.py`
- Phase 2: umgesetzt — `ki_knowledge/django_site/source_workflow.py`
- Phase 3: umgesetzt — `ki_knowledge/django_site/knowledge_summary.py`
- Phase 4: in Arbeit — `ki_knowledge/django_site/jira_workflow.py`

# Feature Inventory and Localization Status

## Ziel

Diese Übersicht zeigt, welche Features im Projekt bereits klar im Dateisystem lokalisiert sind und welche noch in übergeordneten God-Modules wie `ki_knowledge/django_site/services.py` durcheinanderlaufen.

## Status-Logik

- Klar lokalisiert: Das Feature hat einen eindeutigen Home-Pfad im Code.
- Teilweise gemischt: Die Logik ist verteilt; die primäre Orchestrierung läuft noch in einem Sammelmodul.
- Legacy / unscharf: Die Benennung oder der Routing-Kontext ist veraltet und sollte bereinigt werden.

## Features und Code-Stand

| Feature | Status | Klar lokalisierbar | Hinweise |
|---|---|---|---|
| Enduser Infosite Generator | Klar lokalisiert | `ki_knowledge/services/generator.py`, `ki_knowledge/django_site/templates/infosite/*`, `ki_knowledge/django_site/static/infosite/css/*` | Generierung und Styling sind weitgehend getrennt, sauber erkennbar. |
| Source discovery und Markdown-Import | Teilweise gemischt | `ki_knowledge/services/discovery.py`, `ki_knowledge/services/import_runner.py`, `ki_knowledge/ui/knowledge_api_client.py`, `ki_knowledge/django_site/services.py` | Import-Workflow und UI-Orchestrierung sind noch nicht vollständig getrennt. |
| Domain-/Pfadauflösung | Teilweise klar, Phase 1 begonnen | `ki_knowledge/config_runtime.py`, `ki_knowledge/django_site/domain_paths.py` | Das zentrale Pfad- und Domain-Konzept wurde in ein eigenes Modul ausgegliedert; bisherige Übergangsschicht bleibt in `services.py`. |
| Semantic Layer / Terms / Jobs | Teilweise klar | `ki_knowledge/integrations/semantic_terms.py`, `ki_knowledge/django_site/views.py`, `ki_knowledge/django_site/templates/kicli_django/jobs*.html` | Job-Management und Semantik sind überwiegend klar, aber die orchestrierende Sicht bleibt noch in `services.py`. |
| Knowledge graph + artifacts | Teilweise gemischt | `ki_knowledge/integrations/knowledge_graph.py`, `ki_knowledge/knowledge/generate.py`, `ki_knowledge/integrations/knowledge_store.py`, `ki_knowledge/django_site/services.py` | Repräsentation und Generierung sind klar, die Gesamtkoordination ist noch breit verteilt. |
| Knowledge API / overview / purge | Klar lokalisiert | `ki_knowledge/django_site/views.py`, `ki_knowledge/django_site/templates/kicli_django/knowledge_api.html` | Der fachliche Workflow ist gut sichtbar; einzelne backend-Details bleiben noch im Sammelmodul. |
| Wagtail workflow / output workflow | Klar konzeptionell, aber noch nicht vollständig getrennt | `ki_knowledge/wagtail_cms/*`, `doc/source-workspace-and-workflow-concept.md` | Das Konzept ist dokumentiert; die technische Trennung im UI/Code ist besser geworden, aber noch nicht überall vollständig ausgeprägt. |
| Data Sources / Workspace | Klar konzeptionell, UI noch im Fluss | `ki_knowledge/django_site/views.py`, templates under `ki_knowledge/django_site/templates/`, `doc/source-workspace-and-workflow-concept.md` | Der Begriff Workspace ist nun als Vorbereitungs-/Staging-Konzept definiert, aber die UI-Teile sind noch nicht überall konsistent. |
| Jobs overview / cancellation | Klar lokalisiert | `ki_knowledge/django_site/templates/kicli_django/jobs.html`, `jobs_rows_fragment.html`, `job_detail.html`, `ki_knowledge/integrations/semantic_terms.py` | Die Anzeige und der Ablauf sind sichtbar; der bulk-select Bug wurde behoben. |

## Wo die Verwirrung noch sitzt

Folgende Bereiche sind noch nicht sauber abgegrenzt:

1. `ki_knowledge/django_site/services.py`
   - Das Modul aggregiert zu viele Verantwortlichkeiten.
   - Damit werden Pfadlogik, Domain-Summaries, Jobs, imports und UI-Orchestrierung nicht sauber getrennt.

2. Historische Jira-Namensmuster
   - Einige Begriffe und Legacy-Pfade sind noch in Teilen des Codes erhalten.
   - Diese sind sichtbar, aber nicht mehr im primären UI prominent.

3. Workspace vs. Data Sources vs. Wagtail output workflow
   - Das Konzept ist jetzt dokumentiert, aber das UI darf noch nicht als Mix aus Input-, Processing- und Output-Workflow interpretiert werden.

## Empfohlener Refactor-Zielzustand

- `django_site/services.py` bleibt als Übergangsfassade erhalten.
- Neue Module übernehmen jeweils ein Thema:
  - Domain/Path/Cache
  - Source import and preprocessing
  - Semantic jobs and cancellation
  - Knowledge summary and purge logic
  - Output generation / artifact logic
- UI-Views import weiterhin aus der Fassade, damit keine Seiten umgehend alle Imports ändern müssen.

## Phase 1 + 2 Status

Phase 1 wurde begonnen mit:

- Neuer Modulstart: `ki_knowledge/django_site/domain_paths.py`
- Extraktion der Domain-/Pfad- und Cache-Logik aus dem Sammelmodul
- `ki_knowledge/django_site/services.py` nutzt nun diese Funktionen als zentrale Übergangsschicht

Phase 2 wurde erweitert mit:

- `ki_knowledge/django_site/source_workflow.py`
- Auslagerung von discovery / workspace / markdown-PDF-Import / ontology-import
- `services.py` nutzt die neue Modul-Fassade und bleibt kompatibel

Damit ist die Trennung nun bereits auf zwei Kernbereiche erweitert: Domain-Handling und Source-Workflow, ohne das gesamte System in einem Rutsch zu refaktorisieren.

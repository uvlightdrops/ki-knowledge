# Views module split

## Goal

The Django views layer had grown into a single monolithic `ki_knowledge/django_site/views.py` file that mixed:

- shared request helpers
- dashboard and navigation logic
- settings and layout builder logic
- data-source import workflows
- knowledge and semantic workflows
- output-page logic

This made it harder to reason about the app and easier to introduce accidental cross-coupling.

## Current structure

The app now uses a split layout with a thin compatibility facade:

- `ki_knowledge/django_site/views.py`
  - compatibility façade only
  - re-exports the canonical view functions for existing URL imports and legacy module references
- `ki_knowledge/django_site/views_common.py`
  - shared request/helpers, domain detection, dashboard persistence, widget layout helpers
- `ki_knowledge/django_site/views_dashboard.py`
  - main dashboard, monitoring, builder, settings overview and layout pages
- `ki_knowledge/django_site/views_data_sources.py`
  - source ingestion, source browser, import workflows, PDF and Jira source pages
- `ki_knowledge/django_site/views_knowledge.py`
  - knowledge landing, semantic workflows, records/artifacts and API/browser pages

## Why this split

This keeps the responsibilities aligned with the app’s functional areas instead of one giant view file. It also makes the builder and widget lifecycle easier to evolve without touching unrelated import or semantic logic.

## Compatibility strategy

The original `views.py` file remains importable for any existing reverse/URL or code references. It now acts as a compatibility wrapper to avoid breaking the rest of the project during the migration period.

## Future directions

The next cleanup step would be to split the remaining larger domain-specific files even further, especially if the knowledge/semantic and data-source modules continue to grow. The current split is a practical boundary: shared logic, dashboard/settings, source workflow, and knowledge workflow.

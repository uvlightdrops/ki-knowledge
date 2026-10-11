# Widget catalog preview audit

> The leading Data Sources interaction model is
> [Source Workspace and Workflow Concept](../doc/source-workspace-and-workflow-concept.md).
> This audit documents current renderers, not a requirement to retain every
> existing intake widget as an independent view.

## Contract and implementation

The canonical registry currently contains **45 widgets**. The catalog previously
used shared adapter keys, so unrelated widgets could show the same table or
counts, and adapters queried the hardcoded `default` domain. Catalog rendering
now uses the actual widget fragment handlers, not those runtime data adapters.

`build_widget_preview_payload(widget_ids=..., active_domain=...)` creates a
single bounded example context for the selected domain. It performs no database
queries, directory discovery, configuration probing, OCR probing, or remote
master requests. Counts, dates, projects, source files, paths, nodes, and URLs
are **sample data**, not measurements of that domain. Changing domains changes
the domain context and highlights, not the example counts.

The catalog resolves an explicit query domain, then the existing selected
session domain, then `KNOWLEDGE_DEFAULT_DOMAIN` (or the normal `default` name
when none is configured). It deliberately does not use the normal page helper,
which sends automatic distributed heartbeats and mutates the session. Domain
selection in this read-only page does not persist a new session selection.
The catalog-specific request context also avoids default-domain filesystem
discovery in the global header's context processor.

The payload includes canonical identity, label, description, area, category,
default width/height, `active_domain`, `preview_mode="sample"`, `readonly=true`,
`status`, `note`, and `body_html`. Legacy `stats`, `rows`, and `links` fields are
empty; they are not the catalog's rendering contract anymore. The single-widget
helper and `render_widget_preview` also require an explicit active domain.
Batch calls reuse one context. Renderer errors propagate rather than being
silently converted into empty or misleading previews.

There are **43 sample previews using real renderers/templates** and **two
planned Quiz placeholders**. Every registered widget has a real renderer;
planned Quiz is explicitly the only feature placeholder.

## Read-only rendering and styling

The browser renders the real body using the package's standalone catalog
stylesheet; it does not require the host base theme or Infosite dashboard CSS.
It displays the sample/read-only hint immediately under the preview heading,
the configured scope/status label, any widget-specific limitation note, and an
expandable **read-only rendered HTML** listing.
The listing is the sanitized preview fragment, not an actionable original
fragment. Sizes in the catalog are registry metadata, not a grid-placement
simulation.

Before serialization, the reusable `widgetkit_django.preview` visual-markup
allowlist removes scripts, resources,
event handlers, IDs, integration/data attributes, hidden form values,
navigation targets, form targets, and field names. Forms become inert visual
groups; native controls are disabled; links have no destinations. Only a small
set of static layout CSS declarations is retained. The preview body is also
`inert` and has a CSS pointer-events fallback. The surrounding metadata and
source listing remain selectable/accessible; the inert sample itself is not
an interactive accessibility surface.

Metadata and source markup are assigned with DOM `textContent`; only sanitized
server-generated `body_html` is assigned as HTML. Django `json_script` protects
the serialized payload. Preview fragments do not fetch resources or bind
application actions. The catalog overrides the optional base HTMX script
block, so it does not require the external HTMX CDN. Other pages retain their
existing script inclusion.

Normal `render_widget_data`, dashboard adapter behavior, and shell-builder live
payload behavior remain unchanged. The two shell-builder callers explicitly
use `render_widget_data` rather than the newly offline catalog helper. Existing
inline workspace/config and settings/registry markup was extracted to escaped
shared Jinja fragments without changing its normal-page content.

## Per-widget audit

Paths below are relative to `ki_knowledge/`. `J:` means
`widgetkit_templates/<name>.html`; `D:` means
`django_site/templates/<path>.html`. All actions and navigation in every row
are disabled by the shared preview boundary.

| Canonical widget | Actual shape and reused renderer/template | Implemented preview improvement and honest limit |
| --- | --- | --- |
| `datasources.overview.summary.v1` | J: `datasources_overview_summary`; source, Markdown, OWL counts | Actual summary fragment with two sample sources; no live inventory scan. |
| `datasources.import.quick.v1` | J: `datasources_import_quick`; upload drop zone, image mode, five folder tiles, import-all | Exact upload/import template with five sample folder rows. Bypasses `quick_import_rows`, path resolution and symlink checks; no upload/import handlers. |
| `datasources.sources.discovery.v1` | J: `datasources_sources_discovery`; Markdown/PDF/ontology file counts, imported-source count and browser link | Separates on-disk inventory from imported sources; it no longer repeats the overview widget's same two totals. |
| `datasources.mix.overview.v1` | J: `datasources_mix_overview`; folder, file-kind counts, OCR notice, import button | Exact populated template using sample mixed files. Bypasses `mixed_files_summary`; OCR availability is demonstrative, not detected. |
| `datasources.sources.list.v1` | J: `sources_list` plus package toolbar; filters, shortcuts, source table, provenance, records/artifacts, row actions, pager | Real Markdown/image rows and toolbar presets. No source store query, reimport, generate, or delete action. Shows table mode, not every alternate card/filter state. |
| `datasources.sources.unimported.v1` | J: `sources_unimported`; compact open-file summary and import-all actions | Populated folder counts with new/queued examples. No filesystem discovery or queue creation. |
| `datasources.jobs.recent.v1` | J: `datasources_jobs_recent`; current PDF queue counts, Jira issue count and PDF queue link | Renamed **PDF import status** to match its actual data; it does not claim to display recent job rows. |
| `datasources.markdown.files.v1` | J: `datasources_markdown_files`; bounded Markdown file list, workspace selection links and import forms | Uses the active domain's real discovered Markdown files. Workspace owns filtering and cards/table mode; catalog actions and navigation are inert. |
| `datasources.ontology.overview.v1` | J: `datasources_ontology_overview`; on-disk ontology files and imported OWL sources | Uses domain-scoped file/source counts and links to the OWL source filter; no parsing or import runs in the widget. |
| `knowledge.overview.summary.v1` | J: `knowledge_overview_summary`; sources/records/artifacts | Exact counts fragment with consistent sample knowledge summary; no knowledge store scan. |
| `knowledge.semantic.monitor.v1` | J: `knowledge_semantic_monitor`; active domain and semantic/jobs links | Exact current link-based widget. Does not invent progress/enrichment indicators absent from its renderer. |
| `knowledge.semantic.quick.v1` | J: `knowledge_semantic_quick`; analysis/search/graph navigation | Exact quick-navigation fragment. No semantic extraction jobs or search calls. |
| `knowledge.records.summary.v1` | J: `knowledge_records_summary`; records count and browser link | Actual record summary, not a generic overview; sample count is explicitly labelled at the preview boundary. |
| `knowledge.artifacts.summary.v1` | J: `knowledge_artifacts_summary`; artifacts count and link | Actual artifact summary; no artifact loading/generation. |
| `knowledge.api.browser.v1` | J: `knowledge_api_browser`; domain, source/record counts, API/browser links | Exact API overview fragment for the selected domain. No API request or interactive browser embedding. |
| `knowledge.jobs.recent.v1` | J: `knowledge_jobs_recent`; domain, links, artifact count | Exact current fragment. This widget currently has no actual recent-job table, so the preview does not fabricate one. |
| `knowledge.tools.summary.v1` | J: `knowledge_tools_summary`; labelled tool cards/descriptions | Actual tool-card template with two illustrative links; not a complete live configured tool inventory. |
| `knowledge.graph.overview.v1` | J: `knowledge_graph_overview`; domain, records/sources, graph link | Actual summary fragment, not the graph explorer itself. No graph engine, WebGL, or graph-data loading. |
| `knowledge.semantic.overview.v1` | D: `kicli_django/widgets/knowledge_semantic_overview`; term count and domain | Actual Django template with a sample term count, rather than generic adapter stats. |
| `infooutput.overview.summary.v1` | J: `output_overview`; project/document/approval metrics and recent count | Existing output handler with one sample project/two documents scoped to the selected domain. No generated-document ORM query. |
| `infooutput.infosite.recent.v1` | J: `output_recent_projects`; project titles, working titles, generation states | Existing project transformation and template with a plain sample object. No project queryset or generation action. |
| `infooutput.documents.recent.v1` | J: `output_recent_documents`; project/document paths and review labels | Existing document handler with approved and in-review sample documents. No preview navigation. |
| `infooutput.formats.summary.v1` | J: `output_formats`; format cards, descriptions and availability | Actual formats template; Infosite available and Quiz planned, not generic document totals. |
| `infooutput.domain.overview.v1` | J: `output_domain_overview`; domain review-status table, active highlight | Exact domain statistics table with selected-domain sample row. No cross-domain statistics gathering. |
| `infooutput.generated.documents.v1` | J: `output_recent_documents`; approved/in-review filter in real handler | Reuses the real generated-only filtering path; does not invent a second document UI. |
| `infooutput.infosite.stats.v1` | D: `infosite/widgets/dashboard_stats`; four statistic cards | Actual Infosite stats template. Counts are sample figures, not all-domain database totals. |
| `infooutput.infosite.projects.v1` | D: `infosite/widgets/dashboard_projects`; project table, document totals, status/date, quick actions | Actual full project widget with a plain `documents.all` list, avoiding related-manager queries/N+1. Project/admin/import/refine links are disabled. |
| `infooutput.infosite.workflow.import.v1` | D: `infosite/widgets/dashboard_import_workflow`; instructional ordered list | Exact real instructions; no invented import controls or job execution. |
| `infooutput.infosite.workflow.refine.v1` | D: `infosite/widgets/dashboard_refine_workflow`; instructional ordered list | Exact real instructions; no AI calls or refinement execution. |
| `infooutput.quiz.overview.v1` | D: `kicli_django/widgets/output_quiz_overview`; future-feature explanation | Actual **planned** placeholder. No fake generated questions or working quiz application. |
| `infooutput.quiz.status.v1` | D: `kicli_django/widgets/output_quiz_status`; planned badge, future integrations, domain | Actual **planned** status/template for the selected domain. |
| `admin.domain.management.v1` | J: `admin_domain_management`; scan control, domain/source-folder table and management link | Existing handler supplied explicit sample `domain_states`, avoiding its live service fallback. Scan/delete/management actions disabled. |
| `admin.domain.create.v1` | J: `admin_domain_create`; create-domain form | Actual form appearance with no endpoint, field names, CSRF values, or enabled submit/input. No domain registration. |
| `admin.domain.switcher.v1` | J: `domain_switcher`; active domain chips | Actual switcher with selected-domain sample chip; clicking the preview never changes domain/session. |
| `admin.domain.db.overview.v1` | J: `admin_domain_db_overview`; source/knowledge/project/output table | Actual domain-database table, not the same adapter displayed for unrelated source widgets. No registry/store scan. |
| `admin.system.status.v1` | J: `admin_system_status`; registered domains, data paths, active domain | Exact status fragment with `/sample/` paths, not local filesystem/config disclosure. |
| `admin.workspace.config.v1` | J: `admin_workspace_config`; knowledge path, active domain, config link | Shared escaped extraction of the existing inline renderer. Catalog path is `/sample/knowledge`; normal page keeps its existing `/data/knowledge` value. |
| `admin.sync.overview.v1` | D: `kicli_django/admin_sync_overview`; node/role/enabled/URLs/run/job counts | Actual sync template with a sample host and reserved `.invalid` URLs. No node configuration/remote request. |
| `admin.sync.history.v1` | D: `kicli_django/admin_sync_history`; worker command and direction/status/domain/node/start table | Actual history table with one sample run and selected-domain worker-command text. No subprocess or SyncRun queryset. |
| `admin.sync.catalog.v1` | D: `kicli_django/admin_sync_catalog`; host-only master URL/domain count | Exact host branch with a prebuilt sample catalog; does not fetch a master or imply remote availability. |
| `admin.sync.hosts.v1` | D: `kicli_django/admin_sync_hosts`; master-only host registry table | Exact master branch deliberately demonstrated using a sample master role; note explains this role override. No host discovery. |
| `settings.layout.registry.v1` | J: `settings_layout_registry`; active area, supported areas, builder link | Shared escaped extraction of the existing inline registry fragment; no layout mutation. |
| `settings.config.summary.v1` | J: `settings_config_summary`; provider, knowledge root, Infosite state | Exact template with a named sample provider/root, not host configuration or credentials. |
| `settings.layout.preview.v1` | J: `settings_layout_preview`; active domain/current settings view/builder link | Exact current fragment; does not claim to simulate a saved dashboard or interactive builder state. |

## Aliases and future work

`datasources.domain.overview.v1` and `datasources.domain.switcher.v1` resolve to
the canonical `admin.domain.management.v1` and `admin.domain.switcher.v1`.
`datasources.source.list.v1` resolves to `datasources.sources.list.v1`; the two
IDs represented the same source-browser list and are no longer separate widgets.
These aliases do not appear twice in the catalog. Saved aliases continue to
resolve. The nonfunctional `datasources.ai.summary.v1` registration was retired:
no AI-specific data-source workflow exists to render. Saved placements for this
retired ID are ignored at load time without changing stored layouts.

The default Data Sources page now includes overview, quick import, inventory
discovery, mixed-folder status, Markdown files, ontology status, and PDF import
status. Workspace's Markdown widget is backed by the same live file list used
for selecting/importing files; the duplicate hardcoded file list was removed.
PDF jobs and PDF inventory remain standalone workflow pages: the jobs page
owns queue controls and processing reports, while inventory scans only after an
explicit request. The PDF-status widget links to that queue rather than
duplicating its controls or showing a description-only card there.
Full widget IDs, wider metadata list, area-tab counts, and no redundant category
footer are preserved.

When adding a registry entry, add its real renderer (or an explicitly planned
feature template); the all-registry test will fail on a missing handler. Extend
the bounded sample context instead of introducing a live query.
Future empty/error/multiple-role/card-mode variants can be offered as explicit
sample scenarios, but are not currently selectable. No browser screenshot or
full interactive-page parity is claimed: this is a read-only catalog of the
widgets' current fragments, not their surrounding applications.

## Validation

`tests/test_widget_catalog.py` covers all registry entries, actual handler
parity, explicit status/schema, selected-domain propagation, aliases, shared
context construction, rendering failures, and removal of actionable markup.
Its autouse guard rejects database queries, network connections, live summary
providers, and filesystem-discovery providers.

`tests/test_frontend_assets.py` verifies JSON escaping, local assets, actual-body
selection in Node's fake DOM, inert/read-only markup, text-only metadata/source
insertion, and widget switching. Output-widget and adapter regression tests
remain database-free.

Run with Django initialized **and database access globally guarded**:

```python
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
import django
django.setup()
from django.db.backends.utils import CursorWrapper
def forbidden(*args, **kwargs):
    raise AssertionError("Database access prohibited")
CursorWrapper.execute = forbidden
CursorWrapper.executemany = forbidden
import pytest
raise SystemExit(pytest.main([
    "-q", "tests/test_widget_catalog.py", "tests/test_frontend_assets.py",
    "tests/test_infooutput_widgets.py", "tests/test_widgetkit_adapters.py",
]))
```

Also run `.venv/bin/python manage.py check`. Do not run Django database-marked
pytest tests on the configured application database; this environment does not
provide pytest-django isolation.

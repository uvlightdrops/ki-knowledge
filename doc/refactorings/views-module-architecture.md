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
  - explicit compatibility exports for the source-area views, not implementations
- `ki_knowledge/django_site/views_knowledge.py`
  - knowledge landing, semantic workflows, records/artifacts and API/browser pages

## Why this split

This keeps the responsibilities aligned with the app’s functional areas instead of one giant view file. It also makes the builder and widget lifecycle easier to evolve without touching unrelated import or semantic logic.

## Compatibility strategy

The original `views.py` file remains importable for any existing reverse/URL or code references. It now acts as a compatibility wrapper to avoid breaking the rest of the project during the migration period.

## Future directions

The next cleanup step would be to split the remaining larger domain-specific files even further, especially if the knowledge/semantic and data-source modules continue to grow. The current split is a practical boundary: shared logic, dashboard/settings, source workflow, and knowledge workflow.

## Responsibility split of services and source views (2026-10-28)

The former `services.py` (2,328 lines at the start of this step) and
`views_data_sources.py` (1,977 lines) are now compatibility facades. Existing
callable names, signatures, URL names, decorators, response/context shapes
and data locations remain available. Overridden earlier implementations in
`services.py` were removed, not copied into new modules.

The remaining implementations are grouped under `ki_knowledge/django_site/`:

| Service/adapter module | Responsibility |
|---|---|
| `domain_registry.py` | Registry defaults, domain discovery/create/delete, source scoping and inventory |
| `data_display.py` | Display-only path labels, source references and artifact previews |
| `chat_service.py` | Configured chat calls and conversation Markdown output |
| `prompt_library.py` | Templates, backlog parsing/execution and batch output files |
| `support_chat.py` | Domain-scoped retrieval, index coverage and grounded answers |
| `knowledge_browser.py` | Store access, artifacts, API browsing and graph presentation |
| `pdf_jobs.py` | Queue access, worker startup, job reports and statistics |

Existing focused modules remain authoritative: `source_workflow.py` for
imports/discovery, `jira_workflow.py` for Jira, `knowledge_summary.py` for
summary/reset and semantic queries, `ui_dispatcher.py` for task dispatch,
and `services/domain_paths.py` for filesystem rules. The two historic
domain-default policies remain distinct. Inventory dependencies on prompt
directories and PDF job statistics are loaded at call time to avoid
cross-feature import cycles.

| View module | Responsibility |
|---|---|
| `views_source_workspace.py` | Source landing/workspace plus file/upload import actions |
| `views_source_browser.py` | Inventory filters, table configuration and file/source actions |
| `views_source_detail.py` | Source details, source-backed InfoSites and source graphs |
| `views_content.py` | Records, artifacts and artifact generation |
| `views_semantic.py` | Semantic terms and enrichment-job pages |
| `views_jira.py` | Jira search/timeline/graph/analysis and exclusions |
| `views_chat.py` | Domain chat, compatible conversation actions and prompt backlog |
| `views_pdf.py` | PDF inventory, job queue, reports and JSON status |

Newly separated views and local import helpers call their owning adapters
directly, not the compatibility facade. Existing external consumers may
continue importing `services` or `views_data_sources`; `views.py` and the
URL configuration retain the same exported handler objects. Tests patch
dependencies where their implementation now lives, rather than assuming
that changing a facade global alters every consumer.

`tests/test_django_module_boundaries.py` checks facade exports, URL callback
identity, bound globals in moved functions, no reverse dependencies on
facades, and chat/prompt file-output behavior. Existing domain, retrieval,
source browser, record/InfoSite, chat, PDF and packaging tests cover the
surrounding behavior.

This is a responsibility/module split, **not** a claim that every service is
now Django-independent: ORM/configuration/presentation adapters remain in
`django_site`. It introduces no queue, migration, authorization change,
provider switch or service restart.

## P1: shared Jira retrieval service (2026-10-28)

`ki_knowledge/services/jira_retrieval.py` now owns hybrid Jira search, the daily
timeline, graph exploration/rebuilding and domain-term/field analysis.
`JiraRetrievalService` works with explicit cache, graph and assistant instances.
It imports neither Django nor the HTTP API. The existing TF-IDF setup and field
embedding selection are shared there as well; this extraction does not change
the provider strategy, ranking algorithms or empty-index error behavior.

The call paths are:

- HTML views -> `django_site.services` compatibility facade ->
  `django_site.jira_workflow` domain/path adapter -> shared retrieval service.
- `/api/search`, `/api/timeline`, `/api/graph/{entity_id}/neighbors` and
  `/api/domain/terms` -> shared retrieval service directly.

The old function signatures and result dictionaries remain available.
Overridden duplicate implementations of these four functions were removed
from `django_site.services`; its active forwarding wrappers remain.

The Django adapter now constructs retrieval from the domain's resolved cache
and graph paths. It no longer temporarily changes process-wide environment
variables or borrows the singleton runtime of the API. This intentionally fixes
cross-domain cache reuse: a request for beta cannot reuse alpha's initialized
cache. Existing domain-specific/legacy path resolution stays in the adapter.
The API retains its existing default-runtime initialization and compatibility
globals; per-domain API routing has not been added.

`tests/test_jira_retrieval.py`, `tests/test_jira_retrieval_views.py` and the
retrieval cases in `tests/test_jira_api.py` cover result shapes, limits, actual
temporary stores, domain switching, path overrides, HTML/facade forwarding,
and API retrieval without the Django service facade.

**Still outside this slice:** source imports and synchronous job execution,
semantic job dispatch, support-chat orchestration, term curation/reimport and
general domain-path extraction. In particular, semantic API routes still use
the existing Django facade. This is the first P1 slice, not completion of the
whole service-layer refactor.

## P1: import-status execution boundary (2026-10-28)

The second P1 slice separates the synchronous import-status operation:

- `services/document_import.py`: job orchestration using `DocumentImportService`
  and the small `ImportDocuments` repository protocol; no Django imports.
- `django_site/document_import.py`: ORM lookups scoped to the job's project,
  timestamp/status updates and a transaction covering the batch.
- `services/import_runner.py`: existing entry points retained as composition
  and compatibility wrappers; enqueue and execution remain explicit.
- `infosite_import_selected`: request parsing, synchronous service call,
  notifications and redirect only.

There is no new queue, worker, data migration or content-ingestion behavior.
Batch writes now roll back together on ORM failure; invalid form IDs surface
an error instead of being silently dropped. Missing/foreign documents retain
the prior skip behavior with warning logs. Explicit job reruns clear stale
job errors/completion metadata. Details, including the non-atomic boundary
between the ORM database and job journal, are in the
[InfoSite execution contract](../features/INFOSITE.md#import-control-current-execution-contract).

The import tests cover real temporary SQLite job state, failures and reruns,
HTTP notifications, and the real ORM adapter in a child process with an
in-memory Django database, including batch rollback and project isolation.
No application database is used for that integration test.

Remaining work includes other source/PDF pipelines, semantic dispatch and the
broader service facade; these two P1 slices do not complete P2/P3.

## P2: domain/filesystem boundary (2026-10-28)

The canonical filesystem helpers now live in `services/domain_paths.py`.
They use `DataLayout` without importing Django, FastAPI or any ORM registry.
They own source/state path resolution, case-preserving directory matching,
source-to-domain inference and bounded symlink-root discovery.
`django_site/domain_paths.py` keeps explicit compatibility exports and the
existing Django summary-cache adapter (keys, TTL, invalidation and fallback
behavior). Existing callers can still import the old names.

Source workflows, Jira adapters, summary logic and management commands now
import filesystem helpers from the service directly; cache operations stay in
the Django adapter. `DataLayout` remains the only layout-version authority.
No directory migration or new data layout was introduced.

Existing side effects are deliberately preserved: `domain_state_paths` can
rename a legacy state filename when the preferred filename is absent;
`domain_pdf_dir` creates the selected PDF directory, while resolving source
roots alone does not. Linked-directory discovery retains its existing cache,
depth bound and inaccessible-directory handling.

Two historical naming/default policies are **not silently unified**:

- The filesystem helpers preserve internal dots in slugs and use
  `KNOWLEDGE_DOMAIN`, then `KICLI_DOMAIN`, otherwise `default`.
- The existing `django_site.services` registry facade replaces dots and uses
  `KNOWLEDGE_DEFAULT_DOMAIN`, otherwise the first discovered domain. Its
  normalizer delegates to the explicitly named `normalize_registry_domain`;
  discovery and ORM registry backfill remain Django responsibilities.

Changing those policies together would be a behavior/data-identity migration,
not a safe code extraction. The policy distinction is now explicit and covered
by contract tests rather than hidden in two similarly named implementations.

`tests/test_domain_paths.py` checks layouts v1/v2/v3, case matching, legacy
filename handling, overrides, PDF directory creation, symlink loops, cache
keys/invalidation, old import compatibility and imports without Django.
Existing source-browser/domain-chat/Jira consumers retain their contracts.

This is the first P2 slice. Domain lifecycle operations, other source and
semantic services, and the leading-store decisions for InfoSite/Wagtail are
still separate work.

## P2: InfoSite/Wagtail ownership boundary (2026-10-28)

The second P2 slice makes the existing ownership contract explicit in the
[content model matrix](../architecture/content-model-matrix.md#0-verbindliche-speicher--und-adaptergrenze-p2).
Input/output files remain authoritative content. The existing
`SourceDocument`/`GeneratedDocument` rows are shared with Wagtail snippets;
there is no second CMS document registry. Pipeline statuses, editorial
statuses and page publication remain independent.

`services/infosite_catalog.py` reads persisted InfoSite project blocks and
computes statistics from those records. It uses `KnowledgeStore(read_only=True)`:
SQLite opens an existing database with `mode=ro`, PostgreSQL connections use
a read-only transaction, and schema initialization is skipped. Existing
writable consumers retain their default behavior.

Wagtail rendering no longer creates/publishes detail pages, initializes a
store or reparses source files for statistics. Store failures are logged and
displayed explicitly instead of being presented as empty results.
Only live existing detail pages are linked. The explicit, repeatable
`setup_wagtail_cms` command creates/publishes missing catalog/project pages;
existing drafts and editorial content remain untouched.

`output_registry.py` remains the metadata-upsert bridge after generation and
refinement. It preserves editorial fields, applies a supplied source iterable
consistently to every generated document, and propagates unreadable-file
errors instead of recording an empty hash as successful synchronization.
Existing snippet permissions and content-review policy have not changed.

The catalog/ownership tests exercise real temporary block stores plus a
migrated **in-memory** Django/Wagtail database in an isolated child process.
They cover read-only SQL, no initialization/writes while rendering, explicit
setup, draft preservation, shared snippets, live persisted statistics,
visible failures, provenance and preservation of editorial metadata.

No schema/data migration, source-ID rewrite or store merge is included.
The general store target and InfoSite SQLite block store remain separate.
Remaining source/PDF services, semantic dispatch and the wider service facade
are still separate cleanup slices; these two P2 steps do not complete that
broader modularization.

## P3: lifecycle entry points (2026-10-28)

Comparison with the current Assist README/`StackctlBridge` and stackctl's user
installation contract found that ki-knowledge's wrapper still bootstrapped a
second stackctl inside its project venv. That duplicate bootstrap is removed.
The canonical interface is the central `stackctl` command, invoked in the
project checkout; its tool environment is separate from application dependencies.
Project config loaders and `{python}` service commands use the project interpreter.

`kistack` is retained only as a compatibility alias. Like Assist, it prefers
`~/.local/bin/stackctl`, otherwise PATH, always with the selected project as
cwd. It preserves arguments and exit status, works through a symlink, and
reports a missing central tool instead of cloning/installing anything.
`stackctl install` alone owns project environment/dependency setup.
The two `examples/run_knowledge_*.py` aliases continue forwarding to local
foreground mode; API environment overrides remain compatible.

README and active launch guides now recommend `stackctl start|run|status|logs`.
Django management commands remain available for administration; direct
`manage.py runserver` is a deliberate bypass, not another lifecycle manager.
No HTTP API, CLI business command, URL or persistence interface was removed.
This is the lifecycle portion of P3, not permission to remove the P1/P2
compatibility facades or the two API modules without separate consumer checks.

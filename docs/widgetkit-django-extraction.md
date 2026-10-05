# widgetkit-django extraction log

This document records the extraction of the reusable dashboard/layout builder layer from `ki-knowledge` into the standalone package `widgetkit_django`.

## Goal

The original builder was tightly embedded in `ki_knowledge.django_site`:

- builder routes and controller logic lived in app views
- templates and static assets were app-local
- persistence wrote directly to dashboard models
- navigation metadata and builder metadata were duplicated
- widget taxonomy and page wiring were inconsistent across areas

The extraction goal was not an immediate repository split, but a safe internal separation:

1. stabilize builder behavior
2. normalize widget taxonomy
3. centralize metadata
4. extract generic builder UI and orchestration
5. leave only host-specific adapters inside `django_site`

## Phase 1: stabilize builder behavior

The first work focused on correctness before extraction.

### Width persistence and UI behavior

The builder had a client-side bug where widget width changes snapped back after selection. The root cause was not server persistence, but browser-side form behavior. The builder JavaScript was hardened so that:

- saving uses an explicit `data-save-url`
- widget width updates apply immediately in CSS
- form action mutation no longer leaks invalid URLs such as `[object HTMLInputElement]`

### Width constraints

Widget sizing rules were pushed through the whole stack:

- `WidgetSpec` gained `min_w` and `resizable`
- builder controls hide invalid widths
- non-resizable widgets render a fixed-width indicator
- persistence clamps widths server-side

This mattered before extraction because a reusable package must carry consistent layout rules instead of relying on host-specific UI behavior.

## Phase 2: normalize taxonomy and page participation

Before extracting code, the widget model itself had to become coherent.

### Canonical widget IDs

The old `sources.*` naming was normalized under the `datasources` area:

- `sources.filter.v1` -> `datasources.sources.filter.v1`
- `sources.list.v1` -> `datasources.sources.list.v1`
- `sources.unimported.v1` -> `datasources.sources.unimported.v1`

Legacy aliases remained supported through canonicalization so persisted layouts stayed compatible.

### Workspace page migration

`/data-sources/workspace/` was still hardcoded and did not participate in builder-configured layouts. It was moved onto the same subpage-aware layout pipeline used elsewhere:

- area: `datasources`
- subpage: `workspace`

This was necessary so the future package could treat page targets uniformly.

## Phase 3: centralize builder and navigation metadata

The next step removed duplicated page metadata.

Builder subpage targets and navigation submenu definitions were first extracted into a shared registry, later moved into:

- `ki_knowledge/widgetkit_django/layout_targets.py`

That module now provides:

- `layout_targets_for_area(...)`
- `layout_target(...)`
- `layout_builder_url(...)`
- `nav_areas_config()`

This unified:

- builder subpage tabs
- navigation menus
- builder entry URLs in templates and view code

At this point, metadata was no longer owned by app-local builder code.

## Phase 4: extract generic templates and assets

With metadata stable, the generic UI moved into the new package:

- `templates/widgetkit_django/dashboard_builder.html`
- `templates/widgetkit_django/dashboard_builder_shell.html`
- `static/widgetkit_django/css/dashboard-builder.css`
- `static/widgetkit_django/js/dashboard-builder.js`

`widgetkit_django` was then added to `INSTALLED_APPS` so Django could discover its templates and static assets.

This shifted the builder’s presentation layer out of `django_site`.

## Phase 5: introduce persistence abstraction

The builder originally manipulated `DashboardDefinition` and `DashboardWidgetPlacement` directly. To make this reusable, a store contract was introduced:

- `ki_knowledge/widgetkit_django/layout_store.py`

It defines:

- `LayoutPlacement`
- `LayoutStore`

The host project now provides the concrete backend in:

- `ki_knowledge/django_site/layout_store.py`

with `DjangoDashboardLayoutStore`.

This changed persistence from “builder knows app models” to “builder knows placement contract”.

## Phase 6: extract generic builder actions

After persistence was abstracted, action handling moved next.

The generic mutation/seed logic now lives in:

- `ki_knowledge/widgetkit_django/builder_actions.py`

It owns reusable behavior for:

- `add`
- `remove`
- `reset`
- `save-order`
- shared-layout seeding
- subpage-specific default seeding
- width clamping

The host dispatcher only passes concrete registry and store functions into this service.

## Phase 7: extract generic builder context assembly

Next, builder-page context generation was pulled out into:

- `ki_knowledge/widgetkit_django/builder.py`

This module builds:

- selected widget metadata
- unused widget lists
- area tabs
- subpage tabs
- width-option metadata

At this point, generic rendering state no longer had to be assembled in host views.

## Phase 8: define a registry contract

To remove hidden coupling to `django_site.dashboard_registry`, an explicit registry interface was added:

- `ki_knowledge/widgetkit_django/registry.py`

It defines:

- `WidgetRegistry`
- `CallbackWidgetRegistry`

The package now depends on an explicit host-facing contract:

- builtin areas
- widget hierarchy
- widget IDs
- widget lookup by ID
- default widgets by area/subpage

This was a key turning point: the extraction boundary became an API instead of a set of ad-hoc callbacks.

## Phase 9: extract the builder controller

The final controller split moved the generic Builder view into:

- `ki_knowledge/widgetkit_django/views.py`

using:

- `BuilderViewConfig`
- `dashboard_builder_view(...)`

The host view in `django_site/views_dashboard.py` now only wires:

- active-domain lookup
- registry adapter
- layout-store adapter
- selection loader
- selection syncer
- host `base.html`

That changed `django_site` from owning the controller to merely adapting it.

## Phase 10: decouple from host base template

The extracted page template originally still extended the project’s `base.html`.

To remove that hard dependency, the package gained:

- `templates/widgetkit_django/base.html`

and the builder template now extends a configurable `widgetkit_base_template`.

Result:

- the package can render standalone with its own minimal base template
- a host app can still inject `base.html`

## Current boundary

The current split is:

### Owned by `widgetkit_django`

- builder templates and static assets
- area/subpage metadata
- builder URL helpers and template tag
- layout store protocol
- placement dataclass
- registry contract
- generic builder actions
- generic builder context assembly
- generic builder controller
- fallback base template

### Owned by `django_site`

- concrete widget registry content
- concrete Django persistence backend
- active-domain/session semantics
- app-specific widgets and data providers
- host route wiring
- host chrome (`base.html`)

## What “extracted” means right now

`widgetkit_django` is now an internal package with a real public boundary, not just moved files.

It is ready for the next step:

1. copy into its own repository
2. add its own packaging metadata
3. publish/install it as an external dependency
4. leave only the host adapters in `ki-knowledge`

## Files added during extraction

Main package files:

- `ki_knowledge/widgetkit_django/apps.py`
- `ki_knowledge/widgetkit_django/builder.py`
- `ki_knowledge/widgetkit_django/builder_actions.py`
- `ki_knowledge/widgetkit_django/layout_store.py`
- `ki_knowledge/widgetkit_django/layout_targets.py`
- `ki_knowledge/widgetkit_django/registry.py`
- `ki_knowledge/widgetkit_django/views.py`
- `ki_knowledge/widgetkit_django/templatetags/widgetkit_django.py`
- `ki_knowledge/widgetkit_django/templates/widgetkit_django/base.html`
- `ki_knowledge/widgetkit_django/templates/widgetkit_django/dashboard_builder.html`
- `ki_knowledge/widgetkit_django/templates/widgetkit_django/dashboard_builder_shell.html`
- `ki_knowledge/widgetkit_django/static/widgetkit_django/css/dashboard-builder.css`
- `ki_knowledge/widgetkit_django/static/widgetkit_django/js/dashboard-builder.js`

Host adapter files:

- `ki_knowledge/django_site/layout_store.py`
- `ki_knowledge/django_site/views_dashboard.py`
- `ki_knowledge/django_site/views_common.py`
- `ki_knowledge/django_site/ui_dispatcher.py`

## Validation summary

The extraction was kept behavior-safe through targeted checks:

- Django system check
- targeted builder/layout target tests
- targeted builder seeding/persistence regressions
- focused tests for the new registry and placement-loading boundary

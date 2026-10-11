# widgetkit-django host integration

This guide shows what a host Django application must provide to use `widgetkit_django`.

## 1. Install the app

Add the package to `INSTALLED_APPS` so Django discovers templates, static files, and template tags.

Current in-repo app name:

- `widgetkit_django`

## 2. Provide a layout store

Implement `widgetkit_django.layout_store.LayoutStore`.

Required methods:

- `load_placements(...)`
- `load_shared_placements(...)`
- `replace_placements(...)`
- `clear_placements(...)`

The host decides:

- which database models back placements
- how dashboards are keyed
- whether layouts are user-owned, shared, tenant-owned, or domain-owned

## 3. Provide a widget registry

Use `widgetkit_django.registry.CallbackWidgetRegistry` or your own implementation of `WidgetRegistry`.

The registry must answer:

- which builder areas exist
- which widgets belong to which categories
- how to resolve a widget by ID
- which defaults seed each area/subpage

## 4. Provide selection wiring

The generic builder view does not decide session semantics.

The host supplies:

- a selection loader
- a selection syncer
- active-domain lookup

This keeps package logic reusable across:

- single-tenant apps
- multi-tenant apps
- domain-scoped workspaces

## 5. Mount the builder view

Use `widgetkit_django.views.dashboard_builder_view(...)` from a thin host adapter view and pass a `BuilderViewConfig`.

Typical host choices:

- route name
- page title
- page subtitle
- base template name

## 6. Optional host chrome

If the host wants the builder inside its own site shell, pass:

- `base_template_name="base.html"`

If not, the package falls back to:

- `widgetkit_django/base.html`

## 7. Reuse metadata helpers

The package can also drive navigation and builder links:

- `layout_builder_url(...)`
- `layout_targets_for_area(...)`
- `layout_target(...)`
- `nav_areas_config()`

This avoids duplicating page-target metadata between navigation and builder tabs.

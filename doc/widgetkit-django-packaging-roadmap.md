# widgetkit-django packaging roadmap

This roadmap describes the remaining work to move `widgetkit_django` from an in-repo package to a standalone project.

## Already done

- generic builder controller extracted
- generic registry contract extracted
- generic layout-store contract extracted
- generic builder actions extracted
- generic builder context assembly extracted
- builder templates and static files moved into package
- fallback package base template added
- host app reduced to concrete adapters

## Remaining work for standalone publication

### 1. Create a dedicated repository

Copy:

- `ki_knowledge/widgetkit_django/`

into a new repository named `widgetkit-django`.

## 2. Add package-local metadata

Create package-level:

- `pyproject.toml`
- license file
- changelog
- release workflow

## 3. Split tests cleanly

Keep generic package tests with the new project and leave host-app integration tests in `ki-knowledge`.

A good split is:

- package tests: metadata, controller, template behavior, contract helpers
- host tests: concrete registry content, persistence backend, app-specific widget behavior

## 4. Define versioned public API

Document which modules are public and stable:

- `layout_store`
- `layout_targets`
- `registry`
- `views`
- possibly `builder_actions`

Avoid exposing host-specific internal assumptions.

## 5. Replace in-repo import in ki-knowledge

After publishing:

1. remove the in-repo package copy
2. add external dependency
3. keep only adapter implementations in `django_site`

## 6. Optional future improvements

- dedicated widget spec dataclass in `widgetkit_django`
- typed response objects instead of generic `Any`
- separate builder shell endpoint helpers
- packaged demo project
- more standalone screenshots/examples

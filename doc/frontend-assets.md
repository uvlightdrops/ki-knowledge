# Frontend asset rules

## Where code belongs

- Put executable page behavior in page-specific static JavaScript files, not
  multi-line template `<script>` blocks. Put stylesheet rules in static CSS,
  loaded with `{% static %}`. The base theme owns shared visual primitives;
  page styles should not silently change unrelated pages.
- Use `django_site/js/` and `django_site/css/` for general Django pages, and
  `infosite/js/` and `infosite/css/` for InfoSite pages.
- Load scripts after the DOM/configuration they consume, or use `defer` /
  `DOMContentLoaded`. Load third-party libraries before scripts that need them.
- Reuse a helper only when the behavior and ownership are genuinely shared.
  `bulk-selection.js` handles form-owned checkboxes, including controls using
  `form="..."` outside the form. Preview/import/refinement workflows remain
  page-specific.

## What stays in templates

- Small declarative dynamic style attributes are appropriate: e.g.
  `style="grid-column: span {{ card.width }};"`, CSS custom properties for
  widget dimensions, or a progress bar's calculated percentage. Prefer a
  class for static styling or a repeated visual state.
- Simple scalar configuration belongs in quoted, autoescaped `data-*`
  attributes. Read it through `element.dataset`; parse numbers/booleans
  explicitly when needed. Do not use `escapejs` for HTML attributes.
- Structured data belongs in `{{ payload|json_script:"page-data" }}` and is
  read with `JSON.parse(document.getElementById("page-data").textContent)`.
  Pass the Python list/dict itself, **not** a pre-serialized JSON string.
  `json_script` safely escapes `<`, `>` and `&`, including closing script tags.
- Static files must not contain Django variables or tags. Never interpolate
  template values into executable JavaScript or use `|safe` for data scripts.
- New handlers should use `addEventListener` rather than inline `onclick`
  or `onsubmit`. Existing short confirmation handlers are a separate,
  incremental cleanup; their presence is not a strict-CSP compatibility claim.

Do not mass-replace `style` attributes. Assess each page's semantics and
cascade, preserve dynamic dimensions, and extract compound/repeated static
styles when working on that page. Existing small/legacy presentation
attributes may remain until that page is deliberately restyled.

## Cleanup inventory (2026-10-07)

All 107 HTML templates under `ki_knowledge/` were scanned. There were no
remaining `<style>` blocks. Executable script blocks were extracted from:

- `document_preview.html`
- InfoSite: `ai_refine`, `project_detail`, `preview`, `import_control`,
  `knowledge_blocks`
- KICLI: `records`, `artifacts`, `jobs`, `jira_support_chat`, `settings_layout`,
  `pdf_import_jobs`, `graph_3d`

The widget shell builder's inline bootstrap is now `data-*` configuration
plus its existing `json_script` preset. Hierarchy/document/statistics payloads
also use `json_script`. The widget catalog receives its list directly rather
than double-encoding it, and its preview table/stat/link styles are restored.
Document preview's static attributes and 3D graph dimensions moved to CSS.

Intentionally inline: serialized JSON, scalar `data-*` values, declarative
dynamic dimensions, existing short confirmations, and legacy small style
attributes (258 style attributes and 23 short event handlers in this snapshot).
No executable `<script>` bodies or stylesheet blocks remain in
the repository's HTML templates. External script references remain.

## Validation

`tests/test_frontend_assets.py` checks template rendering, escaping, payload
types, static references and the no-inline-block inventory without database
queries. It also exercises the shared selection and catalog loader in Node
when available. Run with Django initialized:

```bash
.venv/bin/python - <<'PY'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
import django
django.setup()
import pytest
raise SystemExit(pytest.main(["-q", "tests/test_frontend_assets.py"]))
PY
.venv/bin/python manage.py check
```

Use `node --check` on changed JavaScript. These are not visual/browser tests;
check page interactions and third-party integrations in a browser when
deploying. Do not run database tests against the application's real database:
use an explicitly isolated test database and a database-aware runner.

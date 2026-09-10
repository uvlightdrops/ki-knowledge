# Widget Building the Wagtail Way

This note describes the intended direction for widget building in ki-knowledge:
use Wagtail for the editorial basics, but keep widgets data-driven and reusable.

## Goal

Widgets should behave like Wagtail content objects:

- registered centrally
- editable through a small structured config surface
- rendered through shared templates
- previewed from the same data path as the live view

Hardcoded `if/else` HTML should stay a temporary fallback only.

## What Wagtail already gives us

Wagtail is already used for:

- CMS pages (`Page` subclasses)
- snippets (`SnippetViewSet`)
- moderation workflow (`DraftStateMixin`, `RevisionMixin`, `WorkflowMixin`)
- structured editor UI via panels

That means we already have the right primitives for a widget system that is more Wagtail-like and less ad hoc.

## What a Wagtail-style widget system should contain

### 1. Widget model / spec

Each widget needs a canonical spec with:

- stable widget id
- label, description, category
- area assignment
- default width and layout hints
- config schema

This spec is the equivalent of a Wagtail content type definition.

### 2. Structured editor UI

Widget configuration should be edited with structured fields, not freeform HTML.

Examples:

- data source selector
- domain filter
- width
- sort order
- visible columns
- toggle options

In Wagtail terms this is the equivalent of panels / form fields, not raw template code.

### 3. Data adapter per widget type

Each widget should have a small adapter that returns the data it needs.

Examples:

- domain inventory widget -> domain stats query
- source overview widget -> source counts and recent items
- knowledge widget -> block counts and semantic metrics
- output widget -> generated document stats

The adapter prepares data; it does not build the final HTML.

### 4. Shared renderer

Rendering should be centralized:

- one card layout
- one preview layout
- optional inner fragments for tables, chips, lists, etc.

This avoids duplicate HTML per widget type and keeps the UI consistent.

### 5. Preview from the live path

The preview should use the same adapter and renderer as the real widget.

That means:

- no separate preview-only HTML
- no second rendering branch just for the catalog
- preview data can be sample data or live data, depending on cost

## What to avoid

- hardcoded HTML inside long `if/else` chains
- widget-specific template duplication
- preview logic that diverges from live rendering
- mixing config UI with output HTML

## Practical build plan

If we want this to feel like a slim Wagtail-style system, the next step is:

1. define `WidgetSpec`
2. define widget config forms / schema
3. add adapter functions for data
4. render everything through one card component
5. keep builder/catalog preview and live views on the same path

That gives us the Wagtail pattern without rebuilding Wagtail itself.

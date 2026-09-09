# Dashboard and page-level layout concept

## Goal

We want a single layout system for the application, but with separate persistent layouts per page area instead of one global ad-hoc layout state.

## Model

Each page area owns a `DashboardDefinition` record:

- `dashboard`: top-level home dashboard
- `datasources`: Data Sources landing page
- `knowledge`: Internal Knowledge landing page
- `infooutput`: Info Output landing page
- `admin`: admin-specific widgets
- `settings`: settings tools and config surfaces

Each area stores a ordered list of widget placements (`DashboardWidgetPlacement`) with:

- `widget_id`
- `sort_index`
- `x`, `y`, `w`, `h`
- `config_json`

This keeps the layout state independent from the page contents while still allowing a clean drag-and-drop editor.

## Design rules

1. Layout state is area-scoped, not global.
   - A layout change on `/data-sources/` must not mutate the layout of `/knowledge/`.
2. Default layouts remain deterministic.
   - Every area gets a fallback widget list from the registry when no saved layout exists.
3. Area selection is explicit in the builder UI.
   - The builder dropdown chooses the active `area_key` before loading or saving widgets.
4. Widgets remain business-domain oriented.
   - The widget registry keeps canonical IDs and metadata; page templates consume them, not raw view logic.
5. Unused widgets are kept in a dedicated stash.
   - This allows a “parked but not deleted” workflow before the widget is placed elsewhere.

## Builder workflow

- Open `/settings/layout/builder/?area=<area_key>`.
- Select the page area from the dropdown.
- Drag widgets into the grid or move them to “Unused”.
- Save order updates the persisted layout for that area only.
- The saved layout is loaded by the corresponding page view when rendering the page.

## Rendering contract

Page views should call a shared helper to resolve the configured widget IDs for the current area and render them with the consistent dashboard-grid template.

Example contract:

- root dashboard view → `area_key="dashboard"`
- data sources view → `area_key="datasources"`
- knowledge view → `area_key="knowledge"`
- info output view → `area_key="infooutput"`

The layout builder is the only place that edits the placements; page views simply consume them.

## Why this is the right split

This keeps the system flexible without coupling layout state to one single page or one homepage fragment.
It also matches the user workflow: configure a page layout in place, then reuse the same widget registry across all major areas without mixing page-specific content into the builder state.

## Next implementation steps

1. Ensure every major landing page resolves its own `area_key` and loads persisted placements.
2. Keep the builder UI as the canonical editor for all page-area layouts.
3. Add optional page-specific default widgets per area if a page needs a stricter starter layout.
4. Only then consider advanced features like snapping, copy-between-pages, or template presets.

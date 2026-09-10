"""Widget registry and taxonomy for the dashboard builder.

This module provides the initial taxonomy for the dashboard migration. The
frontpage and legacy dashboard area are intentionally not treated as a widget
namespace; instead widgets are organized by business function:

- datasources
- knowledge
- infooutput
- admin
- settings

This keeps the registry aligned with the actual functional areas and allows the
future builder UI to compose dashboards from business-domain widgets instead of
page-centric dashboard containers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Tuple


@dataclass(frozen=True)
class WidgetSpec:
    """Metadata for a dashboard widget.

    `widget_id` is the canonical, persistent identifier for a widget and is the
    stable key used in storage, migrations and builder actions.
    """

    widget_id: str
    area: str
    category: str
    label: str
    description: str
    default_size: str = "balanced"
    default_w: int = 6
    default_h: int = 1
    render_kind: str = "card"
    preview_kind: str = "summary"
    config_schema: tuple[str, ...] = ()
    data_adapter: str = ""
    legacy_aliases: Tuple[str, ...] = ()


def _widget(
    *,
    widget_id: str,
    area: str,
    category: str,
    label: str,
    description: str,
    default_size: str = "balanced",
    default_w: int = 6,
    default_h: int = 1,
    render_kind: str = "card",
    preview_kind: str = "summary",
    config_schema: Iterable[str] = (),
    data_adapter: str = "",
    legacy_aliases: Iterable[str] = (),
) -> WidgetSpec:
    return WidgetSpec(
        widget_id=widget_id,
        area=area,
        category=category,
        label=label,
        description=description,
        default_size=default_size,
        default_w=default_w,
        default_h=default_h,
        render_kind=render_kind,
        preview_kind=preview_kind,
        config_schema=tuple(config_schema),
        data_adapter=data_adapter,
        legacy_aliases=tuple(legacy_aliases),
    )


def widget_adapter_key(widget_id: str) -> str:
    spec = widget_by_id(widget_id)
    return spec.data_adapter if spec is not None else ""


# Canonical registry: business-function based, not page-based. The legacy
# dashboard page is intentionally not a widget area in this registry.
_REGISTRY: Dict[str, WidgetSpec] = {
    "datasources.domain.overview.v1": _widget(
        widget_id="datasources.domain.overview.v1",
        area="datasources",
        category="overview",
        label="Domains",
        description="Overview of the configured domains and their active source footprint.",
        default_size="wide",
        default_w=8,
        default_h=1,
        data_adapter="datasources.domain_overview",
    ),
    "datasources.overview.summary.v1": _widget(
        widget_id="datasources.overview.summary.v1",
        area="datasources",
        category="overview",
        label="Overview",
        description="Summary of data-source counts, health and recent activity.",
        default_size="wide",
        default_w=8,
        default_h=1,
        data_adapter="knowledge.overview",
    ),
    "datasources.import.quick.v1": _widget(
        widget_id="datasources.import.quick.v1",
        area="datasources",
        category="import",
        label="Quick import",
        description="Quick access actions for markdown, PDF, Jira and OWL imports.",
        default_size="balanced",
        default_w=6,
        default_h=1,
        data_adapter="datasources.import_quick",
        legacy_aliases=("quick-import",),
    ),
    "datasources.sources.discovery.v1": _widget(
        widget_id="datasources.sources.discovery.v1",
        area="datasources",
        category="sources",
        label="Sources discovery",
        description="Discovery and ingestion status for source documents.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        data_adapter="datasources.discovery",
    ),
    "datasources.jobs.recent.v1": _widget(
        widget_id="datasources.jobs.recent.v1",
        area="datasources",
        category="jobs",
        label="Recent jobs",
        description="Latest import and sync jobs for the configured domain.",
        default_size="wide",
        default_w=8,
        default_h=1,
        data_adapter="infooutput.overview",
    ),
    "datasources.source.list.v1": _widget(
        widget_id="datasources.source.list.v1",
        area="datasources",
        category="sources",
        label="Source list",
        description="Most relevant source cards for the current domain.",
        default_size="wide",
        default_w=8,
        default_h=1,
        data_adapter="admin.domain_db",
    ),
    "datasources.ai.summary.v1": _widget(
        widget_id="datasources.ai.summary.v1",
        area="datasources",
        category="ai",
        label="AI workspace",
        description="AI-related source workflow actions for the active domain.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        data_adapter="datasources.discovery",
    ),
    "datasources.markdown.files.v1": _widget(
        widget_id="datasources.markdown.files.v1",
        area="datasources",
        category="files",
        label="Markdown files",
        description="Workspace markdown overview and quick access to source files.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "datasources.ontology.overview.v1": _widget(
        widget_id="datasources.ontology.overview.v1",
        area="datasources",
        category="ontology",
        label="Ontology overview",
        description="OWL and ontology import state for the current domain.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "knowledge.overview.summary.v1": _widget(
        widget_id="knowledge.overview.summary.v1",
        area="knowledge",
        category="overview",
        label="Overview",
        description="Knowledge base counts and aggregate indicators.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "knowledge.semantic.monitor.v1": _widget(
        widget_id="knowledge.semantic.monitor.v1",
        area="knowledge",
        category="semantic",
        label="Semantic monitor",
        description="Semantic pipeline status and enrichment counts.",
        default_size="balanced",
        default_w=6,
        default_h=1,
        legacy_aliases=("semantic-monitor",),
    ),
    "knowledge.semantic.quick.v1": _widget(
        widget_id="knowledge.semantic.quick.v1",
        area="knowledge",
        category="semantic",
        label="Quick semantic tasks",
        description="Direct actions for semantic extraction and refinement jobs.",
        default_size="balanced",
        default_w=6,
        default_h=1,
        legacy_aliases=("semantic-quick",),
    ),
    "knowledge.records.summary.v1": _widget(
        widget_id="knowledge.records.summary.v1",
        area="knowledge",
        category="records",
        label="Records summary",
        description="Record volume and aspect overview for the active domain.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "knowledge.artifacts.summary.v1": _widget(
        widget_id="knowledge.artifacts.summary.v1",
        area="knowledge",
        category="artifacts",
        label="Artifacts summary",
        description="Artifacts and generated output overview for the current knowledge domain.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "knowledge.api.browser.v1": _widget(
        widget_id="knowledge.api.browser.v1",
        area="knowledge",
        category="api",
        label="Knowledge API",
        description="Browser and search view for the knowledge API across sources and records.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "knowledge.jobs.recent.v1": _widget(
        widget_id="knowledge.jobs.recent.v1",
        area="knowledge",
        category="jobs",
        label="Recent jobs",
        description="Recent semantic enrichment, indexing and background task activity.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "knowledge.tools.summary.v1": _widget(
        widget_id="knowledge.tools.summary.v1",
        area="knowledge",
        category="tools",
        label="Tasks and tools",
        description="Quick links and task shortcuts for the knowledge workflow.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "knowledge.graph.overview.v1": _widget(
        widget_id="knowledge.graph.overview.v1",
        area="knowledge",
        category="graph",
        label="Graph overview",
        description="Graph context and concept relationships for the active domain.",
        default_size="balanced",
        default_w=6,
        default_h=1,
    ),
    "infooutput.overview.summary.v1": _widget(
        widget_id="infooutput.overview.summary.v1",
        area="infooutput",
        category="overview",
        label="Overview",
        description="Generated output overview and publication summary.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "infooutput.infosite.recent.v1": _widget(
        widget_id="infooutput.infosite.recent.v1",
        area="infooutput",
        category="infosite",
        label="Recent infosites",
        description="Recent output projects and their current generation state.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "infooutput.documents.recent.v1": _widget(
        widget_id="infooutput.documents.recent.v1",
        area="infooutput",
        category="documents",
        label="Recent output documents",
        description="Recently generated or published documents for the active domain.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "infooutput.formats.summary.v1": _widget(
        widget_id="infooutput.formats.summary.v1",
        area="infooutput",
        category="formats",
        label="Formats",
        description="Available output formats, planning status and navigation targets.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "infooutput.domain.overview.v1": _widget(
        widget_id="infooutput.domain.overview.v1",
        area="infooutput",
        category="overview",
        label="Domain overview",
        description="Generated-document status across all configured domains.",
        default_size="wide",
        default_w=8,
        default_h=1,
    ),
    "infooutput.generated.documents.v1": _widget(
        widget_id="infooutput.generated.documents.v1",
        area="infooutput",
        category="documents",
        label="Generated documents",
        description="Generated and reviewed output files available for publication.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "admin.domain.management.v1": _widget(
        widget_id="admin.domain.management.v1",
        area="admin",
        category="domain",
        label="Domain management",
        description="Create, select and manage active domains in the knowledge workspace.",
        default_size="wide",
        default_w=8,
        default_h=1,
        legacy_aliases=("domain-management",),
    ),
    "admin.domain.db.overview.v1": _widget(
        widget_id="admin.domain.db.overview.v1",
        area="admin",
        category="domain",
        label="Domain DB overview",
        description="Overview of the active domain database state and related knowledge counts.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        legacy_aliases=("knowledge-summary",),
    ),
    "admin.system.status.v1": _widget(
        widget_id="admin.system.status.v1",
        area="admin",
        category="system",
        label="System status",
        description="Global status of the current application state and session health.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        legacy_aliases=("status",),
    ),
    "admin.workspace.config.v1": _widget(
        widget_id="admin.workspace.config.v1",
        area="admin",
        category="config",
        label="Workspace config",
        description="Workspace orchestration and configuration state overview.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "settings.layout.registry.v1": _widget(
        widget_id="settings.layout.registry.v1",
        area="settings",
        category="layout",
        label="Layout registry",
        description="Configuration for the current UI layout and widget preferences.",
        default_size="balanced",
        default_w=6,
        default_h=1,
    ),
    "settings.config.summary.v1": _widget(
        widget_id="settings.config.summary.v1",
        area="settings",
        category="config",
        label="Config summary",
        description="Current configuration summaries for the active workspace.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "settings.layout.preview.v1": _widget(
        widget_id="settings.layout.preview.v1",
        area="settings",
        category="layout",
        label="Layout preview",
        description="Preview of the active builder state and current grid composition.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
}


def widget_registry() -> Dict[str, WidgetSpec]:
    """Return a snapshot of the canonical widget registry."""
    return dict(_REGISTRY)


def widget_ids() -> List[str]:
    """Return the canonical widget ids in stable order."""
    return list(_REGISTRY.keys())


def widget_by_id(widget_id: str) -> WidgetSpec | None:
    """Resolve a widget by its canonical or legacy identifier."""
    if widget_id in _REGISTRY:
        return _REGISTRY[widget_id]

    for spec in _REGISTRY.values():
        if widget_id in spec.legacy_aliases:
            return spec
    return None


def area_widget_ids(area: str | None = None) -> List[str]:
    """Return widget ids filtered by area name."""
    if area is None:
        return widget_ids()
    return [widget_id for widget_id in widget_ids() if _REGISTRY[widget_id].area == area]


def widget_hierarchy() -> Dict[str, Any]:
    """Build a nested view model for a tree-based builder UI."""
    tree: Dict[str, Any] = {}

    for spec in _REGISTRY.values():
        area_bucket = tree.setdefault(spec.area, {})
        category_parts = [part for part in spec.category.split(".") if part]
        current: Dict[str, Any] = area_bucket
        for part in category_parts:
            current = current.setdefault(part, {})
        widgets = current.setdefault("_widgets", [])
        widgets.append(spec)

    return tree


def legacy_widget_aliases() -> Dict[str, str]:
    """Map legacy dashboard ids to the new canonical widget ids."""
    mapping: Dict[str, str] = {}
    for spec in _REGISTRY.values():
        for alias in spec.legacy_aliases:
            mapping[alias] = spec.widget_id
    return mapping


def builtin_areas() -> List[str]:
    """Return the canonical widget areas, including the top-level dashboard."""
    return ["dashboard", "datasources", "knowledge", "infooutput", "admin", "settings"]


def layout_positions_for_widgets(widget_ids: Iterable[str], *, columns: int = 12) -> Dict[str, Dict[str, int]]:
    """Return a simple row-major grid layout for widget ids.

    The algorithm keeps the default widths and heights from the widget registry,
    wraps onto a new row when a widget would exceed the available grid width, and
    produces deterministic x/y coordinates suitable for persistence and later
    rendering.
    """
    positions: Dict[str, Dict[str, int]] = {}
    current_x = 0
    current_y = 0

    for widget_id in widget_ids:
        spec = widget_by_id(widget_id)
        width = min(max(spec.default_w if spec is not None else 6, 1), columns)
        height = max(spec.default_h if spec is not None else 1, 1)
        if current_x + width > columns:
            current_x = 0
            current_y += 1
        positions[widget_id] = {"x": current_x, "y": current_y, "w": width, "h": height}
        current_x += width
        if current_x >= columns:
            current_x = 0
            current_y += 1

    return positions


def default_widget_ids_for_area(area: str | None = None) -> List[str]:
    """Return the canonical widget ids for a known area-specific layout.

    These are the seed layouts used when a page/area has not yet been explicitly
    configured by a user. They intentionally reuse existing widgets from the
    registry instead of inventing new page-specific identifiers.
    """
    area_key = (area or "dashboard").strip().lower()
    defaults: Dict[str, List[str]] = {
        "dashboard": frontpage_aggregate_widgets(),
        "datasources": [
            "datasources.domain.overview.v1",
            "datasources.overview.summary.v1",
            "datasources.import.quick.v1",
            "datasources.sources.discovery.v1",
            "datasources.markdown.files.v1",
            "datasources.ontology.overview.v1",
            "datasources.jobs.recent.v1",
            "datasources.source.list.v1",
            "datasources.ai.summary.v1",
        ],
        "knowledge": [
            "knowledge.overview.summary.v1",
            "knowledge.semantic.monitor.v1",
            "knowledge.semantic.quick.v1",
            "knowledge.records.summary.v1",
            "knowledge.artifacts.summary.v1",
            "knowledge.api.browser.v1",
            "knowledge.graph.overview.v1",
            "knowledge.jobs.recent.v1",
            "knowledge.tools.summary.v1",
        ],
        "infooutput": [
            "infooutput.formats.summary.v1",
            "infooutput.overview.summary.v1",
            "infooutput.domain.overview.v1",
            "infooutput.infosite.recent.v1",
            "infooutput.documents.recent.v1",
            "infooutput.generated.documents.v1",
        ],
        "admin": [
            "admin.domain.management.v1",
            "admin.domain.db.overview.v1",
            "admin.system.status.v1",
            "admin.workspace.config.v1",
        ],
        "settings": [
            "settings.layout.registry.v1",
            "settings.config.summary.v1",
            "settings.layout.preview.v1",
        ],
    }
    return list(defaults.get(area_key, defaults["dashboard"]))


def frontpage_aggregate_widgets() -> List[str]:
    """Return the widgets intended for an overview/aggregator frontpage.

    The frontpage should remain a composition layer. The dashboard top-level page
    is not treated as a widget area; instead, a home page can compose the
    overview widgets from the real functional areas.
    """
    return [
        "datasources.overview.summary.v1",
        "knowledge.overview.summary.v1",
        "infooutput.overview.summary.v1",
    ]

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

from widgetkit_django.layout import layout_positions_for_widgets as _widgetkit_layout_positions


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
    min_w: int = 3
    default_h: int = 1
    resizable: bool = True
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
    min_w: int = 3,
    default_h: int = 1,
    resizable: bool = True,
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
        min_w=min_w,
        default_h=default_h,
        resizable=resizable,
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
    "datasources.overview.summary.v1": _widget(
        widget_id="datasources.overview.summary.v1",
        area="datasources",
        category="overview",
        label="Overview",
        description="Counts of registered sources, Markdown files, and imported OWL sources in the active domain.",
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
        description="Format-neutral import: drop files or import any source folder of the domain with one click.",
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
    "datasources.mix.overview.v1": _widget(
        widget_id="datasources.mix.overview.v1",
        area="datasources",
        category="sources",
        label="Mix-Quellen",
        description="Gemischte Dateiformate im mix/-Ordner der Domain (PDF, Tabellen, Bilder mit OCR, Markdown, OWL).",
        default_size="balanced",
        default_w=4,
        default_h=1,
        data_adapter="datasources.mix",
    ),
    "datasources.sources.list.v1": _widget(
        widget_id="datasources.sources.list.v1",
        area="datasources",
        category="sources.browser",
        label="Quellen der Domain",
        description="",
        default_size="wide",
        default_w=12,
        min_w=8,
        default_h=2,
        legacy_aliases=("sources.list.v1", "datasources.source.list.v1", "datasources.sources.filter.v1", "sources.filter.v1"),
    ),
    "datasources.sources.unimported.v1": _widget(
        widget_id="datasources.sources.unimported.v1",
        area="datasources",
        category="sources.browser",
        label="Noch nicht importiert",
        description="Dateien in md/, pdf/, owl/ und mix/ der Domain ohne Eintrag im Store.",
        default_size="wide",
        default_w=12,
        min_w=8,
        default_h=1,
        legacy_aliases=("sources.unimported.v1",),
    ),
    "datasources.jobs.recent.v1": _widget(
        widget_id="datasources.jobs.recent.v1",
        area="datasources",
        category="jobs",
        label="PDF import status",
        description="Current PDF import queue counts and Jira issue total for the active domain.",
        default_size="wide",
        default_w=8,
        min_w=6,
        default_h=1,
    ),
    "datasources.markdown.files.v1": _widget(
        widget_id="datasources.markdown.files.v1",
        area="datasources",
        category="files",
        label="Markdown files",
        description="Browse and import Markdown files from the active domain.",
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
        min_w=6,
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
        min_w=6,
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
        min_w=6,
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
    "knowledge.semantic.overview.v1": _widget(
        widget_id="knowledge.semantic.overview.v1",
        area="knowledge",
        category="semantic",
        label="Semantic overview",
        description="High-level entry summary for the semantic workspace of the active domain.",
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
        min_w=6,
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
        min_w=6,
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
        min_w=6,
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
    "infooutput.infosite.stats.v1": _widget(
        widget_id="infooutput.infosite.stats.v1",
        area="infooutput",
        category="infosite",
        label="Infosite stats",
        description="Project, document and import totals for Infosite management.",
        default_size="wide",
        default_w=12,
        min_w=8,
        default_h=1,
    ),
    "infooutput.infosite.projects.v1": _widget(
        widget_id="infooutput.infosite.projects.v1",
        area="infooutput",
        category="infosite",
        label="Infosite projects",
        description="Project table with quick actions for discovery, import, AI refinement and management.",
        default_size="wide",
        default_w=12,
        min_w=8,
        default_h=2,
    ),
    "infooutput.infosite.workflow.import.v1": _widget(
        widget_id="infooutput.infosite.workflow.import.v1",
        area="infooutput",
        category="infosite",
        label="Import workflow",
        description="Step-by-step import workflow for Infosite source documents.",
        default_size="balanced",
        default_w=6,
        default_h=1,
    ),
    "infooutput.infosite.workflow.refine.v1": _widget(
        widget_id="infooutput.infosite.workflow.refine.v1",
        area="infooutput",
        category="infosite",
        label="AI refine workflow",
        description="Step-by-step AI refinement workflow for Infosite markdown content.",
        default_size="balanced",
        default_w=6,
        default_h=1,
    ),
    "infooutput.quiz.overview.v1": _widget(
        widget_id="infooutput.quiz.overview.v1",
        area="infooutput",
        category="quiz",
        label="Quiz overview",
        description="Current concept and purpose of the planned quiz output format.",
        default_size="balanced",
        default_w=8,
        min_w=6,
        default_h=1,
    ),
    "infooutput.quiz.status.v1": _widget(
        widget_id="infooutput.quiz.status.v1",
        area="infooutput",
        category="quiz",
        label="Quiz status",
        description="Current planning status and next likely integration points for quiz output.",
        default_size="balanced",
        default_w=4,
        default_h=1,
    ),
    "admin.domain.management.v1": _widget(
        widget_id="admin.domain.management.v1",
        area="admin",
        category="domain",
        label="Domain management",
        description="Registered domains with source counts, directory scan and removal of unused domains.",
        default_size="wide",
        default_w=8,
        min_w=8,
        default_h=1,
        legacy_aliases=("domain-management", "datasources.domain.overview.v1"),
    ),
    "admin.domain.create.v1": _widget(
        widget_id="admin.domain.create.v1",
        area="admin",
        category="domain",
        label="Add domain",
        description="Create a new domain in the knowledge workspace.",
        default_size="compact",
        default_w=4,
        default_h=1,
    ),
    "admin.domain.switcher.v1": _widget(
        widget_id="admin.domain.switcher.v1",
        area="admin",
        category="domain",
        label="Domain switcher",
        description="Switch active domain for current session.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        data_adapter="shared.domain_switcher",
        legacy_aliases=("datasources.domain.switcher.v1",),
    ),
    "admin.domain.db.overview.v1": _widget(
        widget_id="admin.domain.db.overview.v1",
        area="admin",
        category="domain",
        label="Domain DB overview",
        description="Overview of the active domain database state and related knowledge counts.",
        default_size="balanced",
        default_w=4,
        min_w=6,
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
    "admin.sync.overview.v1": _widget(
        widget_id="admin.sync.overview.v1",
        area="admin",
        category="sync",
        label="Sync overview",
        description="Distributed sync node state, links and operational summary.",
        default_size="balanced",
        default_w=4,
        default_h=1,
        data_adapter="admin.sync",
    ),
    "admin.sync.history.v1": _widget(
        widget_id="admin.sync.history.v1",
        area="admin",
        category="sync",
        label="Sync history",
        description="Recent distributed sync runs and queued jobs.",
        default_size="wide",
        default_w=8,
        min_w=8,
        default_h=1,
        data_adapter="admin.sync",
    ),
    "admin.sync.catalog.v1": _widget(
        widget_id="admin.sync.catalog.v1",
        area="admin",
        category="sync",
        label="Master domain catalog",
        description="Host-side adoption view for master-managed domains.",
        default_size="wide",
        default_w=8,
        min_w=6,
        default_h=1,
        data_adapter="admin.sync",
    ),
    "admin.sync.hosts.v1": _widget(
        widget_id="admin.sync.hosts.v1",
        area="admin",
        category="sync",
        label="Known hosts",
        description="Master-side host registry with recent node presence.",
        default_size="wide",
        default_w=8,
        min_w=8,
        default_h=1,
        data_adapter="admin.sync",
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


def canonical_widget_id(widget_id: str) -> str:
    """Return the canonical widget id for a canonical or legacy widget identifier."""
    spec = widget_by_id(widget_id)
    return spec.widget_id if spec is not None else str(widget_id)


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


def layout_positions_for_widgets(
    widget_ids: Iterable[str],
    *,
    columns: int = 12,
    widths: dict[str, int] | None = None,
) -> Dict[str, Dict[str, int]]:
    return _widgetkit_layout_positions(
        widget_ids, widget_by_id=widget_by_id, columns=columns, widths=widths,
    )


def default_widget_ids_for_area(area: str | None = None, subpage: str | None = None) -> List[str]:
    """Return the canonical widget ids for a known area-specific layout.

    These are the seed layouts used when a page/area has not yet been explicitly
    configured by a user. They intentionally reuse existing widgets from the
    registry instead of inventing new page-specific identifiers.
    """
    area_key = (area or "dashboard").strip().lower()
    subpage_key = (subpage or "").strip().lower()
    defaults: Dict[str, List[str]] = {
        "dashboard": frontpage_aggregate_widgets(),
        "datasources": [
            "datasources.overview.summary.v1",
            "datasources.import.quick.v1",
            "datasources.sources.discovery.v1",
            "datasources.mix.overview.v1",
            "datasources.markdown.files.v1",
            "datasources.ontology.overview.v1",
            "datasources.jobs.recent.v1",
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
            "admin.domain.create.v1",
            "admin.domain.db.overview.v1",
            "admin.system.status.v1",
            "admin.sync.overview.v1",
            "admin.sync.history.v1",
            "admin.sync.catalog.v1",
            "admin.sync.hosts.v1",
            "admin.workspace.config.v1",
        ],
        "settings": [
            "settings.layout.registry.v1",
            "settings.config.summary.v1",
            "settings.layout.preview.v1",
        ],
    }
    subpage_defaults: Dict[tuple[str, str], List[str]] = {
        ("admin", "domains"): [
            "admin.domain.management.v1",
            "admin.domain.create.v1",
            "admin.domain.db.overview.v1",
            "admin.workspace.config.v1",
        ],
        ("admin", "sync"): [
            "admin.sync.overview.v1",
            "admin.sync.history.v1",
            "admin.sync.catalog.v1",
            "admin.sync.hosts.v1",
        ],
        ("admin", "status"): [
            "admin.system.status.v1",
            "admin.workspace.config.v1",
        ],
        ("knowledge", "semantic"): [
            "knowledge.semantic.overview.v1",
            "knowledge.semantic.monitor.v1",
            "knowledge.semantic.quick.v1",
            "knowledge.graph.overview.v1",
            "knowledge.tools.summary.v1",
        ],
        ("knowledge", "records"): [
            "knowledge.records.summary.v1",
            "knowledge.overview.summary.v1",
            "knowledge.tools.summary.v1",
        ],
        ("knowledge", "artifacts"): [
            "knowledge.artifacts.summary.v1",
            "knowledge.overview.summary.v1",
            "knowledge.tools.summary.v1",
        ],
        ("knowledge", "jobs"): [
            "knowledge.jobs.recent.v1",
            "knowledge.tools.summary.v1",
        ],
        ("knowledge", "api"): [
            "knowledge.api.browser.v1",
            "knowledge.tools.summary.v1",
        ],
        ("infooutput", "infosite-dashboard"): [
            "infooutput.infosite.stats.v1",
            "infooutput.infosite.projects.v1",
            "infooutput.infosite.workflow.import.v1",
            "infooutput.infosite.workflow.refine.v1",
        ],
        ("infooutput", "quiz"): [
            "infooutput.quiz.overview.v1",
            "infooutput.quiz.status.v1",
        ],
        ("datasources", "sources"): [
            "datasources.sources.list.v1",
            "datasources.sources.unimported.v1",
        ],
        ("datasources", "workspace"): [
            "datasources.markdown.files.v1",
            "datasources.mix.overview.v1",
        ],
        ("datasources", "pdf"): [
            "datasources.jobs.recent.v1",
            "datasources.import.quick.v1",
        ],
        ("settings", "config"): [
            "settings.config.summary.v1",
            "settings.layout.preview.v1",
        ],
        ("settings", "shells"): [
            "settings.layout.preview.v1",
            "settings.layout.registry.v1",
        ],
    }
    if subpage_key:
        resolved = subpage_defaults.get((area_key, subpage_key))
        if resolved is not None:
            return list(resolved)
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

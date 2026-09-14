from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class WidgetContext:
    widget_id: str
    label: str
    description: str
    stats: list[dict[str, str]]
    rows: list[dict[str, str]]
    links: list[dict[str, str]]
    body: str = ""


@dataclass(frozen=True)
class WidgetKitConfig:
    template_dir: Path | None = None
    autoescape: bool = True
    trim_blocks: bool = True
    lstrip_blocks: bool = True


@dataclass(frozen=True)
class DataSourceSpec:
    source_id: str
    source_type: str = "table"
    label: str = ""
    description: str = ""
    rows: tuple[dict[str, Any], ...] = ()
    stats: tuple[tuple[str, str], ...] = ()
    links: tuple[tuple[str, str], ...] = ()
    detail_url_template: str = ""


WidgetAdapter = Callable[[Any], dict[str, Any]]


@dataclass(frozen=True)
class WidgetSpec:
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


class TableDataSourceAdapter:
    """Normalize flat table-like data into the widget payload contract.

    The adapter accepts either a ``DataSourceSpec`` or a raw table-like object and
    produces a widget payload with the same shape used by the UI: ``stats``,
    ``rows`` and ``links``. This keeps widget rendering source-agnostic while
    allowing future adapters for JSON, REST or queryset sources.
    """

    key = "table"

    def __call__(self, source: Any) -> dict[str, Any]:
        return self.adapt(source)

    @staticmethod
    def _pair_to_mapping(item: Any) -> dict[str, str]:
        if isinstance(item, Mapping):
            return {str(k): str(v) for k, v in item.items()}
        if isinstance(item, Sequence) and not isinstance(item, (str, bytes, bytearray)) and len(item) == 2:
            left, right = item
            return {"label": str(left), "value": str(right)}
        return {"label": str(item), "value": ""}

    def _normalize_stats(self, stats: Any) -> list[dict[str, str]]:
        if stats is None:
            return []
        if isinstance(stats, Mapping):
            stats = [stats]
        normalized: list[dict[str, str]] = []
        for item in stats:
            raw = self._pair_to_mapping(item)
            label = raw.get("label", raw.get("name", ""))
            value = raw.get("value", raw.get("count", ""))
            if label or value:
                normalized.append({"label": str(label), "value": str(value)})
        return normalized

    def _normalize_rows(self, rows: Any, *, detail_url_template: str = "") -> list[dict[str, str]]:
        if rows is None:
            return []
        if isinstance(rows, Mapping):
            rows = [rows]
        normalized: list[dict[str, str]] = []
        for item in rows:
            raw = self._pair_to_mapping(item)
            label = raw.get("label", raw.get("title", raw.get("name", "")))
            value = raw.get("value", raw.get("status", raw.get("count", "")))
            url = raw.get("url", raw.get("href", ""))
            if not url and detail_url_template:
                route_key = raw.get("id", raw.get("slug", raw.get("key", raw.get("name", ""))))
                if route_key:
                    context = dict(raw)
                    context["id"] = route_key
                    context["slug"] = route_key
                    url = detail_url_template.format_map(context)
            row = {"label": str(label), "value": str(value)}
            if url:
                row["url"] = str(url)
            if label or value or url:
                normalized.append(row)
        return normalized

    def _normalize_links(self, links: Any) -> list[dict[str, str]]:
        if links is None:
            return []
        if isinstance(links, Mapping):
            links = [links]
        normalized: list[dict[str, str]] = []
        for item in links:
            raw = self._pair_to_mapping(item)
            label = raw.get("label", raw.get("title", ""))
            url = raw.get("url", raw.get("href", raw.get("value", "")))
            if label or url:
                normalized.append({"label": str(label), "url": str(url)})
        return normalized

    def adapt(self, source: Any, *, widget_id: str = "", label: str = "", description: str = "") -> dict[str, Any]:
        if isinstance(source, DataSourceSpec):
            spec = source
            widget_id = widget_id or spec.source_id
            label = label or spec.label or spec.source_id
            description = description or spec.description
            rows = spec.rows
            stats = spec.stats
            links = spec.links
            detail_url_template = spec.detail_url_template
        else:
            rows = source.get("rows") if isinstance(source, Mapping) else None
            stats = source.get("stats") if isinstance(source, Mapping) else None
            links = source.get("links") if isinstance(source, Mapping) else None
            detail_url_template = str(source.get("detail_url_template", "")) if isinstance(source, Mapping) else ""
            widget_id = widget_id or str(source.get("source_id", source.get("widget_id", "table"))) if isinstance(source, Mapping) else widget_id or "table"
            label = label or str(source.get("label", "Table")) if isinstance(source, Mapping) else label or "Table"
            description = description or str(source.get("description", "")) if isinstance(source, Mapping) else description

        payload = empty_payload(widget_id or "table", label or "Table", description or "")
        payload["stats"] = self._normalize_stats(stats)
        payload["rows"] = self._normalize_rows(rows, detail_url_template=detail_url_template)
        payload["links"] = self._normalize_links(links)
        return payload


def empty_payload(widget_id: str, label: str, description: str) -> dict[str, Any]:
    return {"widget_id": widget_id, "label": label, "description": description, "stats": [], "rows": [], "links": []}


def payload_context(payload: dict[str, Any]) -> WidgetContext:
    return WidgetContext(
        widget_id=str(payload.get("widget_id", "")),
        label=str(payload.get("label", "")),
        description=str(payload.get("description", "")),
        stats=list(payload.get("stats", [])),
        rows=list(payload.get("rows", [])),
        links=list(payload.get("links", [])),
        body=str(payload.get("body", "")),
    )

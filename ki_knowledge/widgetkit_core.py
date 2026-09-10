from __future__ import annotations

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

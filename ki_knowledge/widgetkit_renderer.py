from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .widgetkit_core import WidgetKitConfig, payload_context


DEFAULT_TEMPLATE_DIR = Path(__file__).resolve().parent / "widgetkit_templates"


def create_environment(config: WidgetKitConfig | None = None) -> Environment:
    config = config or WidgetKitConfig(template_dir=DEFAULT_TEMPLATE_DIR)
    return Environment(
        loader=FileSystemLoader(str(config.template_dir or DEFAULT_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("html", "xml")) if config.autoescape else False,
        trim_blocks=config.trim_blocks,
        lstrip_blocks=config.lstrip_blocks,
    )


def render_card(payload: dict[str, Any], *, config: WidgetKitConfig | None = None) -> str:
    template = create_environment(config).get_template("card.html")
    return template.render(widget=payload_context(payload))


def render_fragment(name: str, context: dict[str, Any], *, config: WidgetKitConfig | None = None) -> str:
    template = create_environment(config).get_template(f"{name}.html")
    return template.render(**context)

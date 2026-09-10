from __future__ import annotations

from typing import Any

from .widgetkit_core import WidgetKitConfig
from .widgetkit_renderer import render_card, render_fragment


def render_widget(payload: dict[str, Any], *, config: WidgetKitConfig | None = None) -> str:
    return render_card(payload, config=config)

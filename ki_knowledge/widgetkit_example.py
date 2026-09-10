from __future__ import annotations

from .widgetkit_core import empty_payload
from .widgetkit_integration import register_integration_adapter
from .widgetkit_renderer import render_card


@register_integration_adapter("example.card")
def _example_card(spec):
    payload = empty_payload(spec.widget_id, spec.label, spec.description)
    payload["rows"] = [{"label": "Status", "value": "ok"}]
    payload["links"] = [{"label": "Docs", "url": "https://example.invalid/widgetkit"}]
    return payload


def render_example_card() -> str:
    return render_card(
        {
            "widget_id": "example.card",
            "label": "WidgetKit example",
            "description": "Minimal public API smoke test.",
            "rows": [{"label": "Mode", "value": "standalone"}],
            "links": [{"label": "Docs", "url": "https://example.invalid/widgetkit"}],
            "stats": [{"label": "Example", "value": "yes"}],
        }
    )

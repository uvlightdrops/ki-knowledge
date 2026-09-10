from __future__ import annotations

from .widgetkit_core import WidgetSpec
from .widgetkit_example import render_example_card


def example_widget_spec() -> WidgetSpec:
    return WidgetSpec(
        widget_id="example.card",
        area="example",
        category="smoke",
        label="WidgetKit example",
        description="Standalone smoke-test widget.",
        data_adapter="example.card",
    )


__all__ = ["example_widget_spec", "render_example_card"]

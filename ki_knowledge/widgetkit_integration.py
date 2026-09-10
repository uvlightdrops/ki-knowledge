from __future__ import annotations

from typing import Any

from .widgetkit_core import WidgetAdapter
from .widgetkit_registry import register_adapter, resolve_adapter


register_integration_adapter = register_adapter


def resolve_integration_adapter(key: str, default: WidgetAdapter) -> WidgetAdapter:
    return resolve_adapter(key, default)


__all__ = ["register_integration_adapter", "resolve_integration_adapter"]

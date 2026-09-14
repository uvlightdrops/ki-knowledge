from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .widgetkit_core import TableDataSourceAdapter

AdapterFactory = Callable[[Any], dict[str, Any]]
DataSourceAdapter = Callable[[Any], dict[str, Any]]

ADAPTERS: dict[str, AdapterFactory] = {}
DATA_SOURCE_ADAPTERS: dict[str, DataSourceAdapter] = {}


def register_adapter(key: str) -> Callable[[AdapterFactory], AdapterFactory]:
    def decorator(func: AdapterFactory) -> AdapterFactory:
        ADAPTERS[key] = func
        return func

    return decorator


def resolve_adapter(key: str, default: AdapterFactory) -> AdapterFactory:
    return ADAPTERS.get(key, default)


def register_data_source_adapter(key: str) -> Callable[[DataSourceAdapter], DataSourceAdapter]:
    def decorator(func: DataSourceAdapter) -> DataSourceAdapter:
        DATA_SOURCE_ADAPTERS[key] = func
        return func

    return decorator


def resolve_data_source_adapter(key: str, default: DataSourceAdapter) -> DataSourceAdapter:
    return DATA_SOURCE_ADAPTERS.get(key, default)


def clear_adapters() -> None:
    ADAPTERS.clear()
    DATA_SOURCE_ADAPTERS.clear()


register_data_source_adapter("table")(TableDataSourceAdapter())

__all__ = [
    "ADAPTERS",
    "DATA_SOURCE_ADAPTERS",
    "clear_adapters",
    "register_adapter",
    "register_data_source_adapter",
    "resolve_adapter",
    "resolve_data_source_adapter",
]

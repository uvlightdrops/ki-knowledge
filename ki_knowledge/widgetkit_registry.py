from __future__ import annotations

from collections.abc import Callable
from typing import Any

AdapterFactory = Callable[[Any], dict[str, Any]]

ADAPTERS: dict[str, AdapterFactory] = {}


def register_adapter(key: str) -> Callable[[AdapterFactory], AdapterFactory]:
    def decorator(func: AdapterFactory) -> AdapterFactory:
        ADAPTERS[key] = func
        return func

    return decorator


def resolve_adapter(key: str, default: AdapterFactory) -> AdapterFactory:
    return ADAPTERS.get(key, default)


def clear_adapters() -> None:
    ADAPTERS.clear()


__all__ = ["ADAPTERS", "clear_adapters", "register_adapter", "resolve_adapter"]

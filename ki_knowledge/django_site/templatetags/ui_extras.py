from __future__ import annotations

from pathlib import Path

from django import template

register = template.Library()


@register.filter
def short_id(value: object, max_len: int = 44) -> str:
    text = str(value or "")
    if len(text) <= max_len:
        return text
    keep = max(10, int(max_len) // 2 - 2)
    return f"{text[:keep]}…{text[-keep:]}"


@register.filter
def basename(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return Path(text).name

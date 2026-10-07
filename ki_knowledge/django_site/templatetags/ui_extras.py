from __future__ import annotations

from pathlib import Path

from django import template
from ki_knowledge.django_site.layout_targets import layout_builder_url as build_layout_builder_url

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


@register.simple_tag
def layout_builder_url(area_key: str, subpage_key: str = "overview") -> str:
    return build_layout_builder_url(area_key, subpage_key)

import json
from importlib.resources import files

from django import template
from django.core.exceptions import ImproperlyConfigured

register = template.Library()


@register.simple_tag
def workbench_assets():
    manifest = files("ki_knowledge.django_site").joinpath(
        "static/django_site/workbench/manifest.json",
    )
    if not manifest.is_file():
        raise ImproperlyConfigured(
            "Workbench assets missing. Run npm ci && npm run build in frontend/workbench.",
        )
    entries = json.loads(manifest.read_text(encoding="utf-8"))
    entry = entries["src/main.tsx"]
    prefix = "django_site/workbench/"
    return {
        "script": prefix + entry["file"],
        "styles": [prefix + path for path in entry.get("css", [])],
    }

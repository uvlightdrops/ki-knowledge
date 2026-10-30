"""Project ownership and activation boundaries for the shared settings UI."""

from pathlib import Path

from django.urls import reverse
from ki_core.runtime_settings import RuntimeSettings
from widgetkit_django.runtime_settings import runtime_settings_view

from .config_editor import DB_OWNED_FIELDS
from .layout_targets import layout_builder_url


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESTART_PATHS = (
    "apps.ki_knowledge.django",
    "apps.ki_knowledge.distributed.postgres_dsn",
    "knowledge.data_root",
    "knowledge.cache_db",
    "knowledge.graph_db",
    "knowledge.paths",
    "knowledge.embed_model",
    "jira.cache_db",
    "jira.graph_db",
    "jira.embed_model",
)
EXCLUDED_PATHS = tuple(path for path, _owner in DB_OWNED_FIELDS) + (
    "apps.ki_knowledge.distributed.node_id",
)


def build_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        PROJECT_ROOT,
        restart_paths=RESTART_PATHS,
        excluded_paths=EXCLUDED_PATHS,
    )


def settings_config_view(request, *, compact=False):
    return runtime_settings_view(
        request,
        service=build_runtime_settings(),
        base_template="base.html",
        title="C2 · Konfiguration" if compact else "Live-Konfiguration",
        compact=compact,
        context={
            "configuration_url": reverse("settings-config"),
            "ownership_links": [
                {
                    "url": reverse("admin-sync"),
                    "label": "NodeConfig: Rolle, Master-URL, Aktivierung und Sync",
                },
                {
                    "url": layout_builder_url("settings", "overview"),
                    "label": "Widget-Layouts im Dashboard Builder",
                },
            ],
        },
    )


def settings_config_compact_view(request):
    return settings_config_view(request, compact=True)

"""Settings editor for the sync/remote-collaboration YAML fields.

Project adapter around ``yaml_cfg_wizard.editor`` (core) and
``yaml_cfg_wizard.django`` (optional Django adapter). Only a small allowlist of
non-secret, non-DB-owned fields is editable, and only in one known
project-owned file: the host-local runtime layer
``config/runtime/runtime.yaml`` (gitignored, highest YAML layer of ki-core).

Fields that ``NodeConfig`` (DB) overrides at runtime are deliberately *not*
editable here; they stay owned by the sync admin (``/admin-overview/sync/``).
Without the optional adapter the page is read-only.
"""

from __future__ import annotations

import logging
import os
import re
from functools import wraps
from pathlib import Path
from typing import Any, Mapping, Optional, Union
from urllib.parse import urlsplit

import yaml
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponseNotAllowed
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods

TEMPLATE_NAME = "kicli_django/settings_config_sync.html"
logger = logging.getLogger(__name__)
RUNTIME_FILE_ID = "runtime"

_DISTRIBUTED = "apps.ki_knowledge.distributed"
PUBLIC_URL_PATH = f"{_DISTRIBUTED}.public_url"
FEDERATION_ID_PATH = f"{_DISTRIBUTED}.federation_id"

# (path, label, description) - the complete allowlist. Neither field is read
# from NodeConfig: both are taken from the resolved YAML config only.
EDITABLE_FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        PUBLIC_URL_PATH,
        "Öffentliche Node-URL",
        "Eigene erreichbare URL dieses Nodes (http/https, ohne Zugangsdaten, Query oder Fragment); "
        "wird im Node-Descriptor und in Heartbeats angekündigt.",
    ),
    (
        FEDERATION_ID_PATH,
        "Federation-ID",
        "Nur Heartbeats von Nodes derselben Federation werden akzeptiert. Leer bedeutet 'default'.",
    ),
)

# YAML keys that NodeConfig (DB) overrides once a row for the local node
# exists (see distributed_api.get_runtime_node_settings). Shown as
# explanation only, never editable here.
DB_OWNED_FIELDS: tuple[tuple[str, str], ...] = (
    (f"{_DISTRIBUTED}.node_role", "NodeConfig.role"),
    (f"{_DISTRIBUTED}.enabled", "NodeConfig.is_enabled"),
    (f"{_DISTRIBUTED}.sync_on_connect", "NodeConfig.sync_on_connect"),
    (f"{_DISTRIBUTED}.master_url", "NodeConfig.base_url (Host-Rolle)"),
    (f"{_DISTRIBUTED}.sync_shared_secret", "NodeConfig.sync_shared_secret (Secret)"),
)

# Strict shape for URL fields: optional, http(s), host[:port], optional path;
# no userinfo (credentials), whitespace, query or fragment.
SAFE_URL_PATTERN = r"^$|^https?://[A-Za-z0-9.\-]+(:[0-9]{1,5})?(/[^\s@?#]*)?$"
SAFE_URL_FIELDS = frozenset({PUBLIC_URL_PATH})


def is_safe_url(value: Any) -> bool:
    """True for empty or credential-free http(s) URLs matching SAFE_URL_PATTERN."""
    if value in (None, ""):
        return True
    if not isinstance(value, str) or not re.fullmatch(SAFE_URL_PATTERN, value):
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return not (parts.username or parts.password or "@" in parts.netloc)


def display_value(value: Any, path: str) -> str:
    """Render a row value; URL fields with unsafe content are never shown."""
    if value is None:
        return "—"
    if path in SAFE_URL_FIELDS and not is_safe_url(value):
        return "(verborgen: ungültige oder zugangsdatenhaltige URL)"
    if value == "":
        return '""'
    return str(value)


# --- target file ------------------------------------------------------------------


def runtime_target(path: Optional[Union[str, Path]] = None) -> Optional[Path]:
    """The project-owned runtime layer file, or None if it is not project-owned.

    Same location ki-core reads (``<config dir>/runtime/runtime.yaml``), but
    only accepted below the current project working directory and never via a
    symlink, so the editor cannot be pointed at arbitrary files.
    """
    from ki_core.config import _layered_config_dir

    target = _layered_config_dir(path) / "runtime" / "runtime.yaml"
    project_root = Path.cwd().resolve()
    absolute = target if target.is_absolute() else Path.cwd() / target
    for candidate in (absolute, *absolute.parents):
        if candidate.is_symlink():
            return None
    try:
        absolute.resolve().relative_to(project_root)
    except ValueError:
        return None
    return absolute


# --- resolution -------------------------------------------------------------------


def _safe_validation_error(message: str) -> Exception:
    try:
        from yaml_cfg_wizard.editor import ValidationError

        return ValidationError(message)
    except ImportError:  # pragma: no cover - core not installed
        return ValueError(message)


def resolve_candidate(
    file_id: str, candidate: Mapping[str, Any], path: Optional[Union[str, Path]] = None
) -> dict[str, Any]:
    """Full effective config with the runtime layer replaced by ``candidate``.

    Mirrors ``ki_core.config._resolve_config`` step by step (defaults dir,
    ki.yaml, profile, stage, runtime, ``KI_CFG_*`` env, base-schema check,
    creds.yaml, merged-schema defaults). The runtime layer is *replaced* by the
    candidate, not merged onto the effective result, so removed keys fall back
    to lower layers and higher layers (env, creds) still win. Credentials are
    loaded internally like at runtime; callers only ever expose allowlisted
    fields.
    """
    if file_id != RUNTIME_FILE_ID:
        raise KeyError(file_id)
    if not isinstance(candidate, Mapping):
        raise _safe_validation_error("runtime layer must be a mapping")

    from jsonschema import Draft7Validator
    from ki_core import config as kc
    from yaml_cfg_wizard import ConfigResolver, deep_merge
    from yaml_cfg_wizard.core import env_to_dict, load_directory_yaml, load_yaml_files
    from yaml_cfg_wizard.schema_utils import merge_schemas, scaffold_skeleton_from_schema

    config_path = kc._find_yaml_config_path(path)
    creds_path = kc._find_creds_yaml_path(path)
    layered = kc._layered_config_dir(path)
    stage_file = kc._layer_file(layered / "stages", kc.STAGE_ENV, kc.ACTIVE_STAGE_MARKER)
    profile_file = kc._layer_file(layered / "profiles", kc.PROFILE_ENV, kc.ACTIVE_PROFILE_MARKER)
    schemas = kc.get_merged_schemas()

    # Same order as yaml_cfg_wizard.ConfigResolver.resolve() with ki-core's arguments.
    merged: dict[str, Any] = {}
    if (layered / "defaults").exists():
        merged = deep_merge(merged, load_directory_yaml(layered / "defaults"))
    merged = deep_merge(merged, load_yaml_files([config_path] if config_path else []))
    merged = deep_merge(merged, load_yaml_files([profile_file] if profile_file else []))
    merged = deep_merge(merged, load_yaml_files([stage_file] if stage_file else []))
    merged = deep_merge(merged, dict(candidate))
    merged = deep_merge(merged, env_to_dict("KI_CFG_"))
    if schemas:
        import yaml

        base_schema = yaml.safe_load(Path(schemas[0]).read_text(encoding="utf-8"))
        if any(True for _ in Draft7Validator(base_schema).iter_errors(merged)):
            # never echo jsonschema messages: they contain the offending values
            raise _safe_validation_error("candidate violates the base config schema")

    if creds_path:
        try:
            creds_payload = ConfigResolver(defaults=[creds_path], schema_file=schemas[0] if schemas else None).resolve()
        except ValueError:
            raise _safe_validation_error("creds.yaml violates the base config schema") from None
        if isinstance(creds_payload, dict):
            merged = deep_merge(merged, creds_payload)

    schema_defaults = scaffold_skeleton_from_schema(merge_schemas(*schemas)) if schemas else {}
    return deep_merge(schema_defaults, merged)


def editor_schema() -> dict[str, Any]:
    """Merged ki-core + app schema, plus the safe-URL constraint for URL fields."""
    import copy

    from ki_core.config import get_merged_schemas
    from yaml_cfg_wizard.schema_utils import merge_schemas

    schema = copy.deepcopy(merge_schemas(*get_merged_schemas()))
    for dotted in SAFE_URL_FIELDS:
        node: dict[str, Any] = schema
        for part in dotted.split("."):
            node = node.setdefault("properties", {}).setdefault(part, {})
        node["type"] = "string"
        node["pattern"] = SAFE_URL_PATTERN
    return schema


# --- editor -----------------------------------------------------------------------


def build_editor(path: Optional[Union[str, Path]] = None):
    """Editor for the runtime layer, or None if core or target are unavailable."""
    try:
        from yaml_cfg_wizard.editor import Editor, Field
    except ImportError:
        return None
    target = runtime_target(path)
    if target is None:
        return None
    return Editor(
        files={RUNTIME_FILE_ID: target},
        fields=[Field(path=p, label=label, description=desc) for p, label, desc in EDITABLE_FIELDS],
        resolve=lambda file_id, candidate: resolve_candidate(file_id, candidate, path),
        schema=editor_schema(),
    )


def _load_render_editor():
    try:
        from yaml_cfg_wizard.django import render_editor
    except ImportError:
        return None
    return render_editor


def _get_path(data: Any, dotted: str) -> tuple[bool, Any]:
    current = data
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return False, None
        current = current[part]
    return True, current


def readonly_rows(path: Optional[Union[str, Path]] = None) -> list[dict[str, Any]]:
    """Rows without the editor core: allowlisted fields only, same row shape."""
    from yaml_cfg_wizard.core import load_yaml_file

    target = runtime_target(path)
    layer = load_yaml_file(target) if target is not None else {}
    effective = resolve_candidate(RUNTIME_FILE_ID, layer, path)
    rows = []
    for field_path, label, description in EDITABLE_FIELDS:
        overridden, override = _get_path(layer, field_path)
        _found, value = _get_path(effective, field_path)
        rows.append(
            {
                "path": field_path,
                "label": label,
                "description": description,
                "overridden": overridden,
                "override": override if overridden else None,
                "effective": value,
            }
        )
    return rows


# --- view -------------------------------------------------------------------------


def superuser_required(view):
    """Config files are host-wide: only active superusers may view or edit."""

    @wraps(view)
    def wrapped(request: HttpRequest, *args, **kwargs):
        user = getattr(request, "user", None)
        if not (user is not None and user.is_authenticated and user.is_active and user.is_superuser):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapped


def _base_context(target: Optional[Path]) -> dict[str, Any]:
    return {
        "file_id": RUNTIME_FILE_ID,
        "target_path": str(target) if target is not None else None,
        "db_owned_fields": DB_OWNED_FIELDS,
        "env_override_hint": any(k.startswith("KI_CFG_APPS__KI_KNOWLEDGE__DISTRIBUTED__") for k in os.environ),
    }


@never_cache
@superuser_required
@csrf_protect
@require_http_methods(["GET", "POST"])
def settings_config_sync_view(request: HttpRequest):
    target = runtime_target()
    context = _base_context(target)
    editor = build_editor()
    render_editor = _load_render_editor()
    if editor is not None and render_editor is not None:
        return render_editor(request, editor, TEMPLATE_NAME, context={**context, "editable": True})

    # Optional adapter (or core) missing -> read-only.
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])
    error = None
    rows: list[dict[str, Any]] = []
    try:
        rows = editor.snapshot(RUNTIME_FILE_ID).rows if editor is not None else readonly_rows()
    except (OSError, ValueError, yaml.YAMLError):
        logger.warning("Read-only sync configuration could not be resolved.")
        error = "Konfiguration konnte nicht aufgelöst werden."
    return render(
        request if error is None else None,
        TEMPLATE_NAME,
        {
            **context,
            "editable": False,
            "rows": rows,
            "snapshot": None,
            "files": {RUNTIME_FILE_ID: str(target)} if target is not None else {},
            "error": error,
            "saved": False,
        },
        status=400 if error is not None else 200,
    )

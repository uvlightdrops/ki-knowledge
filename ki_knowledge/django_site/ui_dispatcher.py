from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from django.conf import settings

from ki_knowledge.api.app import _get_components, _semantic_model_id
from ki_knowledge.django_site.domain_paths import default_semantic_domain, normalize_semantic_domain
from ki_knowledge.django_site.jira_workflow import (
    jira_cache_db_path,
    jira_domain_terms,
    jira_graph_db_path,
    jira_reimport_data,
    jira_reset_data,
)
from ki_knowledge.django_site.knowledge_summary import (
    domain_knowledge_summary,
    knowledge_base_clear_domain_artifacts,
    knowledge_base_reset_all,
    knowledge_base_reset_domain,
    semantic_store,
)
from ki_knowledge.django_site.jira_workflow import domain_db_paths
from ki_knowledge.integrations.semantic_terms import SemanticEnrichmentService


@contextmanager
def _domain_env(domain: str | None):
    paths = domain_db_paths(domain)
    cache_path = str(paths["cache_db"])
    graph_path = str(paths["graph_db"])
    cypher_path = str(paths["cypher_path"]) if paths.get("cypher_path") else ""
    previous = {k: os.environ.get(k) for k in ("JIRA_CACHE_DB", "JIRA_GRAPH_DB", "JIRA_GRAPH_CYPHER_PATH")}
    os.environ["JIRA_CACHE_DB"] = cache_path
    os.environ["JIRA_GRAPH_DB"] = graph_path
    if cypher_path:
        os.environ["JIRA_GRAPH_CYPHER_PATH"] = cypher_path
    elif "JIRA_GRAPH_CYPHER_PATH" in os.environ:
        del os.environ["JIRA_GRAPH_CYPHER_PATH"]
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _candidate_record_ids_for_semantic_linking(limit: int = 1200, min_len: int = 40) -> list[str]:
    records = semantic_store().list_records(limit=limit)
    allowed_types = {"paragraph", "list_item", "code_block", "quote", "heading"}
    ids: list[str] = []
    for item in records:
        if item.block_type not in allowed_types:
            continue
        content = (item.content or "").strip()
        if len(content) < min_len:
            continue
        ids.append(item.block_id)
    return ids


def run_dashboard_task(task_name: str, *, domain: str | None = None, target_domain: str | None = None) -> dict[str, Any]:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    if task_name == "domain_switch":
        return {"task": task_name, "domain": resolved_domain}

    if task_name == "domain_create":
        from ki_knowledge.django_site.services import create_semantic_domain
        result = create_semantic_domain(target_domain or resolved_domain)
        return {"task": task_name, **result}

    if task_name == "domain_delete":
        from ki_knowledge.django_site.services import delete_semantic_domain
        deleted = delete_semantic_domain(target_domain)
        return {"task": task_name, **deleted}

    if task_name == "kb_reset_domain":
        target = normalize_semantic_domain(target_domain or domain or resolved_domain)
        result = knowledge_base_reset_domain(target)
        return {"task": task_name, "domain": target, **result}

    if task_name == "kb_clear_artifacts_domain":
        target = normalize_semantic_domain(target_domain or domain or resolved_domain)
        result = knowledge_base_clear_domain_artifacts(target)
        return {"task": task_name, "domain": target, **result}

    if task_name == "kb_reset_all":
        result = knowledge_base_reset_all()
        return {"task": task_name, **result}

    if task_name == "jira_reset":
        result = jira_reset_data(resolved_domain)
        return {"task": task_name, "domain": resolved_domain, **result}

    if task_name == "jira_reimport":
        result = jira_reimport_data(resolved_domain)
        return {"task": task_name, "domain": resolved_domain, **result}

    store_obj = semantic_store(resolved_domain)
    if task_name == "semantic_extract_promote":
        terms = jira_domain_terms(limit=300, min_count=2, domain=resolved_domain)
        candidates = store_obj.store_domain_candidates(terms)
        promoted = store_obj.promote_candidates(limit=300)
        return {"task": task_name, "domain": resolved_domain, "candidates": candidates, "promoted": promoted}

    if task_name == "semantic_enqueue":
        enqueued = store_obj.enqueue_jobs(job_type="definition", only_status="new", limit=200)
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued}

    if task_name == "semantic_run":
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
        )
        result = service.run_batch(batch_size=20)
        return {"task": task_name, "domain": resolved_domain, **result}

    if task_name == "semantic_refine_enqueue":
        enqueued = store_obj.enqueue_refinement_jobs(
            limit=100,
            min_facts=2,
            min_relations=1,
            min_confidence=0.65,
            job_type="refine",
        )
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued}

    if task_name == "semantic_refine_run":
        enqueued = store_obj.enqueue_refinement_jobs(
            limit=100,
            min_facts=2,
            min_relations=1,
            min_confidence=0.65,
            job_type="refine",
        )
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
        )
        result = service.run_batch(batch_size=20)
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued, **result}

    if task_name == "semantic_fields_rebuild":
        with _domain_env(resolved_domain):
            cache, _, assistant = _get_components()
        backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
        embedded = cache.build_field_embeddings(backend=backend, embedding_model=embedding_model)
        return {
            "task": task_name,
            "domain": resolved_domain,
            "embedded_fields": embedded,
            "embedding_model": embedding_model,
        }

    if task_name == "semantic_records_enqueue":
        record_ids = _candidate_record_ids_for_semantic_linking()
        enqueued = store_obj.enqueue_record_link_jobs(record_ids, job_type="record_terms")
        return {"task": task_name, "domain": resolved_domain, "records": len(record_ids), "enqueued": enqueued}

    if task_name == "semantic_records_run":
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
            knowledge_db_path=str(settings.KNOWLEDGE_DB_PATH),
        )
        result = service.run_batch(batch_size=30, job_types=("record_terms",))
        return {"task": task_name, "domain": resolved_domain, **result}

    raise ValueError(f"unsupported dashboard task: {task_name}")


def _field_embedding_backend(cache: Any, assistant: Any):
    if assistant is None:
        return None, ""
    backend = getattr(assistant, "embedding_backend", None)
    if backend is not None:
        return backend, getattr(assistant, "embedding_model", "")
    if cache is not None:
        return None, ""
    return None, ""


def resolve_ui_action(
    action: str,
    *,
    request: Any | None = None,
    area_key: str = "settings",
    widget_id: str | None = None,
    widget_order: list[str] | None = None,
    widget_sizes: dict[str, int] | None = None,
) -> list[str]:
    """Resolve UI form/button actions via the central dispatcher contract.

    These actions are intentionally distinct from the semantic task names used in
    the dashboard background pipeline. They map the interactive UI actions of the
    builder/editor (add/remove/reset/reorder) to the persisted layout state.
    """
    from ki_knowledge.django_site.dashboard_registry import layout_positions_for_widgets, widget_by_id
    from ki_knowledge.django_site.infosite_models import DashboardDefinition, DashboardWidgetPlacement, ensure_domain_registered

    if request is None:
        return []

    active_domain = request.session.get("semantic_active_domain", "")
    if active_domain:
        domain = normalize_semantic_domain(str(active_domain))
    else:
        domain = normalize_semantic_domain(default_semantic_domain())
        request.session["semantic_active_domain"] = domain
        request.session.modified = True

    domain_obj = ensure_domain_registered(domain)
    if domain_obj is None:
        return []

    owner = request.user if getattr(request.user, "is_authenticated", False) else None
    dashboard, _ = DashboardDefinition.objects.get_or_create(
        owner=owner,
        domain=domain_obj,
        area_key=area_key,
        slug=f"{area_key}-{domain}",
        defaults={"title": f"{area_key.title()} dashboard for {domain}"},
    )

    selections = list(
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard)
        .order_by("sort_index", "widget_id")
        .values_list("widget_id", flat=True)
    )

    normalized_action = (action or "").strip()
    if normalized_action == "reset":
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard).delete()
        return []

    if normalized_action == "add" and widget_id:
        if widget_by_id(widget_id) is not None and widget_id not in selections:
            selections.append(widget_id)
            DashboardWidgetPlacement.objects.filter(dashboard=dashboard).delete()
            for index, selected_widget_id in enumerate(selections):
                position = layout_positions_for_widgets(selections)[selected_widget_id]
                width = widget_sizes.get(selected_widget_id, position["w"]) if widget_sizes else position["w"]
                width = max(3, min(int(width), 12))
                DashboardWidgetPlacement.objects.create(
                    dashboard=dashboard,
                    widget_id=selected_widget_id,
                    sort_index=index,
                    w=width,
                    h=position["h"],
                    x=position["x"],
                    y=position["y"],
                )
        return selections

    if normalized_action == "remove" and widget_id:
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard, widget_id=widget_id).delete()
        selections = list(
            DashboardWidgetPlacement.objects.filter(dashboard=dashboard)
            .order_by("sort_index", "widget_id")
            .values_list("widget_id", flat=True)
        )
        return selections

    if normalized_action == "save-order":
        ordered = widget_order or []
        valid_ids: list[str] = []
        seen: set[str] = set()
        for candidate in ordered:
            item = str(candidate).strip()
            if not item or item in seen or widget_by_id(item) is None:
                continue
            seen.add(item)
            valid_ids.append(item)
        DashboardWidgetPlacement.objects.filter(dashboard=dashboard).delete()
        for index, selected_widget_id in enumerate(valid_ids):
            position = layout_positions_for_widgets(valid_ids)[selected_widget_id]
            width = widget_sizes.get(selected_widget_id, position["w"]) if widget_sizes else position["w"]
            width = max(3, min(int(width), 12))
            DashboardWidgetPlacement.objects.create(
                dashboard=dashboard,
                widget_id=selected_widget_id,
                sort_index=index,
                w=width,
                h=position["h"],
                x=position["x"],
                y=position["y"],
            )
        return valid_ids

    return selections


__all__ = [
    "run_dashboard_task",
    "resolve_ui_action",
    "_domain_env",
    "_candidate_record_ids_for_semantic_linking",
]

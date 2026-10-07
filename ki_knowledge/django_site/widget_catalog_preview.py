"""Offline, read-only catalog examples. Never call live widget data adapters."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from types import SimpleNamespace
from typing import Any

from django.template.loader import render_to_string

from widgetkit_django.preview import PreviewResult, readonly_preview_html
from ..widgetkit_renderer import render_fragment


# These registrations currently render only their descriptions on real pages.
# Do not disguise a related widget's renderer as their implementation.
UNIMPLEMENTED_WIDGETS = frozenset({
    "datasources.source.list.v1",
    "datasources.ai.summary.v1",
    "datasources.markdown.files.v1",
    "datasources.ontology.overview.v1",
})


def catalog_active_domain(request: Any) -> str:
    """Resolve selection without the normal helper's automatic heartbeat."""
    from .services import normalize_semantic_domain

    selected = request.GET.get("domain", "").strip()
    if not selected:
        selected = str(getattr(request, "session", {}).get("semantic_active_domain", "")).strip()
    if not selected:
        selected = os.getenv("KNOWLEDGE_DEFAULT_DOMAIN", "").strip() or "default"
    return normalize_semantic_domain(selected)


def build_catalog_preview_context(active_domain: str) -> dict[str, Any]:
    """Build bounded sample data once per catalog request, with no I/O."""
    stamp = datetime(2026, 1, 15, 10, 30, tzinfo=timezone.utc)
    domain = {
        "slug": active_domain, "domain_key": active_domain,
        "display_name": active_domain, "is_active": True,
        "knowledge_sources": 2, "knowledge_records": 12,
        "infosite_project_count": 1, "infosite_source_count": 2,
        "total": 2, "approved": 1, "in_review": 1, "rejected": 0,
    }
    state = {
        "domain": active_domain, "domain_label": active_domain,
        "markdown_files": 3, "jira_csv_files": 1, "ontology_files": 1,
        "pdf_files": 2, "mix_files": 3,
        "mix_counts": {"table": 1, "image": 2},
        "has_md_source": True,
    }
    project = SimpleNamespace(
        id=1, title="Sample knowledge guide", domain=active_domain,
        working_title="Sample guide", generation_status="completed",
        enabled=True, last_generated=stamp,
        documents=SimpleNamespace(all=[1, 2]),
    )
    documents = [
        SimpleNamespace(
            display_path=f"sample-guide-{index}.md", project=project,
            project_id=project.id, review_status=status,
            get_review_status_display=lambda label=label: label,
        )
        for index, status, label in [(1, "approved", "Approved"), (2, "in_review", "In review")]
    ]
    rows = [
        {
            "source_id": "sample:guide", "title": "Sample Markdown guide",
            "kind": "markdown", "kind_label": "Markdown", "icon": "📝",
            "relative": "sample-guide.md", "folder": "md",
            "records": 8, "artifacts": 2, "updated_at": "2026-01-15",
            "can_reimport": True, "detail_url": "/knowledge/records/",
        },
        {
            "source_id": "sample:image", "title": "Sample diagram",
            "kind": "image", "kind_label": "Image", "icon": "🖼️",
            "relative": "sample-diagram.png", "folder": "mix",
            "records": 4, "artifacts": 1, "updated_at": "2026-01-15",
            "can_reimport": True, "image_processing": "ocr",
            "detail_url": "/knowledge/records/",
        },
    ]
    node = SimpleNamespace(
        node_id="sample-host", display_name="Sample host", role="host",
        distributed_enabled=True, sync_on_connect=False,
        base_url="https://host.example.invalid",
        master_url="https://master.example.invalid",
    )
    return {
        "active_domain": active_domain,
        "all_domains": [domain], "domain_rows": [domain],
        "domain_states": [state], "active_domain_state": state,
        "sources": rows, "markdown_count": 3, "owl_sources": 1,
        "pdf_jobs": {"pending": 1, "processing": 1, "done": 2, "failed": 0, "total": 4},
        "jira_issues": 5, "csrf_token": "",
        "scoped_knowledge": {"sources": 2, "records": 12, "artifacts": 3},
        "term_count": 6,
        "quick_links": [
            ("Records", "/knowledge/records/", "Browse sample knowledge records"),
            ("Artifacts", "/knowledge/artifacts/", "Browse sample derived artifacts"),
        ],
        "domain_stats": [domain], "domain_documents": documents,
        "recent_projects": [project], "infosite_projects": [project],
        "infosite_stats": {
            "total_projects": 1, "enabled_projects": 1,
            "total_documents": 2, "imported_documents": 2,
        },
        "formats": [
            {"label": "Infosite", "status": "available", "url": "/output/infosite/dashboard/",
             "description": "Sample Markdown presentations"},
            {"label": "Quiz", "status": "planned", "url": "",
             "description": "Not implemented yet"},
        ],
        "registered_domain_count": 1,
        "layout": {
            "data_root": "/sample/data",
            "active_markdown_dir": f"/sample/data/md/{active_domain}",
            "active_jira_dir": f"/sample/data/jira/{active_domain}",
        },
        "config_summary": {
            "active_area": "settings", "llm_provider": "Sample provider",
            "knowledge_root": "/sample/knowledge", "infosite_enabled": True,
        },
        "domain_management_url": "/admin-overview/domains/",
        "status_url": "/admin-overview/status/",
        "sync_admin_url": "/admin-overview/sync/",
        "local_node": node, "runtime_node": node,
        "sync_runs": [SimpleNamespace(
            direction="pull", status="completed",
            domain=SimpleNamespace(slug=active_domain), node=node, started_at=stamp,
        )],
        "sync_jobs": [SimpleNamespace(status="pending")],
        "master_domain_catalog": {
            "master_url": node.master_url, "domain_count": 1,
        },
        "master_domain_catalog_error": "", "known_hosts": [node],
        "rows": rows, "hidden": "", "base_url": "/data-sources/sources/",
        "action_url": "/data-sources/sources/action/",
        "generate_url": "/knowledge/artifacts/generate/",
        "kind": "", "display": "table", "query": "", "sort": "title",
        "sort_options": [("title", "Title"), ("updated", "Updated")],
        "chips": [
            {"key": "", "label": "All", "count": 2, "active": True, "href": "?"},
            {"key": "markdown", "label": "Markdown", "icon": "📝", "count": 1, "href": "?kind=markdown"},
            {"key": "image", "label": "Images", "icon": "🖼️", "count": 1, "href": "?kind=image"},
        ],
        "display_table_href": "?display=table", "display_cards_href": "?display=cards",
        "total_all": 2, "total": 2, "first_index": 1, "last_index": 2,
        "prev_href": "", "next_href": "", "unimported_new": 1,
        "pending": {
            "total": 2, "new": 1, "folders": [{
                "key": "pdf", "new": 1, "files": [
                    {"relative": "sample-new.pdf", "folder": "pdf", "kind": "pdf",
                     "icon": "📄", "status": "new"},
                    {"relative": "sample-queued.pdf", "folder": "pdf", "kind": "pdf",
                     "icon": "📄", "status": "queued"},
                ],
            }],
        },
        "max_files": 5, "ocr_missing": False,
    }


def render_catalog_widget(spec: Any, context: dict[str, Any]) -> PreviewResult:
    from .page_widgets import _widget_fragment_handlers

    widget_id = spec.widget_id
    handlers = _widget_fragment_handlers()
    status = "sample"
    note = ""
    if widget_id in UNIMPLEMENTED_WIDGETS:
        status = "unimplemented"
        note = "No dedicated renderer implemented."
        body = render_to_string("kicli_django/widgets/catalog_unimplemented.html", {
            "description": spec.description,
        })
    elif widget_id == "datasources.import.quick.v1":
        # The normal handler discovers real domain folders. Render its exact
        # template with bounded examples instead; do not resolve any paths.
        body = render_fragment("datasources_import_quick", {
            "active_domain": context["active_domain"], "csrf_token": "",
            "upload_accept": ".md,.pdf,.owl,.csv,.png", "any_files": True,
            "rows": [
                {"key": key, "label": label, "icon": icon, "files": count,
                 "imported": 1, "imported_unit": "Quellen", "can_import": True,
                 "folder": f"{key}/", "dir": f"/sample/{key}/{context['active_domain']}",
                 "formats": formats, "linked": False}
                for key, label, icon, count, formats in [
                    ("md", "Markdown", "📝", 3, ".md"),
                    ("pdf", "PDF", "📄", 2, ".pdf"),
                    ("owl", "Ontologie", "🕸️", 1, ".owl .ttl .rdf"),
                    ("jira", "Jira", "🎫", 1, "Jira-CSV"),
                    ("mix", "Mix", "🧩", 3, "Tabellen, Bilder"),
                ]
            ],
        })
    elif widget_id == "datasources.mix.overview.v1":
        body = render_fragment("datasources_mix_overview", {
            "mix": {"exists": True, "total": 3, "ocr_available": True},
            "mix_dir": f"/sample/mix/{context['active_domain']}",
            "mix_dir_display": f"/sample/mix/{context['active_domain']}",
            "counts": [("table", 1), ("image", 2)], "unsupported": 0,
            "csrf_token": "",
        })
    elif widget_id in {
        "datasources.sources.filter.v1", "datasources.sources.list.v1",
        "datasources.sources.unimported.v1",
    }:
        body = render_fragment({
            "datasources.sources.filter.v1": "sources_filter",
            "datasources.sources.list.v1": "sources_list",
            "datasources.sources.unimported.v1": "sources_unimported",
        }[widget_id], context)
    elif widget_id == "admin.workspace.config.v1":
        body = render_fragment("admin_workspace_config", {
            "active_domain": context["active_domain"], "knowledge_root": "/sample/knowledge",
        })
    elif widget_id == "admin.sync.hosts.v1":
        # Role-gated views need the corresponding role to show their real table.
        body = handlers[widget_id]({
            **context, "runtime_node": SimpleNamespace(role="master"),
        })
        note = "Demonstrates the master-node role."
    else:
        body = handlers[widget_id](context)
    if widget_id.startswith("infooutput.quiz."):
        status = "planned"
        note = "Quiz generation is not implemented."
    return PreviewResult(
        widget_id=widget_id, label=spec.label, description=spec.description,
        area=spec.area, category=spec.category,
        width=spec.default_w, height=spec.default_h,
        active_domain=context["active_domain"],
        preview_mode="sample", readonly=True, status=status,
        note=note, body_html=readonly_preview_html(body), scope_label="Domain",
    )

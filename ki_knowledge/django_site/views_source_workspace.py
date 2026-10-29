"""Source landing/workspace pages and file/upload import actions."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode

from django.contrib import messages
from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from ki_knowledge.django_site.jira_workflow import (
    jira_cache_db_path,
    jira_csv_path,
    jira_issue_count,
)
from ki_knowledge.django_site.knowledge_summary import domain_registry_overview
from ki_knowledge.django_site.source_workflow import (
    import_markdown_directory,
    import_markdown_file,
    import_mixed_directory,
    import_mixed_file,
    import_ontology_directory,
    import_ontology_file,
    import_ontology_url,
    render_markdown_html,
    tree_lines,
    workspace_markdown_files,
    workspace_ontology_files,
)
from ki_knowledge.integrations.mixed_ingest import (
    EPUB_KIND,
    IMAGE_KIND,
    TABLE_KIND,
    classify_file,
    discover_mixed_files,
)
from ki_knowledge.services.domain_paths import domain_pdf_dir

from .dashboard_registry import default_widget_ids_for_area
from .data_display import display_data_path
from .domain_registry import data_dir, semantic_domain_states, source_in_domain
from .knowledge_browser import root_markdown_tree, store
from .page_widgets import build_data_sources_widget_cards, build_workspace_widget_cards
from .pdf_jobs import create_pdf_import_job
from .source_workflow import discover_pdf_files
from .views_common import (
    _active_semantic_domain,
    _display_mode,
    _load_dashboard_widget_ids,
    _load_dashboard_widget_widths,
    _selected_markdown,
)


def data_sources_view(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    display_mode = _display_mode(request, default="cards")
    store_obj = store()
    all_domains = domain_registry_overview(active_domain)
    markdown_files = workspace_markdown_files(domain=active_domain)
    ontology_files = workspace_ontology_files(domain=active_domain)
    jira_issues = jira_issue_count(active_domain)
    domain_states = semantic_domain_states()
    active_state = next((item for item in domain_states if item.get("domain") == active_domain), {"domain": active_domain})
    all_sources = store_obj.list_sources()
    sources_list = [
        source
        for source in all_sources
        if source_in_domain(source, domain=active_domain)
    ]
    owl_sources = [source for source in sources_list if source.source_type == "owl"]
    pdf_dir = domain_pdf_dir(active_domain)
    pdf_jobs = active_state.get("pdf_jobs") or {"pending": 0, "processing": 0, "done": 0, "failed": 0, "total": 0}
    configured_widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="datasources",
        fallback=default_widget_ids_for_area("datasources"),
    )
    widget_widths = _load_dashboard_widget_widths(request, area_key="datasources")
    widget_cards = build_data_sources_widget_cards(
        request=request,
        active_domain=active_domain,
        all_domains=all_domains,
        active_domain_state=active_state,
        markdown_count=len(markdown_files),
        markdown_files=markdown_files,
        display_mode=display_mode,
        data_dir=display_data_path(data_dir(active_domain)),
        jira_issues=jira_issues,
        jira_csv_path=display_data_path(jira_csv_path(active_domain)),
        jira_cache_db=display_data_path(jira_cache_db_path(active_domain)),
        pdf_count=int(active_state.get("pdf_files", 0) or 0),
        pdf_dir=display_data_path(pdf_dir) if active_state.get("has_pdf_source") or pdf_dir.exists() else "unused",
        pdf_jobs=pdf_jobs,
        ontology_count=len(ontology_files),
        ontology_dir=display_data_path(active_state.get("ontology_dir")),
        owl_sources=len(owl_sources),
        sources=sources_list,
        widget_ids=configured_widget_ids,
        widget_widths=widget_widths,
    )
    return render(
        request,
        "kicli_django/data_sources.html",
        {
            "active_domain": active_domain,
            "active_domain_state": active_state,
            "display_mode": display_mode,
            "all_domains": all_domains,
            "widget_cards": widget_cards,

            "data_sources_toggle_cards_url": f"{reverse('data-sources')}?display=cards",
            "data_sources_toggle_table_url": f"{reverse('data-sources')}?display=table",
            "jira_issues": jira_issues,
            "jira_csv_path": display_data_path(jira_csv_path(active_domain)),
            "jira_cache_db": display_data_path(jira_cache_db_path(active_domain)),
            "data_dir": display_data_path(data_dir(active_domain)),
            "pdf_dir": display_data_path(pdf_dir) if active_state.get("has_pdf_source") or pdf_dir.exists() else "unused",
            "pdf_default_path": str(pdf_dir) if (active_state.get("has_pdf_source") or pdf_dir.exists()) else "",
            "pdf_count": int(active_state.get("pdf_files", 0) or 0),
            "pdf_jobs": pdf_jobs,
            "ontology_dir": display_data_path(active_state.get("ontology_dir")),
            "markdown_count": len(markdown_files),
            "markdown_examples": [
                {**item, "display_path": display_data_path(item["path"])}
                for item in markdown_files[:6]
            ],
            "ontology_count": len(ontology_files),
            "ontology_examples": [
                {**item, "display_path": display_data_path(item["path"])}
                for item in ontology_files[:8]
            ],
            "owl_sources": len(owl_sources),
            "sources": sources_list,
        },
    )


@require_http_methods(["GET", "POST"])

def workspace(request: HttpRequest):
    active_domain = _active_semantic_domain(request)
    selected = _selected_markdown(request)
    query = request.GET.get("q", "")
    display_mode = _display_mode(request, default="cards")
    all_domains = semantic_domain_states()
    active_state = next((item for item in all_domains if item.get("domain") == active_domain), {"domain": active_domain})
    tree = root_markdown_tree(query=query, domain=active_domain)
    markdown_files = workspace_markdown_files(query=query, domain=active_domain)
    source_preview = None
    source_preview_html = None
    if selected:
        try:
            source_preview = selected.read_text(encoding="utf-8")
            source_preview_html = render_markdown_html(source_preview)
        except OSError:
            source_preview = None
            source_preview_html = None
    widget_ids = _load_dashboard_widget_ids(
        request,
        area_key="datasources",
        fallback=default_widget_ids_for_area("datasources", "workspace"),
        subpage_key="workspace",
    )
    widget_cards = build_workspace_widget_cards(
        request=request,
        active_domain=active_domain,
        all_domains=all_domains,
        active_domain_state=active_state,
        markdown_count=len(markdown_files),
        markdown_files=markdown_files,
        display_mode=display_mode,
        query=query,
        sources=[],
        widget_ids=widget_ids,
        widget_widths=_load_dashboard_widget_widths(request, area_key="datasources", subpage_key="workspace"),
    )
    return render(
        request,
        "kicli_django/workspace.html",
        {
            "data_dir": display_data_path(data_dir(active_domain)),
            "active_domain": active_domain,
            "tree_lines": tree_lines(tree) if tree else [],
            "markdown_files": markdown_files,
            "selected": selected,
            "source_preview": source_preview,
            "source_preview_html": source_preview_html,
            "query": query,
            "display_mode": display_mode,
            "workspace_toggle_cards_url": f"{reverse('workspace')}?{urlencode({'domain': active_domain, 'q': query, 'display': 'cards'})}",
            "workspace_toggle_table_url": f"{reverse('workspace')}?{urlencode({'domain': active_domain, 'q': query, 'display': 'table'})}",
            "widget_cards": widget_cards,
        },
    )


@require_http_methods(["POST"])

def import_action(request: HttpRequest):
    raw_path = request.POST.get("path", "").strip()
    import_type = request.POST.get("import_type", "file")
    next_page = request.POST.get("next", "dashboard").strip() or "dashboard"
    if not raw_path:
        return HttpResponseBadRequest("path missing")
    path = Path(raw_path).expanduser()
    
    should_treat_as_directory = (
        import_type == "directory"
        or raw_path.endswith(("/", "\\"))
        or (not path.suffix and not raw_path.startswith(("http://", "https://")))
    )

    if path.is_file():
        if path.suffix.lower() == ".pdf":
            domain = _active_semantic_domain(request)
            try:
                job_id = create_pdf_import_job(str(path), domain=domain)
            except FileNotFoundError:
                return HttpResponseBadRequest("PDF file not found")
            messages.success(request, f"PDF import queued: {job_id}")
            return HttpResponseRedirect(f"{reverse('pdf-import-jobs')}?domain={domain}")
        if classify_file(path) in {TABLE_KIND, IMAGE_KIND, EPUB_KIND}:
            image_processing = "asset" if request.POST.get("image_processing") == "asset" else "ocr"
            result = import_mixed_file(
                path,
                domain=_active_semantic_domain(request),
                image_processing=image_processing,
            )
            if result.get("error"):
                messages.error(request, f"{path.name}: {result['error']}")
            else:
                messages.success(request, f"{path.name}: {result['imported']} Wissensobjekte übernommen.")
                for warning in result.get("warnings", []):
                    messages.warning(request, warning)
            return HttpResponseRedirect(reverse(next_page))
        # Detect OWL/RDF files by extension
        if path.suffix.lower() in {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}:
            import_ontology_file(path)
        else:
            import_markdown_file(path, source_name=request.POST.get("source_name") or path.name)
    elif should_treat_as_directory:
        path.mkdir(parents=True, exist_ok=True)
        grouped = discover_mixed_files(path)
        if grouped[TABLE_KIND] or grouped[IMAGE_KIND] or grouped[EPUB_KIND]:
            domain = _active_semantic_domain(request)
            summary = import_mixed_directory(
                path,
                domain=domain,
                queue_pdf=lambda pdf_path: create_pdf_import_job(str(pdf_path), domain=domain),
                image_processing="asset" if request.POST.get("image_processing") == "asset" else "ocr",
            )
            counts = ", ".join(f"{kind}: {count}" for kind, count in summary["files"].items() if count)
            messages.success(
                request,
                f"Mix-Import: {summary['imported']} Wissensobjekte ({counts or 'keine Dateien'}), "
                f"{summary['queued_pdfs']} PDF-Jobs eingereiht.",
            )
            for error in summary["errors"][:10]:
                messages.warning(request, f"{Path(error['file']).name}: {error['error']}")
            if summary["unsupported"]:
                messages.info(request, f"{len(summary['unsupported'])} Datei(en) mit unbekanntem Format übersprungen.")
            return HttpResponseRedirect(reverse(next_page))
        # Auto-detect which importer to use based on file types in directory
        md_files = list(path.glob("**/*.md"))
        pdf_files = discover_pdf_files(path)
        ontology_suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
        ontology_files = [p for p in path.glob("**/*") if p.suffix.lower() in ontology_suffixes]

        if pdf_files:
            domain = _active_semantic_domain(request)
            created = 0
            for pdf_path in sorted({p.resolve(strict=False) for p in pdf_files}):
                try:
                    create_pdf_import_job(str(pdf_path), domain=domain)
                    created += 1
                except (FileNotFoundError, OSError, ValueError):
                    continue
            messages.success(request, f"Queued {created} PDF jobs for domain {domain}.")
            return HttpResponseRedirect(f"{reverse('pdf-import-jobs')}?domain={domain}")

        # Import all remaining types found (recursive)
        if md_files:
            import_markdown_directory(path)
        if ontology_files:
            import_ontology_directory(path)

        if not (md_files or pdf_files or ontology_files):
            messages.info(request, f"Directory prepared: {path}. No importable files found yet.")
            return HttpResponseRedirect(reverse(next_page))
    elif raw_path.startswith(("http://", "https://")) and import_type in {"file", "ontology"}:
        import_ontology_url(raw_path)
    else:
        return HttpResponseBadRequest("path not importable")
    return HttpResponseRedirect(reverse(next_page))


@require_http_methods(["POST"])

def quick_import_action(request: HttpRequest):
    """Path-free import: a source folder of the active domain, all folders, or uploaded files."""
    from .quick_import import QUICK_SOURCE_KEYS, quick_import_rows, run_all_imports, run_source_import, save_and_import_uploads

    domain = _active_semantic_domain(request)
    target = reverse("data-sources")
    uploads = request.FILES.getlist("files")
    image_processing = "asset" if request.POST.get("image_processing") == "asset" else "ocr"
    if uploads:
        result = save_and_import_uploads(uploads, domain, image_processing=image_processing)
        if result["imported"]:
            messages.success(request, "Hochgeladen & importiert: " + ", ".join(result["imported"]))
        for warning in result["warnings"][:10]:
            messages.warning(request, warning)
        if not result["imported"] and not result["warnings"]:
            messages.info(request, "Keine Dateien empfangen.")
        return HttpResponseRedirect(target)

    source = request.POST.get("source", "").strip()
    if source == "all":
        state = next((item for item in semantic_domain_states() if item.get("domain") == domain), {"domain": domain})
        results = run_all_imports(domain, quick_import_rows(domain, state, ()), image_processing=image_processing)
        if not results:
            messages.info(request, "Keine Dateien zum Importieren gefunden.")
    elif source in QUICK_SOURCE_KEYS:
        results = [run_source_import(source, domain, image_processing=image_processing)]
    else:
        return HttpResponseBadRequest("unknown source")
    for result in results:
        (messages.success if result["ok"] else messages.error)(request, result["message"])
        for warning in result["warnings"][:10]:
            messages.warning(request, warning)
    return HttpResponseRedirect(target)

"""Compatibility exports; implementations live in focused responsibility modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ki_knowledge.django_site.domain_paths import (
    _cached_delete,
    _cached_get,
    _cached_set,
    _domain_source_ids_cache_key,
    _domain_summary_cache_key,
    invalidate_domain_summary_cache,
)
from ki_knowledge.django_site.source_workflow import (
    discover_ontology_files,
    import_markdown_directory,
    import_markdown_file,
    import_mixed_directory,
    import_mixed_file,
    import_ontology_directory,
    import_ontology_file,
    import_ontology_url,
    import_pdf_directory,
    import_pdf_file,
    mixed_files_summary,
    render_markdown_html,
    tree_lines,
    workspace_markdown_files,
    workspace_ontology_files,
)
from ki_knowledge.integrations.jira_cache import DomainTerm
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.services.domain_paths import (
    data_layout,
    data_root,
    domain_jira_dir,
    domain_label,
    domain_markdown_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    domain_source_roots,
    domain_state_paths,
    infer_domain_from_path,
    normalize_registry_domain,
)

from .chat_service import (
    ollama_available_models,
    ollama_chat_answer,
    ollama_chat_dir,
    ollama_runtime_settings,
    save_ollama_chat_markdown,
)
from .data_display import artifact_content_preview, display_data_path, display_source_ref
from .domain_registry import (
    _domain_blockers,
    _domain_env,
    _infer_domain_from_path,
    _is_under_dir,
    _register_domains,
    _source_matches_domain_legacy,
    available_data_domains,
    create_semantic_domain,
    data_dir,
    data_layout_snapshot,
    default_semantic_domain,
    delete_semantic_domain,
    domain_db_paths,
    jira_graph_db_path,
    normalize_semantic_domain,
    semantic_domain_states,
    semantic_domains,
    semantic_target,
    source_in_domain,
)
from .knowledge_browser import (
    _candidate_record_ids_for_semantic_linking,
    generate_all_artifacts,
    graph_3d_context,
    graph_context,
    graph_payload,
    knowledge_api_browser_context,
    knowledge_api_default_url,
    knowledge_api_health,
    root_markdown_tree,
    store,
)
from .knowledge_summary import _domain_scoped_sources, domain_source_ids
from .pdf_jobs import (
    _compact_job_preview,
    _minutes_since,
    _parse_iso_datetime,
    create_pdf_import_job,
    delete_pdf_import_jobs,
    get_pdf_batch_processor,
    get_pdf_job_stats,
    pdf_batch_db_path,
    pdf_import_jobs,
    pdf_import_report,
    process_pdf_import_job,
    start_pdf_worker,
)
from .prompt_library import (
    _default_prompt_backlog_markdown,
    _default_prompt_templates_markdown,
    _normalize_prompt_template_name,
    _read_or_initialize_markdown,
    _render_prompt_template,
    load_prompt_library_context,
    parse_prompt_backlog,
    parse_prompt_templates,
    prompt_backlog_path,
    prompt_batch_dir,
    prompt_batch_outputs,
    prompt_library_dir,
    prompt_templates_path,
    run_prompt_backlog_batch,
    save_prompt_batch_markdown,
    save_prompt_library_documents,
)
from .source_workflow import discover_pdf_files
from .support_chat import (
    _normalize_retrieval_sources,
    _support_sources,
    jira_support_chat_answer,
    support_chat_answer,
    support_chat_index_status,
    support_search,
)


@dataclass
class ImportResult:
    imported: int = 0
    source_ids: list[str] | None = None


def jira_cache_db_path(domain: str | None = None) -> str:
    from ki_knowledge.django_site.jira_workflow import jira_cache_db_path as _impl
    return _impl(domain)


def jira_issue_count(domain: str | None = None) -> int:
    from ki_knowledge.django_site.jira_workflow import jira_issue_count as _impl
    return _impl(domain)


def jira_csv_path(domain: str | None = None) -> str:
    from ki_knowledge.django_site.jira_workflow import jira_csv_path as _impl
    return _impl(domain)


def jira_domain_terms(limit: int = 200, min_count: int = 2, *, sort: str = "relevance", order: str = "desc", domain: str | None = None) -> list[DomainTerm]:
    from ki_knowledge.django_site.jira_workflow import jira_domain_terms as _impl
    return _impl(limit=limit, min_count=min_count, sort=sort, order=order, domain=domain)


def jira_reset_data(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_reset_data as _impl
    return _impl(domain)


def jira_reimport_data(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_reimport_data as _impl
    return _impl(domain)


def jira_excluded_terms(kind: str | None = None, domain: str | None = None) -> list[dict[str, str]]:
    from ki_knowledge.django_site.jira_workflow import jira_excluded_terms as _impl
    return _impl(kind=kind, domain=domain)


def jira_exclusion_add(term: str, kind: str = "exception", domain: str | None = None) -> bool:
    from ki_knowledge.django_site.jira_workflow import jira_exclusion_add as _impl
    return _impl(term, kind=kind, domain=domain)


def jira_exclusion_remove(term: str, domain: str | None = None) -> bool:
    from ki_knowledge.django_site.jira_workflow import jira_exclusion_remove as _impl
    return _impl(term, domain=domain)


def jira_forget_jira_term(term: str, kind: str = "exception", domain: str | None = None) -> dict[str, bool]:
    from ki_knowledge.django_site.jira_workflow import jira_forget_jira_term as _impl
    return _impl(term, kind=kind, domain=domain)


def jira_hybrid_search(query: str, limit: int = 8, domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_hybrid_search as _impl
    return _impl(query, limit=limit, domain=domain)


def jira_daily_timeline(days: int = 14, domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_daily_timeline as _impl
    return _impl(days=days, domain=domain)


def jira_graph_explorer(*, issue_key: str | None = None, limit: int = 20, rebuild: bool = False, domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_graph_explorer as _impl
    return _impl(issue_key=issue_key, limit=limit, rebuild=rebuild, domain=domain)


def jira_domain_analysis(*, limit_terms: int = 20, min_count: int = 2, query: str = "", limit_hits: int = 8, domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.jira_workflow import jira_domain_analysis as _impl
    return _impl(limit_terms=limit_terms, min_count=min_count, query=query, limit_hits=limit_hits, domain=domain)


def domain_knowledge_summary(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.knowledge_summary import domain_knowledge_summary as _impl
    return _impl(domain)


def domain_registry_overview(active_domain: str | None = None) -> list[dict[str, Any]]:
    from ki_knowledge.django_site.knowledge_summary import domain_registry_overview as _impl
    return _impl(active_domain)


def knowledge_base_clear_domain_artifacts(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.knowledge_summary import knowledge_base_clear_domain_artifacts as _impl
    return _impl(domain)


def knowledge_base_reset_domain(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.knowledge_summary import knowledge_base_reset_domain as _impl
    return _impl(domain)


def knowledge_base_reset_all() -> dict[str, Any]:
    from ki_knowledge.django_site.knowledge_summary import knowledge_base_reset_all as _impl
    return _impl()


def run_dashboard_task(task_name: str, *, domain: str | None = None, target_domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.ui_dispatcher import run_dashboard_task as _impl
    return _impl(task_name, domain=domain, target_domain=target_domain)


def semantic_store(domain: str | None = None) -> SemanticTermStore:
    from ki_knowledge.django_site.knowledge_summary import semantic_store as _impl
    return _impl(domain)


def semantic_terms(status: str | None = None, limit: int = 300, domain: str | None = None):
    from ki_knowledge.django_site.knowledge_summary import semantic_terms as _impl
    return _impl(status=status, limit=limit, domain=domain)


def semantic_term_detail(term_id: str, domain: str | None = None) -> dict[str, Any] | None:
    from ki_knowledge.django_site.knowledge_summary import semantic_term_detail as _impl
    return _impl(term_id, domain)


def semantic_monitoring_snapshot(domain: str | None = None) -> dict[str, Any]:
    from ki_knowledge.django_site.knowledge_summary import semantic_monitoring_snapshot as _impl
    return _impl(domain)


def semantic_jobs(status: str | None = None, job_type: str | None = None, limit: int = 200, domain: str | None = None):
    from ki_knowledge.django_site.knowledge_summary import semantic_jobs as _impl
    return _impl(status=status, job_type=job_type, limit=limit, domain=domain)


def semantic_job_detail(job_id: str, domain: str | None = None) -> dict[str, Any] | None:
    from ki_knowledge.django_site.knowledge_summary import semantic_job_detail as _impl
    return _impl(job_id, domain)


__all__ = [
    "ImportResult",
    "artifact_content_preview",
    "available_data_domains",
    "create_pdf_import_job",
    "create_semantic_domain",
    "data_dir",
    "data_layout",
    "data_layout_snapshot",
    "data_root",
    "default_semantic_domain",
    "delete_pdf_import_jobs",
    "delete_semantic_domain",
    "discover_ontology_files",
    "discover_pdf_files",
    "display_data_path",
    "display_source_ref",
    "domain_db_paths",
    "domain_jira_dir",
    "domain_knowledge_summary",
    "domain_label",
    "domain_markdown_dir",
    "domain_ontology_dir",
    "domain_pdf_dir",
    "domain_registry_overview",
    "domain_source_ids",
    "domain_source_roots",
    "domain_state_paths",
    "generate_all_artifacts",
    "get_pdf_batch_processor",
    "get_pdf_job_stats",
    "graph_3d_context",
    "graph_context",
    "graph_payload",
    "import_markdown_directory",
    "import_markdown_file",
    "import_mixed_directory",
    "import_mixed_file",
    "import_ontology_directory",
    "import_ontology_file",
    "import_ontology_url",
    "import_pdf_directory",
    "import_pdf_file",
    "infer_domain_from_path",
    "invalidate_domain_summary_cache",
    "jira_cache_db_path",
    "jira_csv_path",
    "jira_daily_timeline",
    "jira_domain_analysis",
    "jira_domain_terms",
    "jira_excluded_terms",
    "jira_exclusion_add",
    "jira_exclusion_remove",
    "jira_forget_jira_term",
    "jira_graph_db_path",
    "jira_graph_explorer",
    "jira_hybrid_search",
    "jira_issue_count",
    "jira_reimport_data",
    "jira_reset_data",
    "jira_support_chat_answer",
    "knowledge_api_browser_context",
    "knowledge_api_default_url",
    "knowledge_api_health",
    "knowledge_base_clear_domain_artifacts",
    "knowledge_base_reset_all",
    "knowledge_base_reset_domain",
    "load_prompt_library_context",
    "mixed_files_summary",
    "normalize_registry_domain",
    "normalize_semantic_domain",
    "ollama_available_models",
    "ollama_chat_answer",
    "ollama_chat_dir",
    "ollama_runtime_settings",
    "parse_prompt_backlog",
    "parse_prompt_templates",
    "pdf_batch_db_path",
    "pdf_import_jobs",
    "pdf_import_report",
    "process_pdf_import_job",
    "prompt_backlog_path",
    "prompt_batch_dir",
    "prompt_batch_outputs",
    "prompt_library_dir",
    "prompt_templates_path",
    "render_markdown_html",
    "root_markdown_tree",
    "run_dashboard_task",
    "run_prompt_backlog_batch",
    "save_ollama_chat_markdown",
    "save_prompt_batch_markdown",
    "save_prompt_library_documents",
    "semantic_domain_states",
    "semantic_domains",
    "semantic_job_detail",
    "semantic_jobs",
    "semantic_monitoring_snapshot",
    "semantic_store",
    "semantic_target",
    "semantic_term_detail",
    "semantic_terms",
    "source_in_domain",
    "start_pdf_worker",
    "store",
    "support_chat_answer",
    "support_chat_index_status",
    "support_search",
    "tree_lines",
    "workspace_markdown_files",
    "workspace_ontology_files",
]

"""Compatibility exports for source-area views; URL names remain unchanged."""

from .views_chat import jira_support_chat_view
from .views_chat import ollama_chat_view
from .views_chat import prompt_backlog_view
from .views_chat import support_chat_view
from .views_content import artifacts
from .views_content import generate_action
from .views_content import records
from .views_jira import jira_daily_timeline_view
from .views_jira import jira_domain_analysis_view
from .views_jira import jira_domain_terms_view
from .views_jira import jira_exclusions_view
from .views_jira import jira_graph_explorer_view
from .views_jira import jira_hybrid_search_view
from .views_pdf import pdf_import_jobs_json
from .views_pdf import pdf_import_jobs_view
from .views_pdf import pdf_import_report_view
from .views_pdf import pdf_inventory_view
from .views_pdf import pdf_job_detail_view
from .views_semantic import job_detail_view
from .views_semantic import jobs_view
from .views_semantic import semantic_term_detail_view
from .views_semantic import semantic_terms_view
from .views_source_browser import sources
from .views_source_browser import sources_action
from .views_source_detail import create_source_infosite_project
from .views_source_detail import source_detail
from .views_source_detail import source_graph
from .views_source_detail import source_graph_3d
from .views_source_workspace import data_sources_view
from .views_source_workspace import import_action
from .views_source_workspace import quick_import_action
from .views_source_workspace import workspace

__all__ = [
    "artifacts",
    "create_source_infosite_project",
    "data_sources_view",
    "generate_action",
    "import_action",
    "jira_daily_timeline_view",
    "jira_domain_analysis_view",
    "jira_domain_terms_view",
    "jira_exclusions_view",
    "jira_graph_explorer_view",
    "jira_hybrid_search_view",
    "jira_support_chat_view",
    "job_detail_view",
    "jobs_view",
    "ollama_chat_view",
    "pdf_import_jobs_json",
    "pdf_import_jobs_view",
    "pdf_import_report_view",
    "pdf_inventory_view",
    "pdf_job_detail_view",
    "prompt_backlog_view",
    "quick_import_action",
    "records",
    "semantic_term_detail_view",
    "semantic_terms_view",
    "source_detail",
    "source_graph",
    "source_graph_3d",
    "sources",
    "sources_action",
    "support_chat_view",
    "workspace",
]

from django.urls import path, include
from django.contrib import admin

from . import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    # Infosite Management
    path("infosite/", include("ki_knowledge.django_site.infosite_urls")),
    # ... rest of URLs
    path("data-sources/", views.data_sources_view, name="data-sources"),
    path("knowledge/", views.knowledge_landing_view, name="knowledge"),
    path("semantic/", views.semantic_landing_view, name="semantic"),
    path("settings/", views.settings_view, name="settings"),
    path("settings/layout/", views.layout_settings_view, name="settings-layout"),
    path("knowledge-api/", views.knowledge_api_view, name="knowledge-api"),
    path("prompt-backlog/", views.prompt_backlog_view, name="prompt-backlog"),
    path("ollama-chat/", views.ollama_chat_view, name="ollama-chat"),
    path("dashboard/monitoring.json", views.dashboard_monitoring, name="dashboard-monitoring"),
    path("dashboard/tasks/run", views.dashboard_task_action, name="dashboard-task-action"),
    path("workspace/", views.workspace, name="workspace"),
    path("sources/", views.sources, name="sources"),
    path("records/", views.records, name="records"),
    path("jobs/", views.jobs_view, name="jobs"),
    path("jobs/<str:job_id>/", views.job_detail_view, name="job-detail"),
    path("pdf-import/", views.pdf_import_jobs_view, name="pdf-import-jobs"),
    path("pdf-import/report/", views.pdf_import_report_view, name="pdf-import-report"),
    path("pdf-import/jobs/<str:job_id>/", views.pdf_job_detail_view, name="pdf-job-detail"),
    path("pdf-import/jobs.json", views.pdf_import_jobs_json, name="pdf-import-jobs-json"),
    path("jira/domain-terms/", views.jira_domain_terms_view, name="jira-domain-terms"),
    path("jira/exclusions/", views.jira_exclusions_view, name="jira-exclusions"),
    path("jira/domain-analysis/", views.jira_domain_analysis_view, name="jira-domain-analysis"),
    path("jira/hybrid-search/", views.jira_hybrid_search_view, name="jira-hybrid-search"),
    path("jira/graph-explorer/", views.jira_graph_explorer_view, name="jira-graph-explorer"),
    path("jira/daily-timeline/", views.jira_daily_timeline_view, name="jira-daily-timeline"),
    path("jira/support-chat/", views.jira_support_chat_view, name="jira-support-chat"),
    path("support-chat/", views.support_chat_view, name="support-chat"),
    path("semantic/terms/", views.semantic_terms_view, name="semantic-terms"),
    path("semantic/terms/<path:term_id>/", views.semantic_term_detail_view, name="semantic-term-detail"),
    path("sources/<path:source_id>/", views.source_detail, name="source-detail"),
    path("graphs/<path:source_id>/3d/", views.source_graph_3d, name="source-graph-3d"),
    path("graphs/<path:source_id>/", views.source_graph, name="source-graph"),
    path("artifacts/", views.artifacts, name="artifacts"),
    path("import/", views.import_action, name="import-action"),
    path("generate/", views.generate_action, name="generate-action"),
]

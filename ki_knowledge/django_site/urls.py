from django.urls import path, include
from django.contrib import admin

from wagtail.admin import urls as wagtailadmin_urls
from wagtail import urls as wagtail_urls
from wagtail.documents import urls as wagtaildocs_urls

from . import views

# URL layout follows the navigation IA documented in
# docs/navigation-ia-proposal.md: Dashboard | Data Sources | Internal
# Knowledge | Info Output | CMS Catalog | Settings. View names (the `name=`
# kwarg) are unchanged from the pre-reorganization layout so all internal
# reverse()/{% url %} usages keep working; only the URL *paths* moved under
# their new area prefix. This is a single-user development project with no
# external bookmarks, so old paths are cut over directly (no redirects).
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", views.dashboard, name="dashboard"),
    path("dashboard/monitoring.json", views.dashboard_monitoring, name="dashboard-monitoring"),
    path("dashboard/tasks/run", views.dashboard_task_action, name="dashboard-task-action"),

    # --- 📥 Data Sources: everything that brings raw data in -----------------
    path("data-sources/", views.data_sources_view, name="data-sources"),
    path("data-sources/workspace/", views.workspace, name="workspace"),
    path("data-sources/import/", views.import_action, name="import-action"),
    path("data-sources/sources/", views.sources, name="sources"),
    path("data-sources/sources/<path:source_id>/", views.source_detail, name="source-detail"),
    path("data-sources/pdf/", views.pdf_import_jobs_view, name="pdf-import-jobs"),
    path("data-sources/pdf/report/", views.pdf_import_report_view, name="pdf-import-report"),
    path("data-sources/pdf/jobs/<str:job_id>/", views.pdf_job_detail_view, name="pdf-job-detail"),
    path("data-sources/pdf/jobs.json", views.pdf_import_jobs_json, name="pdf-import-jobs-json"),
    path("data-sources/jira/domain-terms/", views.jira_domain_terms_view, name="jira-domain-terms"),
    path("data-sources/jira/exclusions/", views.jira_exclusions_view, name="jira-exclusions"),

    # --- 🧠 Internal Knowledge: raw data -> processed knowledge -------------
    path("knowledge/", views.knowledge_landing_view, name="knowledge"),
    path("knowledge/api/", views.knowledge_api_view, name="knowledge-api"),
    path("knowledge/records/", views.records, name="records"),
    path("knowledge/artifacts/", views.artifacts, name="artifacts"),
    path("knowledge/generate/", views.generate_action, name="generate-action"),
    path("knowledge/jobs/", views.jobs_view, name="jobs"),
    path("knowledge/jobs/<str:job_id>/", views.job_detail_view, name="job-detail"),
    path("knowledge/graphs/<path:source_id>/3d/", views.source_graph_3d, name="source-graph-3d"),
    path("knowledge/graphs/<path:source_id>/", views.source_graph, name="source-graph"),
    path("knowledge/prompt-backlog/", views.prompt_backlog_view, name="prompt-backlog"),
    path("knowledge/chat/support/", views.support_chat_view, name="support-chat"),
    path("knowledge/chat/jira-support/", views.jira_support_chat_view, name="jira-support-chat"),
    path("knowledge/chat/ollama/", views.ollama_chat_view, name="ollama-chat"),
    # Semantic sub-area (term extraction, domain analysis, graph/hybrid search)
    path("knowledge/semantic/", views.semantic_landing_view, name="semantic"),
    path("knowledge/semantic/terms/", views.semantic_terms_view, name="semantic-terms"),
    path("knowledge/semantic/terms/<path:term_id>/", views.semantic_term_detail_view, name="semantic-term-detail"),
    path("knowledge/semantic/domain-analysis/", views.jira_domain_analysis_view, name="jira-domain-analysis"),
    path("knowledge/semantic/hybrid-search/", views.jira_hybrid_search_view, name="jira-hybrid-search"),
    path("knowledge/semantic/graph-explorer/", views.jira_graph_explorer_view, name="jira-graph-explorer"),
    path("knowledge/semantic/daily-timeline/", views.jira_daily_timeline_view, name="jira-daily-timeline"),

    # --- 📤 Info Output: publishing processed knowledge outward -------------
    path("output/", views.output_landing_view, name="output"),
    path("output/quiz/", views.output_quiz_view, name="output-quiz"),
    path("output/infosite/", include("ki_knowledge.django_site.infosite_urls")),

    # --- 🗂️ CMS Catalog: Wagtail editorial layer (Schritt 3+6) --------------
    path("cms-admin/", include(wagtailadmin_urls)),
    path("cms-documents/", include(wagtaildocs_urls)),

    # --- 🛠️ Admin ------------------------------------------------------------
    path("admin-overview/", views.admin_overview_view, name="admin-overview"),

    # --- ⚙️ Settings ----------------------------------------------------------
    path("settings/", views.settings_view, name="settings"),
    path("settings/config/", views.settings_config_view, name="settings-config"),
    path("settings/layout/", views.layout_settings_view, name="settings-layout"),
    path("settings/layout/widgets/", views.widget_catalog_view, name="settings-layout-widgets"),
    path("settings/layout/builder/", views.dashboard_builder_view, name="settings-layout-builder"),

    # Wagtail page serving must stay last so it acts as a catch-all under /cms/
    path("cms/", include(wagtail_urls)),
]

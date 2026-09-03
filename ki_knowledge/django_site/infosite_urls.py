"""URL patterns for Infosite views."""

from django.urls import path
from . import infosite_views

app_name = "infosite"

urlpatterns = [
    # Project management
    path("", infosite_views.infosite_project_list, name="project_list"),
    path("dashboard/", infosite_views.infosite_dashboard, name="dashboard"),
    path("project/create/", infosite_views.infosite_project_create, name="project_create"),
    path("project/<int:project_id>/", infosite_views.infosite_project_detail, name="project_detail"),
    path("project/<int:project_id>/edit/", infosite_views.infosite_project_edit, name="project_edit"),
    path("project/<int:project_id>/delete/", infosite_views.infosite_project_delete, name="project_delete"),
    
    # Document discovery & sync
    path("project/<int:project_id>/sync/", infosite_views.infosite_sync_documents, name="sync"),
    path("project/<int:project_id>/discover/", infosite_views.infosite_discover_documents, name="discover"),
    
    # Generation & preview
    path("project/<int:project_id>/generate/", infosite_views.infosite_generate, name="generate"),
    path("project/<int:project_id>/preview/", infosite_views.infosite_preview, name="preview"),
    path("project/<int:project_id>/download/", infosite_views.infosite_download, name="download"),
    path("project/<int:project_id>/versions/", infosite_views.infosite_versions, name="versions"),
    
    # Import control
    path("project/<int:project_id>/import/", infosite_views.infosite_import_control, name="import_control"),
    path("project/<int:project_id>/import/selected/", infosite_views.infosite_import_selected, name="import_selected"),
    path("project/<int:project_id>/import/jobs/", infosite_views.infosite_import_jobs, name="import_jobs"),
    path(
        "api/source-document/<int:project_id>/<int:doc_id>/",
        infosite_views.infosite_source_document_preview_api,
        name="source_document_api",
    ),
    
    # Document preview
    path("project/<int:project_id>/documents/", infosite_views.infosite_document_preview, name="documents"),
    path("api/document/<int:project_id>/<path:doc_path>/", infosite_views.infosite_document_preview_api, name="document_api"),
    
    # Knowledge block extraction
    path("project/<int:project_id>/knowledge-blocks/", infosite_views.infosite_extract_knowledge_blocks, name="knowledge_blocks"),
    path("project/<int:project_id>/knowledge-blocks/publish/", infosite_views.infosite_publish_knowledge_blocks, name="publish_blocks"),
    path("project/<int:project_id>/knowledge-blocks/jobs/", infosite_views.infosite_knowledge_extraction_jobs, name="knowledge_extraction_jobs"),
    
    # AI refinement
    path("project/<int:project_id>/refine/", infosite_views.infosite_ai_refine, name="ai_refine"),
    path("project/<int:project_id>/refine/apply/", infosite_views.infosite_ai_refine_apply, name="ai_refine_apply"),
]

"""URL patterns for Infosite views."""

from django.urls import path
from . import infosite_views

app_name = "infosite"

urlpatterns = [
    path("dashboard/", infosite_views.infosite_dashboard, name="dashboard"),
    path("project/<int:project_id>/", infosite_views.infosite_project_detail, name="project_detail"),
    path("project/<int:project_id>/discover/", infosite_views.infosite_discover_documents, name="discover"),
    path("project/<int:project_id>/generate/", infosite_views.infosite_generate, name="generate"),
    path("project/<int:project_id>/preview/", infosite_views.infosite_preview, name="preview"),
    # Import control
    path("project/<int:project_id>/import/", infosite_views.infosite_import_control, name="import_control"),
    path("project/<int:project_id>/import/selected/", infosite_views.infosite_import_selected, name="import_selected"),
    # AI refinement
    path("project/<int:project_id>/refine/", infosite_views.infosite_ai_refine, name="ai_refine"),
    path("project/<int:project_id>/refine/apply/", infosite_views.infosite_ai_refine_apply, name="ai_refine_apply"),
]

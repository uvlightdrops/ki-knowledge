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
]

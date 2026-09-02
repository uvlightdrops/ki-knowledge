"""Django admin configuration for Infosite."""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q

from .infosite_models import InfoSiteProject, SourceDocument


@admin.register(InfoSiteProject)
class InfoSiteProjectAdmin(admin.ModelAdmin):
    """Admin interface for InfoSiteProject."""

    list_display = ["title", "domain", "document_count", "enabled", "last_generated_display"]
    list_filter = ["enabled", "created_at", "domain"]
    search_fields = ["title", "domain", "description"]
    readonly_fields = ["created_at", "updated_at", "last_generated"]

    fieldsets = (
        ("Basic Information", {"fields": ["title", "domain", "description", "enabled"]}),
        ("Source Documents", {"fields": ["source_directory"]}),
        ("Status", {"fields": ["created_at", "updated_at", "last_generated"]}),
    )

    def document_count(self, obj: InfoSiteProject) -> str:
        """Display number of associated documents."""
        count = obj.documents.count()
        imported = obj.documents.filter(imported=True).count()
        return format_html(f"{imported}/{count} imported")

    document_count.short_description = "Documents"

    def last_generated_display(self, obj: InfoSiteProject) -> str:
        """Display last generation time."""
        if obj.last_generated:
            return format_html(f"<small>{obj.last_generated.strftime('%Y-%m-%d %H:%M')}</small>")
        return "Never"

    last_generated_display.short_description = "Last Generated"


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    """Admin interface for SourceDocument."""

    list_display = ["title", "project", "file_type", "imported_badge", "imported_at"]
    list_filter = ["project", "file_type", "imported", "created_at"]
    search_fields = ["file_path", "title"]
    readonly_fields = ["created_at", "updated_at", "imported_at"]

    fieldsets = (
        ("Document", {"fields": ["project", "file_path", "title", "file_type"]}),
        ("Import Status", {"fields": ["imported", "imported_at"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    )

    def imported_badge(self, obj: SourceDocument) -> str:
        """Display import status as badge."""
        if obj.imported:
            return format_html('<span style="color: green;">✓ Imported</span>')
        return format_html('<span style="color: orange;">⚠ Pending</span>')

    imported_badge.short_description = "Status"

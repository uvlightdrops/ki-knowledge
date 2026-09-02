"""Django admin configuration for Infosite."""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Q

from .infosite_models import InfoSiteProject, SourceDocument


@admin.register(InfoSiteProject)
class InfoSiteProjectAdmin(admin.ModelAdmin):
    """Admin interface for InfoSiteProject."""

    list_display = ["title", "domain", "working_title", "document_count", "sync_status_badge", "enabled"]
    list_filter = ["enabled", "sync_status", "auto_discover", "created_at", "domain"]
    search_fields = ["title", "domain", "description", "working_title"]
    readonly_fields = ["created_at", "updated_at", "last_generated", "last_sync_at", "sync_status", "last_sync_error"]

    fieldsets = (
        ("Basic Information", {"fields": ["title", "domain", "working_title", "description", "enabled"]}),
        ("Source Documents", {"fields": ["source_directory"]}),
        ("Auto-Discovery", {
            "fields": ["auto_discover", "sync_status", "last_sync_at", "last_sync_error"],
            "description": "Automatically discover documents from md/&lt;domain&gt;/&lt;working_title&gt;/"
        }),
        ("Status", {"fields": ["created_at", "updated_at", "last_generated"]}),
    )

    def document_count(self, obj: InfoSiteProject) -> str:
        """Display number of associated documents."""
        count = obj.documents.count()
        imported = obj.documents.filter(imported=True).count()
        return format_html("{}/{} imported", imported, count)

    document_count.short_description = "Documents"

    def sync_status_badge(self, obj: InfoSiteProject) -> str:
        """Display sync status as badge."""
        colors = {
            "pending": "gray",
            "syncing": "blue",
            "completed": "green",
            "failed": "red",
        }
        color = colors.get(obj.sync_status, "gray")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_sync_status_display()
        )

    sync_status_badge.short_description = "Sync Status"


@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    """Admin interface for SourceDocument."""

    list_display = ["title", "project", "file_type", "import_status_badge", "file_size_display", "modified_at"]
    list_filter = ["project", "file_type", "import_status", "created_at"]
    search_fields = ["file_path", "title"]
    readonly_fields = ["created_at", "updated_at", "file_size", "modified_at", "import_error"]

    fieldsets = (
        ("Document", {"fields": ["project", "file_path", "title", "file_type"]}),
        ("File Info", {"fields": ["file_size", "modified_at"]}),
        ("Import Status", {"fields": ["import_status", "imported", "imported_at", "import_error"]}),
        ("Timestamps", {"fields": ["created_at", "updated_at"]}),
    )

    def import_status_badge(self, obj: SourceDocument) -> str:
        """Display import status as badge."""
        colors = {
            "discovered": "blue",
            "pending": "orange",
            "imported": "green",
            "failed": "red",
        }
        color = colors.get(obj.import_status, "gray")
        return format_html(
            '<span style="color: {};">●</span> {}',
            color,
            obj.get_import_status_display()
        )

    import_status_badge.short_description = "Status"

    def file_size_display(self, obj: SourceDocument) -> str:
        """Display file size in human-readable format."""
        if obj.file_size is None:
            return "-"
        kb = obj.file_size / 1024
        if kb < 1024:
            return format_html("<small>{} KB</small>", f"{kb:.1f}")
        mb = kb / 1024
        return format_html("<small>{} MB</small>", f"{mb:.1f}")

    file_size_display.short_description = "Size"

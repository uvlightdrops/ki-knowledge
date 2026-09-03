"""Django models for Infosite management."""

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils import timezone

from taggit.managers import TaggableManager

from wagtail.models import DraftStateMixin, RevisionMixin, WorkflowMixin


class InfoSiteProject(models.Model):
    """Project configuration for infosite generation."""

    SYNC_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("syncing", "Syncing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]
    
    GENERATION_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("generating", "Generating"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    title = models.CharField(max_length=255, help_text="Display title for the knowledge base")
    domain = models.CharField(max_length=100, default="default", help_text="Domain/namespace for content")
    working_title = models.CharField(
        max_length=100,
        blank=True,
        help_text="Working title/project code (used in discovery: md/<domain>/<working_title>)"
    )
    description = models.TextField(blank=True, help_text="Description of this knowledge base")
    source_directory = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to source documents directory",
    )
    enabled = models.BooleanField(default=True)
    
    # Auto-discovery fields
    auto_discover = models.BooleanField(
        default=True,
        help_text="Automatically discover documents from source directory"
    )
    sync_status = models.CharField(
        max_length=20,
        choices=SYNC_STATUS_CHOICES,
        default="pending",
        help_text="Status of the last document sync"
    )
    last_sync_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last document discovery/sync"
    )
    last_sync_error = models.TextField(
        blank=True,
        help_text="Error message from last failed sync"
    )
    
    # Generation fields (Phase 2)
    generation_status = models.CharField(
        max_length=20,
        choices=GENERATION_STATUS_CHOICES,
        default="pending",
        help_text="Status of the last generation attempt"
    )
    output_dir = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to generated output directory"
    )
    generated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of last successful generation"
    )
    generation_error = models.TextField(
        blank=True,
        help_text="Error message from last failed generation"
    )
    version_count = models.IntegerField(
        default=0,
        help_text="Number of versions in _originals/ directory"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_generated = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Infosite Project"
        verbose_name_plural = "Infosite Projects"
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        """Return string representation."""
        return f"{self.title} ({self.domain})"


class SourceDocument(WorkflowMixin, DraftStateMixin, RevisionMixin, models.Model):
    """Source document for infosite generation.

    Also registered as a Wagtail snippet (see wagtail_cms/wagtail_hooks.py) so
    editors get a searchable/filterable listing UI plus optional moderation
    workflow (draft/live state, revisions, GroupApprovalTask) on top of the
    canonical discovery/import data below - without duplicating it.
    """

    FILE_TYPES = [
        ("pdf", "PDF"),
        ("markdown", "Markdown"),
        ("text", "Text"),
        ("other", "Other"),
    ]
    
    IMPORT_STATUS = [
        ("discovered", "Discovered"),
        ("pending", "Pending Import"),
        ("imported", "Imported"),
        ("failed", "Failed"),
    ]

    REVIEW_STATUS = [
        ("none", "Nicht bewertet"),
        ("in_review", "In Prüfung"),
        ("approved", "Freigegeben"),
        ("rejected", "Abgelehnt"),
    ]

    project = models.ForeignKey(InfoSiteProject, on_delete=models.CASCADE, related_name="documents")
    file_path = models.CharField(max_length=500, help_text="Path to the document file")
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default="other")
    title = models.CharField(max_length=255, blank=True)
    
    # Size and metadata
    file_size = models.IntegerField(null=True, blank=True, help_text="File size in bytes")
    modified_at = models.DateTimeField(null=True, blank=True, help_text="File modification time")
    
    # Import tracking
    import_status = models.CharField(
        max_length=20,
        choices=IMPORT_STATUS,
        default="discovered",
        help_text="Current import status"
    )
    imported = models.BooleanField(default=False)
    imported_at = models.DateTimeField(null=True, blank=True)
    import_error = models.TextField(blank=True, help_text="Error message from last failed import")

    # Editorial fields (Wagtail-Snippet-Layer, additive to the pipeline state above)
    review_status = models.CharField(
        max_length=20,
        choices=REVIEW_STATUS,
        default="none",
        help_text="Editorial review/approval status (independent of import_status).",
    )
    editor_notes = models.TextField(blank=True, help_text="Freitext-Notizen der Redaktion zu dieser Quelle.")
    tags = TaggableManager(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Required for WorkflowMixin/RevisionMixin so moderation history and
    # revisions are queryable/generic-related back to this model.
    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="source_document",
        for_concrete_model=False,
    )
    revisions = GenericRelation(
        "wagtailcore.Revision",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="source_document",
        for_concrete_model=False,
    )

    class Meta:
        verbose_name = "Source Document"
        verbose_name_plural = "Source Documents"
        ordering = ["file_path"]
        unique_together = [["project", "file_path"]]

    def __str__(self) -> str:
        """Return string representation."""
        return self.title or self.file_path
    
    @property
    def file_size_display(self) -> str:
        """Return human-readable file size."""
        if not self.file_size:
            return "unknown"
        
        size = self.file_size
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @property
    def display_path(self) -> str:
        """Return file_path relative to the project's markdown root.

        Strips the shared prefix (source_directory or the resolved
        domain/working_title root) so UI tables can show only the part of
        the path that actually distinguishes one document from another.
        """
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

        return InfoSiteSourceAdapter.relative_document_path(self.project, self.file_path)

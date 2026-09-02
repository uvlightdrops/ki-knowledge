"""Django models for Infosite management."""

from django.db import models
from django.utils import timezone


class InfoSiteProject(models.Model):
    """Project configuration for infosite generation."""

    title = models.CharField(max_length=255, help_text="Display title for the knowledge base")
    domain = models.CharField(max_length=100, default="default", help_text="Domain/namespace for content")
    description = models.TextField(blank=True, help_text="Description of this knowledge base")
    source_directory = models.CharField(
        max_length=500,
        blank=True,
        help_text="Path to source documents directory",
    )
    enabled = models.BooleanField(default=True)
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


class SourceDocument(models.Model):
    """Source document for infosite generation."""

    FILE_TYPES = [
        ("pdf", "PDF"),
        ("markdown", "Markdown"),
        ("text", "Text"),
        ("other", "Other"),
    ]

    project = models.ForeignKey(InfoSiteProject, on_delete=models.CASCADE, related_name="documents")
    file_path = models.CharField(max_length=500, help_text="Path to the document file")
    file_type = models.CharField(max_length=20, choices=FILE_TYPES, default="other")
    title = models.CharField(max_length=255, blank=True)
    imported = models.BooleanField(default=False)
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Source Document"
        verbose_name_plural = "Source Documents"
        ordering = ["file_path"]
        unique_together = [["project", "file_path"]]

    def __str__(self) -> str:
        """Return string representation."""
        return self.title or self.file_path

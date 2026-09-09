"""Django models for Infosite management."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.utils import timezone

from taggit.managers import TaggableManager

from wagtail.models import DraftStateMixin, RevisionMixin, WorkflowMixin
from wagtail.search import index


class Domain(models.Model):
    """Shared registry of knowledge domains.

    Both the legacy semantic-extraction pipeline (Jira/OWL/Markdown-workspace,
    session-scoped string domain in ``views.py``/``services.py``) and the
    InfoSite pipeline (``InfoSiteProject.domain``) use a plain domain string
    for path resolution and stay otherwise completely separate. This table is
    a lightweight, additive registry so both systems can share one list of
    known domains and one combined overview page - it does not replace either
    pipeline's own storage or scanning behaviour.

    Rows are created on demand via :func:`ensure_domain_registered`, called
    whenever either system encounters a domain (project save, directory scan,
    domain creation) - there is no separate "create domain" step required.
    """

    slug = models.SlugField(max_length=100, unique=True)
    display_name = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["slug"]

    def __str__(self) -> str:
        return self.display_name or self.slug


def ensure_domain_registered(slug: str | None, *, display_name: str | None = None) -> Domain | None:
    """Upsert a :class:`Domain` row for ``slug``, if non-empty.

    Safe to call frequently (e.g. on every project save or domain scan) -
    it's a get-or-create keyed on the slug, with an optional display-name
    backfill for previously auto-created rows.
    """

    normalized = (slug or "").strip()
    if not normalized:
        return None
    domain, created = Domain.objects.get_or_create(
        slug=normalized,
        defaults={"display_name": display_name or normalized},
    )
    if not created and display_name and not domain.display_name:
        domain.display_name = display_name
        domain.save(update_fields=["display_name"])
    return domain


class DashboardDefinition(models.Model):
    """Persistent dashboard configuration for a user/domain/area combination.

    The builder UI stores widget selections and ordering here instead of in a
    browser-only localStorage structure. This keeps dashboard layouts
    consistent across sessions and allows later composition of the actual
    function-based dashboard areas.
    """

    AREA_CHOICES = [
        ("dashboard", "Dashboard"),
        ("datasources", "Data Sources"),
        ("knowledge", "Knowledge"),
        ("infooutput", "Info Output"),
        ("admin", "Admin"),
        ("settings", "Settings"),
    ]

    slug = models.SlugField(max_length=80)
    title = models.CharField(max_length=120, default="Dashboard")
    area_key = models.CharField(max_length=40, choices=AREA_CHOICES, default="settings")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="dashboards")
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="dashboards",
    )
    layout_mode = models.CharField(max_length=20, default="grid")
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["domain__slug", "area_key", "title"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "domain", "area_key", "slug"],
                name="uniq_dashboard_owner_domain_area_slug",
            )
        ]

    def __str__(self) -> str:
        return f"{self.title} [{self.area_key}:{self.domain.slug}]"


class DashboardWidgetPlacement(models.Model):
    """A widget instance on a dashboard layout."""

    dashboard = models.ForeignKey(
        DashboardDefinition,
        on_delete=models.CASCADE,
        related_name="widgets",
    )
    widget_id = models.CharField(max_length=200)
    title_override = models.CharField(max_length=200, blank=True)
    x = models.PositiveIntegerField(default=0)
    y = models.PositiveIntegerField(default=0)
    w = models.PositiveIntegerField(default=6)
    h = models.PositiveIntegerField(default=1)
    sort_index = models.PositiveIntegerField(default=0)
    config_json = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["dashboard", "sort_index", "widget_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["dashboard", "widget_id"],
                name="uniq_dashboard_widget_id",
            )
        ]

    def __str__(self) -> str:
        return f"{self.dashboard.title}:{self.widget_id}"


def _workflow_status_display(instance) -> str:
    """Human-readable label for a WorkflowMixin instance's most recent Wagtail
    workflow state, to show side-by-side with the plain ``review_status``
    field (see docs/content-model-matrix.md - the two are independent:
    review_status is a simple always-editable field, while this reflects an
    actual Wagtail moderation workflow run, if any - including finished ones,
    since ``current_workflow_state`` only exposes active (in-progress) runs).
    """

    state = instance.workflow_states.order_by("-created_at").first()
    if not state:
        return "Kein Workflow aktiv"
    label = dict(state.STATUS_CHOICES).get(state.status, state.status)
    if state.status == state.STATUS_IN_PROGRESS and state.current_task_state:
        task_name = state.current_task_state.task.specific.name
        return f"{label} ({task_name})"
    return label


class EditorialWorkflowMixin:
    """Shared helpers for the CMS-enabled editorial entities."""

    @property
    def workflow_status_display(self) -> str:
        return _workflow_status_display(self)


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
    site_structure = models.JSONField(
        default=dict,
        blank=True,
        help_text="Preferred ordering of top-level sections for the generated infosite. Can be a list of section titles or a nested tree structure.",
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
    generate_html_site = models.BooleanField(
        default=False,
        help_text="Default setting: also generate a static HTML website alongside the markdown output."
    )
    html_site_generated = models.BooleanField(
        default=False,
        help_text="Whether the static HTML preview for this project was already generated successfully."
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

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        ensure_domain_registered(self.domain)

    @property
    def display_output_dir(self) -> str:
        """Return the generated output directory relative to the data root."""
        if not self.output_dir:
            return ""
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

        return InfoSiteSourceAdapter.relative_output_path(self, self.output_dir)

    @property
    def display_source_dir(self) -> str:
        """Return the source directory relative to the data root when possible."""
        if not self.source_directory:
            return ""
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

        return InfoSiteSourceAdapter.relative_document_path(self, self.source_directory)


class SourceDocument(EditorialWorkflowMixin, index.Indexed, WorkflowMixin, DraftStateMixin, RevisionMixin, models.Model):
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

    search_fields = [
        index.SearchField("title", partial_match=True, boost=3),
        index.SearchField("file_path", partial_match=True),
        index.SearchField("editor_notes", partial_match=True),
        index.FilterField("project_id"),
        index.FilterField("file_type"),
        index.FilterField("import_status"),
        index.FilterField("review_status"),
    ]

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


class InfoSiteMappingRule(models.Model):
    """Explicit source-to-destination mapping for generated sections/pages.

    This is the editorial overlay on top of the canonical markdown sources:
    source documents remain the source of truth, while the mapping rule tells the
    generator how a logical source should be placed in the final InfoSite tree.
    """

    MODE_CHOICES = [
        ("auto", "Auto"),
        ("manual", "Manual"),
        ("override", "Override"),
    ]

    project = models.ForeignKey(InfoSiteProject, on_delete=models.CASCADE, related_name="mapping_rules")
    source_document = models.ForeignKey(
        SourceDocument,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mapping_rules",
        help_text="Source document that should be placed into the generated page tree.",
    )
    source_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Relative source path, e.g. anthro/sstk/10_geistige_welt/anspruch-und-ziel.md",
    )
    target_parent = models.CharField(
        max_length=200,
        blank=True,
        help_text="Parent section slug, e.g. 10_geistige_welt",
    )
    target_section = models.CharField(
        max_length=200,
        blank=True,
        help_text="Section slug or title for the generated output section",
    )
    target_title = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional override for the generated title",
    )
    target_slug = models.SlugField(max_length=200, blank=True)
    order_index = models.PositiveIntegerField(default=0)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default="manual")
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["project", "order_index", "target_section", "source_path"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "source_path"],
                name="uniq_infosite_mapping_project_source_path",
            )
        ]

    def __str__(self) -> str:
        if self.target_title:
            return f"{self.target_title} ({self.project.title})"
        target = self.target_section or self.target_parent or self.target_slug or self.source_path or "unassigned"
        return f"{target} [{self.project.title}]"

    @property
    def target_path(self) -> str:
        parts = [part for part in [self.target_parent, self.target_section, self.target_slug] if part]
        return "/".join(parts)


class GeneratedDocument(EditorialWorkflowMixin, index.Indexed, WorkflowMixin, DraftStateMixin, RevisionMixin, models.Model):
    """A generated/refined InfoSite output file living under data_out/.

    Mirrors SourceDocument's Wagtail-editorial treatment (snippet, workflow,
    draft/live, revisions), but on the *output* side of the pipeline: rows
    here are upserted automatically by
    ki_knowledge.services.output_registry whenever InfoSiteGeneratorService
    or the AI-refinement view writes a markdown file to data_out/, so
    Wagtail always knows about output files right after they are produced
    (see docs/content-model-matrix.md and the CMS-workflow rollout plan).
    """

    AI_REFINEMENT_MODES = [
        ("", "Keine Verfeinerung (Rohausgabe)"),
        ("improve", "Improve"),
        ("structure", "Restructure"),
        ("summarize", "Summarize"),
        ("all", "All"),
    ]

    project = models.ForeignKey(
        InfoSiteProject, on_delete=models.CASCADE, related_name="generated_documents"
    )
    file_path = models.CharField(max_length=500, help_text="Path to the generated file under data_out/.")
    generated_at = models.DateTimeField(auto_now=True, help_text="Last time this file was (re-)generated/refined.")
    ai_refinement_mode = models.CharField(max_length=20, choices=AI_REFINEMENT_MODES, blank=True, default="")
    content_hash = models.CharField(max_length=64, blank=True, help_text="Short hash of the file content, for change detection.")

    # Traceability: which SourceDocuments actually fed into this output file.
    used_sources = models.ManyToManyField(
        SourceDocument, blank=True, related_name="used_in_generated_documents"
    )

    # Editorial fields, same review model as SourceDocument.
    review_status = models.CharField(
        max_length=20,
        choices=SourceDocument.REVIEW_STATUS,
        default="none",
        help_text="Editorial review/approval status for this output file.",
    )
    editor_notes = models.TextField(blank=True, help_text="Freitext-Notizen der Redaktion zu dieser Ausgabedatei.")
    tags = TaggableManager(blank=True)

    search_fields = [
        index.SearchField("file_path", partial_match=True, boost=3),
        index.SearchField("editor_notes", partial_match=True),
        index.FilterField("project_id"),
        index.FilterField("ai_refinement_mode"),
        index.FilterField("review_status"),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    workflow_states = GenericRelation(
        "wagtailcore.WorkflowState",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="generated_document",
        for_concrete_model=False,
    )
    revisions = GenericRelation(
        "wagtailcore.Revision",
        content_type_field="base_content_type",
        object_id_field="object_id",
        related_query_name="generated_document",
        for_concrete_model=False,
    )

    class Meta:
        verbose_name = "Generated Document"
        verbose_name_plural = "Generated Documents"
        ordering = ["file_path"]
        unique_together = [["project", "file_path"]]

    def __str__(self) -> str:
        """Return string representation."""
        return self.file_path

    @property
    def display_path(self) -> str:
        """Return file_path relative to the project's output root (data_out/<domain>/<working_title>/)."""
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

        return InfoSiteSourceAdapter.relative_output_path(self.project, self.file_path)

    @property
    def used_sources_summary(self) -> str:
        """Return a short "X von Y" usage summary for the project's total source documents."""
        used = self.used_sources.count()
        total = self.project.documents.count()
        return f"{used} von {total} Quellen verwendet"

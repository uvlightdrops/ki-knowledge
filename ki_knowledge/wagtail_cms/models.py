"""Wagtail page models that surface the canonical data-source layer.

These pages are read-mostly views into existing core data (InfoSiteProject /
SourceDocument, normalized through InfoSiteSourceAdapter). The goal of Phase 3
is to prove that editorial workflow (draft/review/publish, moderation,
revisions) can run on top of the canonical DataSourceDescriptor /
SourceDocumentRecord contracts without duplicating the underlying models.
"""

from __future__ import annotations

from django.db import models

from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class DataSourceIndexPage(Page):
    """Editorial landing page listing all registered canonical data sources.

    Wagtail owns the workflow (draft/review/publish + revisions) for the
    *page*; the underlying data sources themselves keep living in the
    ki_knowledge core (InfoSiteProject, SourceDocument, KnowledgeStore).
    """

    intro = RichTextField(blank=True, help_text="Editorial introduction shown above the data source catalog.")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["wagtail_cms.DataSourceDetailPage"]
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]

    class Meta:
        verbose_name = "Data Source Catalog Page"

    def get_context(self, request, *args, **kwargs):
        from ki_knowledge.django_site.infosite_models import InfoSiteProject
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter

        context = super().get_context(request, *args, **kwargs)
        projects = InfoSiteProject.objects.filter(enabled=True).order_by("title")
        context["data_sources"] = [
            {
                "project": project,
                "descriptor": InfoSiteSourceAdapter.to_descriptor(project),
            }
            for project in projects
        ]
        return context


class DataSourceDetailPage(Page):
    """Editorial detail page for a single canonical data source.

    Linked to an InfoSiteProject by id so editors can attach review notes,
    workflow state, and curated descriptions without touching the sync/
    extraction pipeline.
    """

    infosite_project_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Linked InfoSiteProject.id (canonical data source origin).",
    )
    editorial_notes = RichTextField(blank=True, help_text="Curation/review notes for this data source.")

    content_panels = Page.content_panels + [
        FieldPanel("infosite_project_id"),
        FieldPanel("editorial_notes"),
    ]

    parent_page_types = ["wagtail_cms.DataSourceIndexPage"]
    subpage_types: list[str] = []

    class Meta:
        verbose_name = "Data Source Detail Page"

    def get_context(self, request, *args, **kwargs):
        from ki_knowledge.django_site.infosite_models import InfoSiteProject
        from ki_knowledge.knowledge.adapters import InfoSiteSourceAdapter
        from ki_knowledge.knowledge.wagtail_status_mapping import describe_wagtail_equivalent

        context = super().get_context(request, *args, **kwargs)
        project = None
        descriptor = None
        source_documents = []
        status_equivalence = None
        if self.infosite_project_id:
            project = InfoSiteProject.objects.filter(id=self.infosite_project_id).first()
            if project:
                descriptor = InfoSiteSourceAdapter.to_descriptor(project)
                # Embed the real SourceDocument snippet rows (editorial review
                # status/tags/notes included) instead of the previous ad-hoc
                # descriptor-only document list - editors can jump straight
                # into the snippet editor from here.
                source_documents = project.documents.all().order_by("title")[:50]
                status_equivalence = describe_wagtail_equivalent(descriptor.status)
        context["project"] = project
        context["descriptor"] = descriptor
        context["source_documents"] = source_documents
        context["status_equivalence"] = status_equivalence
        return context


class KnowledgeBlockIndexPage(Page):
    """Editorial landing page listing InfoSite projects that have extracted
    knowledge blocks (semantic sections/paragraphs published via the
    knowledge-extraction pipeline, see docs/content-model-matrix.md Section 3).

    Like DataSourceIndexPage, this is a read-only mirror: the underlying
    KnowledgeSource/KnowledgeBlockRecord data keeps living in KnowledgeStore
    (SQLite), managed by InfoSiteBlockStorage. Wagtail only owns the
    editorial *catalog page* around it, not the blocks themselves.
    """

    intro = RichTextField(blank=True, help_text="Editorial introduction shown above the knowledge-block catalog.")

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    subpage_types = ["wagtail_cms.KnowledgeBlockDetailPage"]
    max_count = 1
    parent_page_types = ["wagtailcore.Page"]

    class Meta:
        verbose_name = "Knowledge Block Catalog Page"

    def get_context(self, request, *args, **kwargs):
        from ki_knowledge.django_site.infosite_models import InfoSiteProject
        from ki_knowledge.services.block_storage import InfoSiteBlockStorage

        context = super().get_context(request, *args, **kwargs)
        entries = []
        for project in InfoSiteProject.objects.filter(enabled=True).order_by("title"):
            storage = InfoSiteBlockStorage(project)
            try:
                block_count = len(storage.get_stored_blocks())
            except Exception:
                block_count = 0
            if block_count:
                entries.append({"project": project, "block_count": block_count})
        context["knowledge_projects"] = entries
        return context


class KnowledgeBlockDetailPage(Page):
    """Editorial detail page rendering the extracted knowledge blocks for a
    single InfoSite project, read live from InfoSiteBlockStorage/KnowledgeStore
    (no duplication - closes the gap noted in content-model-matrix.md Section 3,
    where KnowledgeSource/KnowledgeBlockRecord previously had no Wagtail
    representation at all).
    """

    infosite_project_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Linked InfoSiteProject.id whose extracted knowledge blocks are shown here.",
    )
    editorial_notes = RichTextField(blank=True, help_text="Curation/review notes for this block set.")

    content_panels = Page.content_panels + [
        FieldPanel("infosite_project_id"),
        FieldPanel("editorial_notes"),
    ]

    parent_page_types = ["wagtail_cms.KnowledgeBlockIndexPage"]
    subpage_types: list[str] = []

    class Meta:
        verbose_name = "Knowledge Block Detail Page"

    def get_context(self, request, *args, **kwargs):
        from ki_knowledge.django_site.infosite_models import InfoSiteProject
        from ki_knowledge.services.block_storage import InfoSiteBlockStorage

        context = super().get_context(request, *args, **kwargs)
        project = None
        blocks = []
        stats = {}
        if self.infosite_project_id:
            project = InfoSiteProject.objects.filter(id=self.infosite_project_id).first()
            if project:
                storage = InfoSiteBlockStorage(project)
                blocks = storage.get_stored_blocks()
                try:
                    stats = storage.get_statistics()
                except Exception:
                    stats = {}
        context["project"] = project
        context["blocks"] = blocks
        context["stats"] = stats
        return context

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

        context = super().get_context(request, *args, **kwargs)
        project = None
        descriptor = None
        documents = []
        if self.infosite_project_id:
            project = InfoSiteProject.objects.filter(id=self.infosite_project_id).first()
            if project:
                descriptor = InfoSiteSourceAdapter.to_descriptor(project)
                documents = InfoSiteSourceAdapter.to_documents(project, list(project.documents.all()[:50]))
        context["project"] = project
        context["descriptor"] = descriptor
        context["documents"] = documents
        return context

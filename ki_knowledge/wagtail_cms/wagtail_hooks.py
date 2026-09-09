"""Wagtail snippet registrations for the canonical data-source layer.

Registers ``SourceDocument`` (see ki_knowledge/django_site/infosite_models.py)
as a Wagtail snippet so editors get a searchable/filterable listing UI plus
optional moderation workflow (draft/live state, revisions, GroupApprovalTask)
on top of the existing discovery/import pipeline data - without duplicating
it. This is additive: the pipeline (discovery, import, sync) keeps writing to
the same model fields as before; the snippet registration only adds an
editorial view/workflow on top.
"""

from __future__ import annotations

from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from wagtail import hooks
from wagtail.admin.menu import MenuItem
from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from ki_knowledge.django_site.infosite_models import GeneratedDocument, SourceDocument


@hooks.register("register_admin_menu_item")
def register_back_to_main_site_menu_item():
    """Add an explicit "back to main site" link at the top of the Wagtail
    admin menu.

    The ki-knowledge main site (dashboard, data sources, knowledge, output
    areas) is a separate Django app mounted alongside Wagtail, not served
    through the Wagtail page tree - so Wagtail has no built-in "view site"
    link that makes sense here. Without this, editors have no obvious way
    back to the main app from inside /cms-admin/.
    """

    return MenuItem(
        _("🏠 Zur Hauptseite"),
        reverse("dashboard"),
        name="back-to-main-site",
        icon_name="home",
        order=-100,
    )


class EditorialSnippetViewSet(SnippetViewSet):
    """Shared defaults for CMS-enabled editorial entities."""

    list_per_page = 25
    inspect_view_enabled = True


class SourceDocumentViewSet(EditorialSnippetViewSet):
    """Editorial listing/edit UI for discovered source documents.

    Read-heavy pipeline fields (file_path, file_type, size, import_status)
    are shown but not the main editing focus; the editable surface here is
    the additive editorial layer (review_status, editor_notes, tags).
    """

    model = SourceDocument
    icon = "doc-full"
    menu_label = "Source Documents"
    menu_name = "source-documents"
    menu_order = 210
    add_to_admin_menu = True

    list_display = [
        "title",
        "display_path",
        "project",
        "file_type",
        "import_status",
        "review_status",
        "workflow_status_display",
        "updated_at",
    ]
    list_filter = ["project", "file_type", "import_status", "review_status"]
    search_fields = ["title", "file_path", "editor_notes"]

    panels = [
        FieldPanel("title"),
        FieldPanel("project"),
        FieldPanel("file_path", read_only=True),
        FieldPanel("file_type", read_only=True),
        FieldPanel("import_status", read_only=True),
        FieldPanel("review_status"),
        FieldPanel("editor_notes"),
        FieldPanel("tags"),
    ]


register_snippet(SourceDocumentViewSet)


class GeneratedDocumentViewSet(EditorialSnippetViewSet):
    """Editorial listing/edit UI for generated/refined InfoSite output files.

    Rows are upserted automatically by ki_knowledge.services.output_registry
    right after a file is written to data_out/ - this viewset is purely the
    editorial surface (review status, notes, tags) plus visibility into
    which source documents fed into each output file.
    """

    model = GeneratedDocument
    icon = "doc-full-inverse"
    menu_label = "Generated Documents"
    menu_name = "generated-documents"
    menu_order = 220
    add_to_admin_menu = True

    list_display = [
        "display_path",
        "project",
        "ai_refinement_mode",
        "review_status",
        "workflow_status_display",
        "used_sources_summary",
        "generated_at",
    ]
    list_filter = ["project", "ai_refinement_mode", "review_status"]
    search_fields = ["file_path", "editor_notes"]

    panels = [
        FieldPanel("project"),
        FieldPanel("file_path", read_only=True),
        FieldPanel("ai_refinement_mode", read_only=True),
        FieldPanel("used_sources"),
        FieldPanel("review_status"),
        FieldPanel("editor_notes"),
        FieldPanel("tags"),
    ]


register_snippet(GeneratedDocumentViewSet)


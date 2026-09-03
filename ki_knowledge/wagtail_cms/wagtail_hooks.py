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

from wagtail.admin.panels import FieldPanel
from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from ki_knowledge.django_site.infosite_models import SourceDocument


class SourceDocumentViewSet(SnippetViewSet):
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

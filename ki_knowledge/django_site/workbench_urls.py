from django.urls import path

from . import views_workbench as views


urlpatterns = [
    path("", views.workbench, name="workbench"),
    path("api/", views.api_root, name="workbench-api-root"),
    path("api/sources", views.source_list, name="workbench-sources"),
    path("api/documents", views.document_list, name="workbench-documents"),
    path("api/documents/<uuid:document_id>", views.document_detail, name="workbench-document"),
    path("api/documents/<uuid:document_id>/annotations", views.annotation_create, name="workbench-document-annotations"),
    path("api/annotations", views.annotation_list, name="workbench-annotations"),
    path("api/annotations/<uuid:annotation_id>", views.annotation_patch, name="workbench-annotation"),
    path("api/relations", views.relation_list, name="workbench-relations"),
    path("api/documents/<uuid:document_id>/drafts", views.draft_create, name="workbench-drafts"),
    path("api/drafts", views.standalone_draft_create, name="workbench-standalone-drafts"),
    path("api/documents/<uuid:document_id>/revisions", views.revision_list, name="workbench-revisions"),
    path("api/documents/<uuid:document_id>/revisions/<uuid:revision_id>", views.revision_detail, name="workbench-revision"),
    path("api/annotations/<uuid:annotation_id>/anchors", views.anchor_create, name="workbench-anchors"),
    path("api/provider", views.provider, name="workbench-provider"),
    path("api/chat/config", views.provider, name="workbench-chat-config"),
    path("api/conversations", views.conversation_list, name="workbench-conversations"),
    path("api/conversations/<uuid:conversation_id>", views.conversation_detail, name="workbench-conversation"),
    path("api/conversations/<uuid:conversation_id>/messages", views.message_create, name="workbench-messages"),
]

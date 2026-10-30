"""Private authoring objects, deliberately separate from extracted knowledge."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class WorkbenchDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("django_site.Domain", on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.ForeignKey("django_site.SourceDocument", on_delete=models.PROTECT, null=True, blank=True)
    kind = models.CharField(max_length=20, choices=[("reference", "Reference"), ("draft", "Draft")], default="reference")
    version = models.PositiveIntegerField(default=1)
    head_revision = models.ForeignKey("WorkbenchRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    origin_revision = models.ForeignKey("WorkbenchRevision", on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    title = models.CharField(max_length=255)
    capture_sha256 = models.CharField(max_length=64)
    origin_locator = models.TextField()
    origin_key = models.CharField(max_length=64, blank=True, default="")
    origin_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    @property
    def revision(self):
        return self.head_revision

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "domain", "source", "capture_sha256"],
                name="workbench_capture_unique",
            ),
            models.UniqueConstraint(
                fields=["owner", "domain", "origin_key", "capture_sha256"],
                condition=Q(kind="reference") & ~Q(origin_key=""),
                name="workbench_generic_capture_unique",
            ),
        ]


class WorkbenchRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        WorkbenchDocument, on_delete=models.PROTECT, related_name="revisions",
    )
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, blank=True)
    cause = models.CharField(max_length=20, default="capture")
    text = models.TextField()
    content_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Snapshot revisions are immutable.")
        return super().save(*args, **kwargs)


class WorkbenchAnnotation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(
        WorkbenchDocument, on_delete=models.PROTECT, related_name="annotations",
    )
    title = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=80, blank=True)
    tags = models.JSONField(default=list)
    note = models.TextField(blank=True)
    version = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    @property
    def anchor(self):
        return self.anchors.order_by("-created_at", "-id").first()

    class Meta:
        ordering = ["created_at", "id"]


class WorkbenchAnchor(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    annotation = models.ForeignKey(
        WorkbenchAnnotation, on_delete=models.PROTECT, related_name="anchors",
    )
    revision = models.ForeignKey(WorkbenchRevision, on_delete=models.PROTECT)
    representation = models.CharField(max_length=40, default="markdown-source-v1")
    offset_unit = models.CharField(max_length=30, default="unicode-codepoint")
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    exact = models.TextField()
    prefix = models.TextField(blank=True)
    suffix = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(end__gt=F("start")), name="workbench_anchor_nonempty"),
            models.UniqueConstraint(fields=["annotation", "revision"], name="workbench_anchor_revision_unique"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Snapshot anchors are immutable.")
        return super().save(*args, **kwargs)


class WorkbenchRelation(models.Model):
    TYPES = [
        ("related_to", "Related to"),
        ("supports", "Supports"),
        ("contradicts", "Contradicts"),
        ("derived_from", "Derived from"),
    ]


    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("django_site.Domain", on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source = models.ForeignKey(
        WorkbenchAnnotation, on_delete=models.PROTECT, related_name="outgoing_relations",
    )
    target = models.ForeignKey(
        WorkbenchAnnotation, on_delete=models.PROTECT, related_name="incoming_relations",
    )
    type = models.CharField(max_length=20, choices=TYPES)
    rationale = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["source", "target", "type"], name="workbench_relation_unique",
            ),
            models.CheckConstraint(
                condition=~Q(source=F("target")), name="workbench_relation_not_self",
            ),
        ]


class WorkbenchConversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    domain = models.ForeignKey("django_site.Domain", on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    document = models.ForeignKey(WorkbenchDocument, on_delete=models.PROTECT)
    revision = models.ForeignKey(WorkbenchRevision, on_delete=models.PROTECT)
    annotation = models.ForeignKey(WorkbenchAnnotation, on_delete=models.PROTECT, null=True, blank=True)
    pending_request = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "id"]


class WorkbenchMessage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(WorkbenchConversation, on_delete=models.PROTECT, related_name="messages")
    request_id = models.UUIDField()
    message = models.TextField()
    answer = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="pending")
    error = models.TextField(blank=True)
    context = models.JSONField(default=dict)
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["conversation", "request_id"], name="workbench_message_request_unique"),
        ]


class WorkbenchProposal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document = models.ForeignKey(WorkbenchDocument, on_delete=models.PROTECT, related_name="proposals")
    base_revision = models.ForeignKey(WorkbenchRevision, on_delete=models.PROTECT, related_name="+")
    request_id = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    start = models.PositiveIntegerField()
    end = models.PositiveIntegerField()
    exact = models.TextField()
    prefix = models.TextField(blank=True)
    suffix = models.TextField(blank=True)
    instruction = models.TextField()
    replacement_markdown = models.TextField(blank=True)
    rationale = models.TextField(blank=True)
    generated_response = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="generating", choices=[
        (value, value.title()) for value in ("generating", "pending", "failed", "accepted", "rejected")
    ])
    error = models.TextField(blank=True)
    provider = models.CharField(max_length=40)
    model = models.CharField(max_length=255)
    context = models.JSONField(default=dict)
    prompt_version = models.CharField(max_length=40)
    accepted_revision = models.ForeignKey(WorkbenchRevision, on_delete=models.PROTECT, null=True, blank=True, related_name="+")
    accepted_replacement = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["document", "request_id"], name="workbench_proposal_request_unique"),
            models.CheckConstraint(condition=Q(end__gt=F("start")), name="workbench_proposal_nonempty"),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            previous = type(self).objects.get(pk=self.pk)
            immutable = (
                "document_id", "base_revision_id", "request_id", "request_sha256",
                "start", "end", "exact", "prefix", "suffix", "instruction",
                "provider", "model", "context", "prompt_version",
            )
            if previous.status != "generating":
                immutable += ("replacement_markdown", "rationale", "generated_response")
            if previous.status == "accepted":
                immutable += ("accepted_revision_id", "accepted_replacement", "status")
            if any(getattr(self, field) != getattr(previous, field) for field in immutable):
                raise ValidationError("Proposal source and generated provenance are immutable.")
        return super().save(*args, **kwargs)

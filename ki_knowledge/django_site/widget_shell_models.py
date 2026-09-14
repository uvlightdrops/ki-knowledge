from __future__ import annotations

from django.db import models


class WidgetShellDefinition(models.Model):
    widget_id = models.CharField(max_length=255, unique=True)
    label = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    area = models.CharField(max_length=255, blank=True)
    category = models.CharField(max_length=255, blank=True)
    width = models.CharField(max_length=16, default="6")
    height = models.CharField(max_length=16, default="1")
    source_type = models.CharField(max_length=32, default="table")
    source_table = models.CharField(max_length=255, blank=True, default="")
    stats = models.JSONField(default=list)
    links = models.JSONField(default=list)
    rows = models.JSONField(default=list)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "django_site"

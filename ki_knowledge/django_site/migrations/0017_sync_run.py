from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_site", "0016_domain_sync_foundation"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("direction", models.CharField(choices=[("pull", "Pull"), ("push", "Push"), ("export", "Export")], max_length=20)),
                ("status", models.CharField(choices=[("started", "Started"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="started", max_length=20)),
                ("source_url", models.CharField(blank=True, max_length=500)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("error_message", models.TextField(blank=True)),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("domain", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="sync_runs", to="django_site.domain")),
                ("node", models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name="sync_runs", to="django_site.nodeconfig")),
            ],
            options={"ordering": ["-started_at", "-id"]},
        ),
    ]

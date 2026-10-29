from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("django_site", "0021_workbench_drafts_conversations")]

    operations = [
        migrations.AddField(
            model_name="workbenchdocument", name="origin_key",
            field=models.CharField(blank=True, default="", max_length=64),
        ),
        migrations.AddField(
            model_name="workbenchdocument", name="origin_metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddConstraint(
            model_name="workbenchdocument",
            constraint=models.UniqueConstraint(
                fields=("owner", "domain", "origin_key", "capture_sha256"),
                condition=models.Q(kind="reference") & ~models.Q(origin_key=""),
                name="workbench_generic_capture_unique",
            ),
        ),
    ]

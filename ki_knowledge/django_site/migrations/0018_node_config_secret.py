from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_site", "0017_sync_run"),
    ]

    operations = [
        migrations.AddField(
            model_name="nodeconfig",
            name="sync_shared_secret",
            field=models.CharField(blank=True, max_length=255),
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_site", "0015_widget_shell_source_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="domain",
            name="home_node",
            field=models.CharField(blank=True, max_length=120),
        ),
        migrations.AddField(
            model_name="domain",
            name="last_sync_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="domain",
            name="sync_mode",
            field=models.CharField(default="local", max_length=20),
        ),
        migrations.AddField(
            model_name="domain",
            name="visibility",
            field=models.CharField(default="private", max_length=20),
        ),
        migrations.CreateModel(
            name="NodeConfig",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("node_id", models.CharField(max_length=120, unique=True)),
                ("display_name", models.CharField(blank=True, max_length=150)),
                ("role", models.CharField(choices=[("standalone", "Standalone"), ("master", "Master"), ("host", "Host")], default="standalone", max_length=20)),
                ("base_url", models.URLField(blank=True)),
                ("is_enabled", models.BooleanField(default=True)),
                ("sync_on_connect", models.BooleanField(default=True)),
                ("last_seen_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["node_id"]},
        ),
    ]

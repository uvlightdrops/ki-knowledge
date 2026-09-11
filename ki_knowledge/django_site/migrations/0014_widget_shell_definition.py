from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_site", "0013_infositeproject_html_site_generated_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="WidgetShellDefinition",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("widget_id", models.CharField(max_length=255, unique=True)),
                ("label", models.CharField(blank=True, max_length=255)),
                ("description", models.TextField(blank=True)),
                ("area", models.CharField(blank=True, max_length=255)),
                ("category", models.CharField(blank=True, max_length=255)),
                ("width", models.CharField(default="6", max_length=16)),
                ("height", models.CharField(default="1", max_length=16)),
                ("stats", models.JSONField(default=list)),
                ("links", models.JSONField(default=list)),
                ("rows", models.JSONField(default=list)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]

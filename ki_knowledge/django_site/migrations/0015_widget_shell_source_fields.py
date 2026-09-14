from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_site", "0014_widget_shell_definition"),
    ]

    operations = [
        migrations.AddField(
            model_name="widgetshelldefinition",
            name="source_table",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="widgetshelldefinition",
            name="source_type",
            field=models.CharField(default="table", max_length=32),
        ),
    ]

"""Backfill the shared Domain registry from existing data.

Registers a Domain row for every InfoSiteProject.domain value already in the
database, plus every domain already discoverable by the legacy semantic
pipeline's directory scan (available_data_domains()). This is additive only
- it does not touch InfoSiteProject rows or any legacy-pipeline files.
"""

from django.db import migrations


def backfill_domains(apps, schema_editor):
    Domain = apps.get_model("django_site", "Domain")
    InfoSiteProject = apps.get_model("django_site", "InfoSiteProject")

    slugs: set[str] = set()
    for value in InfoSiteProject.objects.values_list("domain", flat=True).distinct():
        if value and value.strip():
            slugs.add(value.strip())

    try:
        from ki_knowledge.django_site.services import available_data_domains

        slugs.update(available_data_domains())
    except Exception:
        # Best-effort: legacy scan depends on filesystem layout that may not
        # exist in every environment (e.g. CI). Missing it here just means
        # those domains get registered lazily on first real use instead.
        pass

    for slug in slugs:
        Domain.objects.get_or_create(slug=slug, defaults={"display_name": slug})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('django_site', '0006_domain'),
    ]

    operations = [
        migrations.RunPython(backfill_domains, noop_reverse),
    ]

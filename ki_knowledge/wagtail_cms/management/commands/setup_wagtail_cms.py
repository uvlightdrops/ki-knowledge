"""Idempotent bootstrap for the Wagtail CMS/workflow layer.

Creates the DataSourceIndexPage as a child of the Wagtail root page if it
doesn't already exist. Safe to re-run.
"""

from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from ki_knowledge.wagtail_cms.models import DataSourceIndexPage


class Command(BaseCommand):
    help = "Bootstrap the Wagtail CMS layer: create the Data Source Catalog page under root."

    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first()
        if site is None:
            self.stderr.write(self.style.ERROR(
                "No default Wagtail Site found. Run 'python manage.py migrate' first."
            ))
            return
        root_page = site.root_page

        existing = DataSourceIndexPage.objects.first()
        if existing:
            self.stdout.write(self.style.WARNING(
                f"DataSourceIndexPage already exists: {existing.title} (id={existing.id})"
            ))
            return

        index_page = DataSourceIndexPage(
            title="Data Sources",
            slug="data-sources",
            intro="<p>Canonical data sources registered in ki-knowledge.</p>",
        )
        root_page.add_child(instance=index_page)
        index_page.save_revision().publish()

        self.stdout.write(self.style.SUCCESS(
            f"Created DataSourceIndexPage (id={index_page.id}) under root page '{root_page.title}'."
        ))

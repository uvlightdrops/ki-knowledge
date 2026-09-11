from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from ki_knowledge.django_site.dashboard_registry import widget_registry
from ki_knowledge.django_site.widget_shell_models import WidgetShellDefinition


class Command(BaseCommand):
    help = "Seed widget shell definitions from the widget registry."

    def handle(self, *args, **options):
        created = 0
        updated = 0
        with transaction.atomic():
            for spec in widget_registry().values():
                defaults = {
                    "label": spec.label,
                    "description": spec.description,
                    "area": spec.area,
                    "category": spec.category,
                    "width": str(spec.default_w),
                    "height": str(spec.default_h),
                    "stats": [],
                    "links": [],
                    "rows": [],
                }
                obj, was_created = WidgetShellDefinition.objects.update_or_create(
                    widget_id=spec.widget_id,
                    defaults=defaults,
                )
                if was_created:
                    created += 1
                else:
                    updated += 1
        self.stdout.write(self.style.SUCCESS(f"Seeded widget shells: {created} created, {updated} updated."))

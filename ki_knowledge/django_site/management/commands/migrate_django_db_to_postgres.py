"""Copy the Django/Wagtail database from the legacy SQLite file to PostgreSQL.

Dry run by default. The SQLite file is only read and stays as a backup.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core import serializers
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connections
from django.db.migrations.executor import MigrationExecutor

SOURCE = "sqlite_legacy"
TARGET = "default"
# Sessions are disposable; Wagtail's search index is backend-specific and rebuilt.
# Everything else, including content types, is copied with its primary keys so
# Wagtail's string object IDs and log entries of deleted objects stay valid.
EXCLUDED_MODELS = (
    "sessions.session",
    "wagtailsearch.indexentry",
)


def _copied_models():
    for model in apps.get_models():
        label = model._meta.label_lower
        if label in EXCLUDED_MODELS or not model._meta.managed or model._meta.proxy:
            continue
        yield label, model


def _export(path: Path) -> None:
    """Like ``dumpdata``, but also covers apps without a models.py (e.g. django_site)."""
    tables = set(connections[SOURCE].introspection.table_names())
    app_models: dict = {}
    for _label, model in _copied_models():
        if model._meta.db_table in tables:
            app_models.setdefault(model._meta.app_config, []).append(model)

    def objects():
        for model in serializers.sort_dependencies(app_models.items(), allow_cycles=True):
            yield from model._base_manager.using(SOURCE).order_by(model._meta.pk.name).iterator()

    with path.open("w", encoding="utf-8") as stream:
        serializers.serialize("json", objects(), stream=stream)


def _counts(alias: str, existing_tables: set[str]) -> dict[str, int]:
    return {
        label: model.objects.using(alias).count()
        for label, model in _copied_models()
        if model._meta.db_table in existing_tables
    }


class Command(BaseCommand):
    help = "Copy the Django DB from SQLite to the configured PostgreSQL DSN (dry run by default)."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Perform the copy.")
        parser.add_argument(
            "--confirm-services-stopped",
            action="store_true",
            help="Confirm that Django and all workers are stopped (required with --apply).",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Flush a PostgreSQL target that already contains data before loading.",
        )

    def handle(self, *args, **options):
        if SOURCE not in settings.DATABASES:
            raise CommandError("No PostgreSQL DSN configured or SQLite source file missing.")
        if connections[TARGET].vendor != "postgresql":
            raise CommandError("The default database is not PostgreSQL.")
        source_path = Path(settings.DATABASES[SOURCE]["NAME"])
        executor = MigrationExecutor(connections[SOURCE])
        if executor.migration_plan(executor.loader.graph.leaf_nodes()):
            raise CommandError(f"Unapplied migrations in {source_path}; run them on SQLite first.")

        source_counts = _counts(SOURCE, set(connections[SOURCE].introspection.table_names()))
        self.stdout.write(f"Source: {source_path}")
        self.stdout.write(f"Target: {connections[TARGET].settings_dict['HOST']}/{connections[TARGET].settings_dict['NAME']}")
        self.stdout.write(f"{sum(source_counts.values())} rows in {sum(1 for n in source_counts.values() if n)} models to copy.")
        if not options["apply"]:
            for label, count in sorted(source_counts.items()):
                if count:
                    self.stdout.write(f"  {label}: {count}")
            self.stdout.write("Dry run. Re-run with --apply --confirm-services-stopped.")
            return
        if not options["confirm_services_stopped"]:
            raise CommandError("Stop Django and all workers, then pass --confirm-services-stopped.")

        call_command("migrate", database=TARGET, interactive=False, verbosity=0)
        target_counts = _counts(TARGET, set(connections[TARGET].introspection.table_names()))
        # Rows seeded by migrations themselves do not count as existing data.
        seeded = {
            "contenttypes.contenttype", "auth.permission",
            "wagtailcore.page", "wagtailcore.site", "wagtailcore.locale", "wagtailcore.revision",
        }
        if any(count for label, count in target_counts.items() if label not in seeded) and not options["replace"]:
            raise CommandError("PostgreSQL target already contains data; use --replace to overwrite it.")
        call_command("flush", database=TARGET, interactive=False, inhibit_post_migrate=True, verbosity=0)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        dump_path = source_path.with_name(f"django-sqlite-export-{stamp}.json")
        _export(dump_path)
        call_command("loaddata", str(dump_path), database=TARGET, verbosity=0)

        copied = _counts(TARGET, set(connections[TARGET].introspection.table_names()))
        mismatches = {label: (count, copied.get(label)) for label, count in source_counts.items() if copied.get(label) != count}
        if mismatches:
            for label, (expected, actual) in sorted(mismatches.items()):
                self.stderr.write(f"  {label}: sqlite={expected} postgres={actual}")
            raise CommandError(f"Row counts differ in {len(mismatches)} model(s); export kept at {dump_path}.")
        # Adds content types/permissions of models that never existed in SQLite.
        call_command("migrate", database=TARGET, interactive=False, verbosity=0)
        if apps.is_installed("wagtail.search"):
            call_command("update_index", verbosity=0)
        self.stdout.write(self.style.SUCCESS(
            f"Copied {sum(copied.values())} rows. Export: {dump_path}. SQLite file left unchanged."
        ))

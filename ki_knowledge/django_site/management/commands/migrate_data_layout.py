"""Safely migrate the configured data root to a domain-first layout."""

from __future__ import annotations

import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from ki_knowledge.config_runtime import knowledge_data_root
from ki_knowledge.data_layout import DataLayout, LAYOUT_VERSION
from ki_knowledge.data_layout_migration import apply_plan, plan_migration

_SOURCE_ROOT_ENV_VARS = (
    "KNOWLEDGE_MARKDOWN_ROOT", "KICLI_MD_ROOT",
    "KNOWLEDGE_PDF_ROOT", "KICLI_PDF_ROOT",
    "KNOWLEDGE_JIRA_ROOT", "KICLI_JIRA_ROOT",
    "KNOWLEDGE_ONTOLOGY_ROOT", "KICLI_OWL_ROOT",
    "KNOWLEDGE_MIX_ROOT",
)
_DATABASE_PATH_ENV_VARS = (
    "DJANGO_DB_PATH", "KNOWLEDGE_DB_PATH",
    "JIRA_CSV_PATH",
    "JIRA_CACHE_DB", "JIRA_GRAPH_DB",
    "KNOWLEDGE_CACHE_DB", "KNOWLEDGE_GRAPH_DB",
)


class Command(BaseCommand):
    help = "Migrate the data root to v3 (DOMAIN/{md,pdf,jira,owl,mix}/), with v2 available for compatibility."

    def add_arguments(self, parser):
        parser.add_argument("--root", help="Data root (default: configured knowledge data root)")
        parser.add_argument(
            "--target-version",
            type=int,
            choices=(2, 3),
            default=LAYOUT_VERSION,
            help="Target layout version (default: latest, v3)",
        )
        parser.add_argument("--apply", action="store_true", help="Execute the plan (default: dry run)")
        parser.add_argument("--dry-run", action="store_true", help="Only print the plan (default)")
        parser.add_argument(
            "--confirm-services-stopped",
            action="store_true",
            help="Acknowledge that the dev server and all workers are already stopped",
        )

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("--apply and --dry-run are mutually exclusive")
        root = Path(options["root"]).expanduser() if options["root"] else knowledge_data_root()
        target_version = options["target_version"]
        plan = plan_migration(root, target_version=target_version)

        self.stdout.write(f"Data root: {root}")
        self.stdout.write(f"Current layout: v{DataLayout(root).version}")
        self.stdout.write(f"Target layout: v{target_version}")
        self.stdout.write("")
        for op in plan.operations:
            self.stdout.write(f"  {op.describe()}")
        for table_column, count in sorted(plan.db_rows_to_rewrite.items()):
            self.stdout.write(f"  rewrite {count} stored path(s) in {table_column}")
        for warning in plan.warnings:
            self.stdout.write(self.style.WARNING(f"warning: {warning}"))

        source_overrides = [name for name in _SOURCE_ROOT_ENV_VARS if os.getenv(name, "").strip()]
        if source_overrides:
            self.stdout.write(self.style.WARNING(
                "warning: external source-root overrides are preserved as <override>/<domain> and are not migrated: "
                + ", ".join(source_overrides)
            ))
        database_overrides = [name for name in _DATABASE_PATH_ENV_VARS if os.getenv(name, "").strip()]
        if database_overrides:
            self.stdout.write(self.style.WARNING(
                "warning: these env variables pin database paths and are not migrated: "
                + ", ".join(database_overrides)
            ))
        non_sqlite = [
            alias for alias, config in settings.DATABASES.items()
            if config.get("ENGINE") != "django.db.backends.sqlite3"
        ]
        if non_sqlite:
            self.stdout.write(self.style.WARNING(
                "warning: database path references in non-SQLite Django databases cannot be rewritten: "
                + ", ".join(non_sqlite)
            ))

        if options["apply"]:
            if not options["confirm_services_stopped"]:
                raise CommandError(
                    "refusing to apply without --confirm-services-stopped; stop the dev server and all workers first"
                )
            if source_overrides:
                raise CommandError("refusing to apply while external source-root overrides are configured")
            if database_overrides:
                raise CommandError("refusing to apply while database-path overrides are configured")
            if non_sqlite:
                raise CommandError("refusing to apply because non-SQLite stored paths cannot be rewritten")

        if not plan.ok:
            for conflict in plan.conflicts:
                self.stderr.write(self.style.ERROR(f"conflict: {conflict}"))
            raise CommandError("nothing was changed")

        if not options["apply"]:
            self.stdout.write(
                f"\nDry run: {len(plan.moves)} move(s) planned. "
                "No filesystem changes or database writes were made."
            )
            return

        connections.close_all()
        result = apply_plan(plan, log=lambda line: self.stdout.write(f"  done: {line}"))
        for skipped in result.skipped:
            self.stdout.write(self.style.WARNING(skipped))
        for table_column, count in sorted(result.db_rows_rewritten.items()):
            self.stdout.write(f"  rewrote {count} stored path(s) in {table_column}")
        self.stdout.write(self.style.SUCCESS(
            f"\nLayout v{target_version} active. Journal: {result.log_path}. Restart the dev server and workers."
        ))

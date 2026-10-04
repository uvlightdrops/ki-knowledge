"""Convert the data root to the domain-first layout (v2).

Without ``--apply`` only the plan is printed. Stop the Django dev server and
any job workers before applying: they keep the old database paths open.
"""

from __future__ import annotations

import os
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from ki_knowledge.config_runtime import knowledge_data_root
from ki_knowledge.data_layout import DataLayout
from ki_knowledge.data_layout_migration import apply_plan, plan_v1_to_v2

_PATH_ENV_VARS = (
    "DJANGO_DB_PATH",
    "KNOWLEDGE_DB_PATH",
    "JIRA_CSV_PATH",
    "JIRA_CACHE_DB",
    "JIRA_GRAPH_DB",
    "KNOWLEDGE_CACHE_DB",
    "KNOWLEDGE_GRAPH_DB",
)


class Command(BaseCommand):
    help = "Migrate the data root from layout v1 (md/, pdf/, jira/ ...) to v2 (domains/<domain>/...)."

    def add_arguments(self, parser):
        parser.add_argument("--root", help="Data root (default: configured knowledge data root)")
        parser.add_argument("--apply", action="store_true", help="Execute the plan (default: dry run)")
        parser.add_argument("--dry-run", action="store_true", help="Only print the plan (default)")

    def handle(self, *args, **options):
        if options["apply"] and options["dry_run"]:
            raise CommandError("--apply and --dry-run are mutually exclusive")
        root = Path(options["root"]).expanduser() if options["root"] else knowledge_data_root()
        plan = plan_v1_to_v2(root)

        self.stdout.write(f"Data root: {root}")
        self.stdout.write(f"Current layout: v{DataLayout(root).version}")
        self.stdout.write("")
        for op in plan.operations:
            self.stdout.write(f"  {op.describe()}")
        for table_column, count in plan.db_rows_to_rewrite.items():
            self.stdout.write(f"  rewrite {count} stored path(s) in {table_column}")
        for warning in plan.warnings:
            self.stdout.write(self.style.WARNING(f"warning: {warning}"))
        env_overrides = [name for name in _PATH_ENV_VARS if os.getenv(name, "").strip()]
        if env_overrides:
            self.stdout.write(self.style.WARNING(
                "warning: these env variables pin paths and are not migrated: " + ", ".join(env_overrides)
            ))
        if not plan.ok:
            for conflict in plan.conflicts:
                self.stderr.write(self.style.ERROR(f"conflict: {conflict}"))
            raise CommandError("nothing was changed")

        if not options["apply"]:
            self.stdout.write(self.style.SUCCESS(f"\nDry run: {len(plan.moves)} move(s) planned. Re-run with --apply."))
            return

        connections.close_all()
        result = apply_plan(plan, log=lambda line: self.stdout.write(f"  done: {line}"))
        for skipped in result.skipped:
            self.stdout.write(self.style.WARNING(skipped))
        for table_column, count in result.db_rows_rewritten.items():
            self.stdout.write(f"  rewrote {count} stored path(s) in {table_column}")
        self.stdout.write(self.style.SUCCESS(
            f"\nLayout v2 active. Journal: {result.log_path}. Restart the dev server and workers."
        ))

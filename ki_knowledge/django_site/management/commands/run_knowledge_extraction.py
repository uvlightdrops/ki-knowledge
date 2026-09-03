"""Run knowledge extraction pipeline jobs without going through Django views.

This is the CLI/cron entry point for the pipeline decoupling introduced in
Schritt 4: the same ki_knowledge.services.pipeline_runner functions are used
here as in the Django views, so extraction can be triggered by a scheduler
(cron, systemd timer) with no HTTP request involved.
"""

from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.services.pipeline_runner import enqueue_and_run, run_pending_jobs


class Command(BaseCommand):
    help = "Run knowledge extraction/publish jobs for InfoSite projects (decoupled from web views)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--project",
            type=int,
            default=None,
            help="InfoSiteProject id to enqueue and run immediately.",
        )
        parser.add_argument(
            "--pending",
            action="store_true",
            help="Process all pending jobs currently queued (e.g. enqueued from the web UI).",
        )

    def handle(self, *args, **options):
        project_id = options.get("project")
        process_pending = options.get("pending")

        if not project_id and not process_pending:
            raise CommandError("Specify --project <id> or --pending")

        if project_id:
            from ki_knowledge.django_site.infosite_models import InfoSiteProject

            try:
                project = InfoSiteProject.objects.get(id=project_id)
            except InfoSiteProject.DoesNotExist:
                raise CommandError(f"InfoSiteProject {project_id} not found")

            result = enqueue_and_run(project)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Job {result['job_id']}: {result['blocks_stored']} blocks from "
                    f"{result['files_processed']} files -> source '{result['source_id']}'"
                )
            )

        if process_pending:
            result = run_pending_jobs()
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed pending jobs: claimed {result['claimed']}, "
                    f"done {result['done']}, failed {result['failed']}"
                )
            )

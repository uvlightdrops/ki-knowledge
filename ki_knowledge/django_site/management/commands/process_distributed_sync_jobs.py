"""Process pending distributed sync jobs."""

from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.services.distributed_sync_runner import enqueue_sync, run_pending_sync_jobs, run_sync_job


class Command(BaseCommand):
    help = "Process pending distributed sync jobs or enqueue and run one sync job immediately."

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            default=None,
            help="Optional domain filter for pending jobs or immediate execution.",
        )
        parser.add_argument(
            "--pending",
            action="store_true",
            help="Process queued distributed sync jobs.",
        )
        parser.add_argument(
            "--job-type",
            type=str,
            default=None,
            choices=["pull", "export"],
            help="Enqueue and run one distributed sync job immediately.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of pending jobs to process (default: 50).",
        )

    def handle(self, *args, **options):
        domain = options.get("domain")
        process_pending = options.get("pending")
        job_type = options.get("job_type")
        limit = options.get("limit", 50)

        if not process_pending and not job_type:
            raise CommandError("Specify --pending or --job-type <pull|export>")

        if job_type:
            if not domain:
                raise CommandError("--domain is required with --job-type")
            queued = enqueue_sync(domain=domain, job_type=job_type)
            result = run_sync_job(queued["job_id"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"Distributed sync job {result['job_id']} ({result['job_type']}) finished for domain {result['domain']}"
                )
            )

        if process_pending:
            result = run_pending_sync_jobs(domain=domain, limit=limit)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processed distributed sync jobs: claimed {result['claimed']}, "
                    f"done {result['done']}, failed {result['failed']}"
                )
            )

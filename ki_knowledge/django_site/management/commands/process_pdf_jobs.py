"""Process pending PDF import jobs."""

from django.core.management.base import BaseCommand

from ki_knowledge.django_site.services import get_pdf_batch_processor, default_semantic_domain


class Command(BaseCommand):
    help = "Process pending PDF import jobs"

    def add_arguments(self, parser):
        parser.add_argument(
            "--domain",
            type=str,
            default=None,
            help="Specific domain to process (defaults to all pending jobs)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=600,
            help="Timeout in seconds for stale jobs (default: 600)",
        )

    def handle(self, *args, **options):
        domain = options.get("domain") or default_semantic_domain()
        timeout = options.get("timeout", 600)
        verbose = options.get("verbosity", 1) > 1

        processor = get_pdf_batch_processor()

        if verbose:
            self.stdout.write(f"Processing PDF jobs for domain: {domain}")
            self.stdout.write(f"Timeout threshold: {timeout}s")

        def progress_callback(pages_processed, pages_total):
            if verbose and pages_total > 0:
                pct = int(100 * pages_processed / pages_total)
                self.stdout.write(f"  Progress: {pages_processed}/{pages_total} pages ({pct}%)", ending="\r")

        result = processor.process_pending_jobs(domain=domain, timeout_seconds=timeout, callback=progress_callback)

        self.stdout.write("\n" if verbose else "")
        self.stdout.write(
            self.style.SUCCESS(
                f"Processed {result['done']} jobs; {result['failed']} failed; "
                f"recovered {result['timed_out']} stale jobs"
            )
        )

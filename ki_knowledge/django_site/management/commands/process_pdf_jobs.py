"""Process pending PDF import jobs."""

import argparse
import os
import threading

from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.django_site.services import default_semantic_domain, get_pdf_batch_processor


class Command(BaseCommand):
    help = "Process pending PDF import jobs"

    def add_arguments(self, parser):
        scope = parser.add_mutually_exclusive_group()
        scope.add_argument(
            "--domain",
            type=str,
            default=None,
            help="Specific domain to process (defaults to the configured domain)",
        )
        scope.add_argument(
            "--all-domains",
            action="store_true",
            help="Process pending jobs across all domains",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=3600,
            help="Worker lease timeout in seconds (default: 3600)",
        )
        parser.add_argument(
            "--max-jobs",
            type=int,
            default=None,
            help="Maximum jobs this worker will claim (default: all pending)",
        )
        parser.add_argument(
            "--retry-failed",
            action="store_true",
            help="Requeue failed jobs before processing",
        )
        parser.add_argument("--worker-token", type=str, default=None, help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        domain = None if options.get("all_domains") else (options.get("domain") or default_semantic_domain())
        timeout = options.get("timeout", 3600)
        verbose = options.get("verbosity", 1) > 1

        processor = get_pdf_batch_processor()
        worker_token = options.get("worker_token")
        worker_started = False
        stop_heartbeat = threading.Event()
        heartbeat_thread = None

        if worker_token:
            worker_started = processor.worker_started(worker_token, os.getpid())
            if not worker_started:
                raise CommandError("GUI worker reservation is missing, expired, or already finished")

            def heartbeat():
                while not stop_heartbeat.wait(10):
                    if not processor.worker_heartbeat(worker_token):
                        return

            heartbeat_thread = threading.Thread(target=heartbeat, name="pdf-worker-heartbeat", daemon=True)
            heartbeat_thread.start()

        try:
            retried = 0
            if options.get("retry_failed"):
                retried = processor.retry_failed_jobs(domain=domain)["retried"]

            if verbose:
                self.stdout.write(f"Processing PDF jobs for domain: {domain or 'all domains'}")
                self.stdout.write(f"Timeout threshold: {timeout}s")
                if options.get("max_jobs") is not None:
                    self.stdout.write(f"Maximum jobs: {options['max_jobs']}")

            def progress_callback(pages_processed, pages_total):
                if verbose and pages_total > 0:
                    pct = int(100 * pages_processed / pages_total)
                    self.stdout.write(f"  Progress: {pages_processed}/{pages_total} pages ({pct}%)", ending="\r")

            result = processor.process_pending_jobs(
                domain=domain,
                timeout_seconds=timeout,
                callback=progress_callback,
                max_jobs=options.get("max_jobs"),
            )

            self.stdout.write("\n" if verbose else "")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Claimed {result['claimed']} jobs; {result['done']} done; {result['failed']} failed; "
                    f"expired leases {result['timed_out']}; requeued failed {retried}"
                )
            )
        except Exception as exc:
            if worker_token and worker_started:
                processor.finish_worker(worker_token, error_message=str(exc))
            raise
        finally:
            if heartbeat_thread is not None:
                stop_heartbeat.set()
                heartbeat_thread.join(timeout=2)
            if worker_token and worker_started:
                processor.finish_worker(worker_token)

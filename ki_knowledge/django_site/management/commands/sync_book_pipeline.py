"""Recalculate the book pipeline stages (import, quality, embeddings, terms) of a domain."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ki_knowledge.django_site.book_pipeline import refresh_book_pipeline
from ki_knowledge.django_site.domain_paths import default_semantic_domain, normalize_semantic_domain


class Command(BaseCommand):
    help = "Recalculate the per-book pipeline status of a domain (read-only on sources and blocks)."

    def add_arguments(self, parser):
        parser.add_argument("--domain", default="", help="Domain slug (default: active default domain).")

    def handle(self, *args, **options):
        domain = normalize_semantic_domain(options["domain"] or default_semantic_domain())
        result = refresh_book_pipeline(domain)
        summary = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
        self.stdout.write(self.style.SUCCESS(f"[{domain}] {summary}"))

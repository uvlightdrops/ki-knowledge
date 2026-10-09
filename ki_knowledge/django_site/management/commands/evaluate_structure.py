"""Detect book outlines of a domain and compare them with reference outlines (TEI)."""

from __future__ import annotations

from django.core.management.base import BaseCommand

from ki_knowledge.django_site.book_structure import DEFAULT_METHOD, analyze_domain
from ki_knowledge.django_site.domain_paths import default_semantic_domain, normalize_semantic_domain
from ki_knowledge.integrations.structure_eval import METHODS


class Command(BaseCommand):
    help = "Detect the outline of every book and report precision/recall against reference outlines."

    def add_arguments(self, parser):
        parser.add_argument("--domain", default="", help="Domain slug (default: active default domain).")
        parser.add_argument("--method", default=DEFAULT_METHOD, choices=METHODS)
        parser.add_argument("--source", action="append", default=[], help="Only this source id (repeatable).")
        parser.add_argument("--dry-run", action="store_true", help="Do not write artifacts and pipeline status.")
        parser.add_argument("--misses", action="store_true", help="Show missed reference sections.")

    def handle(self, *args, **options):
        domain = normalize_semantic_domain(options["domain"] or default_semantic_domain())
        results = analyze_domain(
            domain, method=options["method"], source_ids=options["source"], write=not options["dry_run"]
        )
        self.stdout.write(f"{'Werk':42} {'Abschn.':>7} {'Ref':>5} {'Präz.':>6} {'Recall':>6} {'Kapitel':>7} {'PDF-ähnl.':>9}")
        evaluated = []
        for result in results:
            evaluation, flat = result["evaluation"], result["evaluation_flat"]
            name = str(result["title"] or result["source_id"])[:42]
            if evaluation is None:
                self.stdout.write(f"{name:42} {result['sections']:>7}   (ohne Referenz)")
                continue
            evaluated.append(evaluation)
            self.stdout.write(
                f"{name:42} {result['sections']:>7} {evaluation['reference']:>5} {evaluation['precision']:>6.2f} "
                f"{evaluation['recall']:>6.2f} {evaluation['titled_recall']:>7.2f} {flat['titled_recall']:>9.2f}"
            )
            if options["misses"]:
                for miss in evaluation["misses"]:
                    self.stdout.write(f"      fehlt: {miss}")
        if evaluated:
            count = len(evaluated)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Mittel über {count} Werke: Präzision {sum(e['precision'] for e in evaluated) / count:.2f}, "
                    f"Kapitel-Recall {sum(e['titled_recall'] for e in evaluated) / count:.2f}"
                )
            )
        self.stdout.write(f"{len(results)} Bücher analysiert ({options['method']}).")

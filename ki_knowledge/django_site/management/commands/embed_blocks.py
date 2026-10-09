"""Embed the knowledge blocks of a domain with a local Ollama model (resumable)."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.django_site.block_search import domain_source_ids, embedding_settings
from ki_knowledge.django_site.book_pipeline import refresh_book_pipeline
from ki_knowledge.django_site.domain_paths import default_semantic_domain, normalize_semantic_domain
from ki_knowledge.integrations.block_embedder import embed_pending_blocks, model_key
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider
from ki_knowledge.integrations.knowledge_store import KnowledgeStore


class Command(BaseCommand):
    help = "Embed blocks without an up-to-date vector; can be interrupted and restarted."

    def add_arguments(self, parser):
        parser.add_argument("--domain", default="", help="Domain slug (default: active default domain).")
        parser.add_argument("--model", default="", help="Ollama embedding model (default: knowledge.embed_model).")
        parser.add_argument("--batch", type=int, default=32, help="Blocks per Ollama request.")
        parser.add_argument("--limit", type=int, default=0, help="Stop after this many blocks (0 = all).")
        parser.add_argument("--status", action="store_true", help="Only show embedded/total blocks.")

    def handle(self, *args, **options):
        domain = normalize_semantic_domain(options["domain"] or default_semantic_domain())
        base_url, default_model = embedding_settings()
        model = model_key(options["model"] or default_model)
        store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
        source_ids = domain_source_ids(domain)
        counts = store.embedding_counts(source_ids, model)
        self.stdout.write(f"[{domain}] {model}: {counts['embedded']}/{counts['blocks']} Blöcke eingebettet")
        if options["status"] or counts["embedded"] >= counts["blocks"]:
            return
        provider = OllamaEmbeddingProvider(base_url=base_url, model=model, timeout=300)
        try:
            provider.embed_many(["probe"])
        except Exception as exc:
            raise CommandError(f"Ollama nicht erreichbar oder Modell fehlt ({base_url}, {model}): {exc}") from exc

        total = counts["blocks"]
        start = counts["embedded"]
        report_every = max(1, 1000 // max(1, options["batch"]))

        def progress(run):
            if run.batches % report_every == 0:
                done = start + run.embedded
                remaining = (total - done) / run.rate if run.rate else 0
                self.stdout.write(
                    f"  {done}/{total} ({100 * done / total:.1f} %), {run.rate:.1f} Blöcke/s, "
                    f"Rest ~{remaining / 60:.0f} min"
                )
                self.stdout.flush()
            if run.batches % (report_every * 10) == 0:
                refresh_book_pipeline(domain)

        run = embed_pending_blocks(
            store,
            provider,
            source_ids,
            model=model,
            batch_size=max(1, options["batch"]),
            limit=options["limit"] or None,
            progress=progress,
        )
        refresh_book_pipeline(domain)
        for message in run.errors:
            self.stderr.write(f"  ! {message}")
        self.stdout.write(
            self.style.SUCCESS(
                f"[{domain}] {run.embedded} eingebettet, {run.failed} fehlgeschlagen, "
                f"{run.seconds / 60:.1f} min ({run.rate:.1f} Blöcke/s)"
            )
        )

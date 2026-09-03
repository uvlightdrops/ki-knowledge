"""Generate a synthetic markdown corpus for load/volume testing the pipeline.

Creates a configurable number of nested markdown files with realistic
heading structure (H1 -> H2 -> H3, paragraphs, tags) under
<KI_CONFIG.knowledge_data_root>/md/<domain>/<working_title>/, and
optionally registers/updates an InfoSiteProject that points at it.

Content is procedurally generated (no external/copyrighted text), so it's
safe to create arbitrarily large corpora purely for testing extraction,
sync, and the knowledge-blocks pipeline at scale.

Examples:
    # 200 files, 5 sections each, nested into 10 subfolders, under
    # domain "loadtest" / working_title "corpus-a", and create/update the
    # matching InfoSiteProject so it shows up in the infosite dashboard
    # and the Wagtail catalog immediately.
    python manage.py generate_test_corpus --domain loadtest --working-title corpus-a \\
        --files 200 --sections 5 --register-project

    # Quick small smoke corpus, directory only, no project registration.
    python manage.py generate_test_corpus --domain loadtest --working-title smoke --files 10
"""

from __future__ import annotations

import random
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

WORDS = (
    "system prozess struktur konzept modul workflow domäne wissen block "
    "quelle dokument pipeline modell schema knoten kontext ebene faktor "
    "muster einheit referenz zustand übergang analyse synthese abstraktion "
    "hierarchie kategorie eigenschaft relation graph index anfrage antwort"
).split()

TOPICS = (
    "Grundlagen", "Architektur", "Anwendungsfälle", "Historie", "Abgrenzung",
    "Methodik", "Praxisbeispiel", "Kritik", "Weiterführung", "Zusammenfassung",
)


def _lorem(rng: random.Random, n_words: int) -> str:
    return " ".join(rng.choice(WORDS) for _ in range(n_words)).capitalize() + "."


def _paragraph(rng: random.Random, sentences: int = 4) -> str:
    return " ".join(_lorem(rng, rng.randint(6, 14)) for _ in range(sentences))


def _render_file(rng: random.Random, title: str, sections: int) -> str:
    lines = [f"# {title}", ""]
    lines.append(_paragraph(rng, 2))
    lines.append("")
    for i in range(sections):
        topic = rng.choice(TOPICS)
        lines.append(f"## {i + 1}. {topic}")
        lines.append("")
        lines.append(_paragraph(rng, rng.randint(2, 5)))
        lines.append("")
        if rng.random() < 0.5:
            lines.append(f"### {topic} im Detail")
            lines.append("")
            lines.append(_paragraph(rng, 3))
            lines.append("")
    return "\n".join(lines)


class Command(BaseCommand):
    help = "Generate a synthetic markdown test corpus for pipeline/volume testing."

    def add_arguments(self, parser):
        parser.add_argument("--domain", required=True, help="Target domain, e.g. 'loadtest'.")
        parser.add_argument("--working-title", required=True, help="Target project working_title, e.g. 'corpus-a'.")
        parser.add_argument("--files", type=int, default=50, help="Number of markdown files to generate (default: 50).")
        parser.add_argument("--sections", type=int, default=4, help="Sections (H2 blocks) per file (default: 4).")
        parser.add_argument("--subfolders", type=int, default=5, help="Number of subfolders to distribute files across (default: 5).")
        parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible corpora.")
        parser.add_argument(
            "--register-project",
            action="store_true",
            help="Create or update an InfoSiteProject pointing at the generated directory.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite existing files in the target directory instead of skipping if it already has content.",
        )

    def handle(self, *args, **options):
        domain = options["domain"].strip()
        working_title = options["working_title"].strip()
        n_files = options["files"]
        n_sections = options["sections"]
        n_subfolders = max(1, options["subfolders"])
        rng = random.Random(options["seed"])

        if n_files < 1:
            raise CommandError("--files must be >= 1")

        data_root = Path(settings.KI_CONFIG.knowledge_data_root)
        target_dir = data_root / "md" / domain / working_title

        if target_dir.exists() and any(target_dir.rglob("*.md")) and not options["force"]:
            raise CommandError(
                f"{target_dir} already contains markdown files. Use --force to add more anyway, "
                f"or pick a different --working-title."
            )

        subfolders = [target_dir / f"{i:02d}_bereich" for i in range(n_subfolders)]
        for folder in subfolders:
            folder.mkdir(parents=True, exist_ok=True)

        written = 0
        for i in range(n_files):
            folder = subfolders[i % n_subfolders]
            title = f"{rng.choice(TOPICS)} {i + 1}"
            slug = title.lower().replace(" ", "-")
            file_path = folder / f"{slug}.md"
            file_path.write_text(_render_file(rng, title, n_sections), encoding="utf-8")
            written += 1

        self.stdout.write(self.style.SUCCESS(f"Generated {written} markdown files under {target_dir}"))

        if options["register_project"]:
            from ki_knowledge.django_site.infosite_models import InfoSiteProject

            project, created = InfoSiteProject.objects.update_or_create(
                domain=domain,
                working_title=working_title,
                defaults={
                    "title": f"{domain}/{working_title} (test corpus)",
                    "source_directory": str(target_dir),
                    "enabled": True,
                },
            )
            action = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action} InfoSiteProject id={project.id} ({domain}/{working_title}) -> {target_dir}"
                )
            )
            self.stdout.write(
                "Next steps: run 'sync'/'discover' in the infosite dashboard (or "
                "DocumentSyncService), then 'run_knowledge_extraction --project "
                f"{project.id}' to extract knowledge blocks from the new corpus."
            )

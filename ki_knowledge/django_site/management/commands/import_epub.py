"""Import one book or all EPUBs from the domain's configured EPUB folder."""

from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ki_knowledge.data_layout import EPUB
from ki_knowledge.integrations.mixed_ingest import EPUB_KIND, discover_mixed_files
from ki_knowledge.services.domain_paths import domain_source_dir


class Command(BaseCommand):
    help = "Convert domain EPUBs into Markdown chapters and register book provenance."

    def add_arguments(self, parser):
        parser.add_argument("--domain", required=True)
        parser.add_argument("--file", help="Path relative to the domain's epub/ folder; omit for all books.")

    def handle(self, *args, **options):
        from ki_knowledge.django_site.epub_import import import_epub_file
        from ki_knowledge.django_site.sources_browser import resolve_folder_file

        domain = options["domain"]
        if options["file"]:
            path = resolve_folder_file(domain, "epub", options["file"])
            if path is None or path.suffix.lower() != ".epub":
                raise CommandError("EPUB not found in the selected domain's epub/ folder.")
            paths = [path]
        else:
            paths = discover_mixed_files(domain_source_dir(EPUB, domain))[EPUB_KIND]
        if not paths:
            raise CommandError(f"No EPUB files in {domain_source_dir(EPUB, domain)}")
        for path in paths:
            try:
                result = import_epub_file(Path(path), domain=domain)
            except (ValueError, OSError) as error:
                raise CommandError(f"{path.name}: {error}") from error
            self.stdout.write(self.style.SUCCESS(
                f"{path.name}: {result['chapters']} chapters, {result['imported']} blocks; {result['markdown_dir']}",
            ))
            for warning in result["warnings"]:
                self.stderr.write(self.style.WARNING(warning))

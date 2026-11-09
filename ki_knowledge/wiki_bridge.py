"""Temporary bridge between the wiki tool and the Django app's markdown domains.

Wiki -> Django domains: ``ki_domains`` lists every Django markdown domain (and each
symlinked sub folder, whose files ``list_documents`` would otherwise skip) as a read-only
``DocumentDomain`` source with its own relation folder.

Django -> wiki: ``link_wiki`` links the wiki block folder into a Django domain's ``md``
folder, so discovery and import see the blocks as markdown sources.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from ki_knowledge.data_layout import MARKDOWN, DataLayout
from ki_knowledge.doc_viewer import list_documents

DEFAULT_RELATIONS_ROOT = Path.home() / "dev_wiki_rel_ki"
DEFAULT_WIKI_ROOT = Path.home() / "dev_wiki"
DEFAULT_WIKI_DOMAIN = "dev-wiki"
DEFAULT_WIKI_LINK = "bloecke"


class BridgeError(RuntimeError):
    pass


def _layout(layout: DataLayout | None) -> DataLayout:
    if layout is not None:
        return layout
    from ki_knowledge.services.domain_paths import data_layout

    return data_layout()


def ki_domains(relations_root: Path = DEFAULT_RELATIONS_ROOT, *, layout: DataLayout | None = None,
               exclude: list[Path] | None = None, create: bool = True) -> list[tuple[str, Path, Path]]:
    """(name, source, relation folder) for Django markdown domains, sources deduplicated.

    Sources equal to, inside or around an ``exclude`` path (e.g. the already served doc
    folder) are skipped. With ``create`` the relation folders below ``relations_root`` are made.
    """
    layout = _layout(layout)
    taken = [path.resolve() for path in exclude or []]
    candidates: list[tuple[str, Path]] = []
    for domain in sorted(layout.source_domain_names(MARKDOWN)):
        md_dir = layout.source_dir(MARKDOWN, domain)
        if not md_dir.is_dir():
            continue
        candidates.append((f"ki:{domain}", md_dir.resolve()))
        for link in sorted(md_dir.rglob("*")):
            if link.is_symlink() and link.is_dir():
                candidates.append((f"ki:{domain}/{link.relative_to(md_dir).as_posix()}", link.resolve()))
    result = []
    for name, source in candidates:
        if any(source == other or source.is_relative_to(other) or other.is_relative_to(source) for other in taken):
            continue
        if not list_documents(source):
            continue
        relations = relations_root / name.removeprefix("ki:").replace("/", "--")
        if create:
            relations.mkdir(parents=True, exist_ok=True)
        taken.append(source)
        result.append((name, source, relations))
    return result


def link_wiki(wiki_root: Path = DEFAULT_WIKI_ROOT, domain: str = DEFAULT_WIKI_DOMAIN,
              link_name: str = DEFAULT_WIKI_LINK, *, layout: DataLayout | None = None) -> tuple[Path, bool]:
    """Symlink ``wiki_root`` into ``<domain>/md/<link_name>``; returns (link, created)."""
    from ki_knowledge.services.domain_paths import validate_domain_name

    validate_domain_name(domain)
    target = wiki_root.expanduser().resolve()
    if not target.is_dir():
        raise BridgeError(f"Wiki-Verzeichnis existiert nicht: {target}")
    link = _layout(layout).source_dir(MARKDOWN, domain, link_name)
    if link.is_symlink():
        if link.resolve() != target:
            raise BridgeError(f"{link} zeigt bereits auf {link.resolve()}, nicht auf {target}")
        return link, False
    if link.exists():
        raise BridgeError(f"{link} existiert bereits und ist kein Symlink")
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(target, target_is_directory=True)
    return link, True


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Temporäre Brücke zwischen Wiki und Django-Domänen")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="Django-Markdown-Domänen anzeigen, die das Wiki einbinden würde")
    link = commands.add_parser("link-wiki", help="Wiki-Blöcke als Django-Markdown-Domäne verlinken")
    link.add_argument("--wiki", type=Path, default=DEFAULT_WIKI_ROOT)
    link.add_argument("--domain", default=DEFAULT_WIKI_DOMAIN)
    link.add_argument("--name", default=DEFAULT_WIKI_LINK)
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            for name, source, relations in ki_domains(create=False):
                print(f"{name}\t{source}\t{relations}")
        else:
            path, created = link_wiki(args.wiki, args.domain, args.name)
            print(f"{'angelegt' if created else 'vorhanden'}: {path} -> {path.resolve()}")
    except (BridgeError, ValueError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()

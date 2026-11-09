from pathlib import Path

import pytest

from ki_knowledge.data_layout import DataLayout
from ki_knowledge.wiki_bridge import BridgeError, ki_domains, link_wiki


def _write(path: Path, text: str = "# Titel\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _layout(tmp_path: Path) -> DataLayout:
    root = tmp_path / "data"
    _write(root / "anthro" / "md" / "buch" / "a.md")
    (root / "leer" / "md").mkdir(parents=True)
    _write(tmp_path / "extern" / "b.md")
    (root / "anthro" / "md" / "extern").symlink_to(tmp_path / "extern", target_is_directory=True)
    _write(tmp_path / "doc" / "c.md")
    (root / "anthro" / "md" / "doc").symlink_to(tmp_path / "doc", target_is_directory=True)
    return DataLayout(root, version=3)


def test_ki_domains_lists_markdown_domains_and_symlinked_folders(tmp_path):
    layout = _layout(tmp_path)
    relations = tmp_path / "rel"

    found = ki_domains(relations, layout=layout, exclude=[tmp_path / "doc"])

    assert [(name, source) for name, source, _ in found] == [
        ("ki:anthro", (layout.root / "anthro" / "md").resolve()),
        ("ki:anthro/extern", (tmp_path / "extern").resolve()),
    ]
    assert [path for _, _, path in found] == [relations / "anthro", relations / "anthro--extern"]
    assert all(path.is_dir() for _, _, path in found)


def test_ki_domains_without_create_leaves_relations_untouched(tmp_path):
    ki_domains(tmp_path / "rel", layout=_layout(tmp_path), create=False)

    assert not (tmp_path / "rel").exists()


def test_link_wiki_is_idempotent_and_refuses_foreign_targets(tmp_path):
    layout = _layout(tmp_path)
    wiki = tmp_path / "wiki"
    wiki.mkdir()

    link, created = link_wiki(wiki, "dev-wiki", layout=layout)
    assert created and link.resolve() == wiki.resolve()
    assert link_wiki(wiki, "dev-wiki", layout=layout) == (link, False)

    other = tmp_path / "other"
    other.mkdir()
    with pytest.raises(BridgeError):
        link_wiki(other, "dev-wiki", layout=layout)


def test_link_wiki_requires_existing_wiki(tmp_path):
    with pytest.raises(BridgeError):
        link_wiki(tmp_path / "fehlt", "dev-wiki", layout=_layout(tmp_path))

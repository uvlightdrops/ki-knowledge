"""Filesystem/domain contracts without application databases or web adapters."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from ki_knowledge.data_layout import DOMAIN_STATE_FILES, MARKDOWN, PDF, DataLayout
from ki_knowledge.services import domain_paths


@pytest.fixture(autouse=True)
def clear_link_cache():
    domain_paths._LINKED_DIRS_CACHE.clear()
    yield
    domain_paths._LINKED_DIRS_CACHE.clear()


@pytest.mark.parametrize(
    "value,semantic,registry",
    [
        (None, "default", "default"), (" ", "default", "default"),
        (" Anthro ", "anthro", "anthro"), ("A.B", "a.b", "a-b"),
        ("A_B", "a_b", "a_b"), ("../A\\B", "a-b", "a-b"),
        ("._-", "default", "default"),
    ],
)
def test_existing_slug_policies_are_preserved(value, semantic, registry):
    assert domain_paths.normalize_semantic_domain(value) == semantic
    assert domain_paths.normalize_registry_domain(value) == registry


def test_default_domain_override_precedence(monkeypatch):
    monkeypatch.delenv("KNOWLEDGE_DOMAIN", raising=False)
    monkeypatch.delenv("KICLI_DOMAIN", raising=False)
    monkeypatch.setenv("KNOWLEDGE_DEFAULT_DOMAIN", "registry-only")
    assert domain_paths.default_semantic_domain() == "default"
    monkeypatch.setenv("KICLI_DOMAIN", " Older.Name ")
    assert domain_paths.default_semantic_domain() == "older.name"
    monkeypatch.setenv("KNOWLEDGE_DOMAIN", " Preferred ")
    assert domain_paths.default_semantic_domain() == "preferred"


@pytest.mark.parametrize("version", [1, 2, 3])
def test_paths_keep_layout_case_and_legacy_file_behavior(tmp_path, monkeypatch, version):
    layout = DataLayout(tmp_path, version=version)
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    markdown = layout.source_dir(MARKDOWN, "Anthro")
    markdown.mkdir(parents=True)
    document = markdown / "book.md"
    document.write_text("# Book", encoding="utf-8")
    state = layout.domain_state_dir("Anthro")
    state.mkdir(parents=True, exist_ok=True)
    preferred, legacy = DOMAIN_STATE_FILES["cache_db"]
    (state / legacy).write_bytes(b"legacy database")
    paths = domain_paths.domain_state_paths("anthro")
    assert domain_paths.data_root() == tmp_path
    assert domain_paths.domain_dir_name("anthro") == "Anthro"
    assert domain_paths.domain_label("anthro") == "Anthro"
    assert domain_paths.domain_markdown_dir("ANTHRO") == markdown
    assert domain_paths.infer_domain_from_path(document) == "anthro"
    assert domain_paths.infer_domain_from_path(tmp_path.parent / "outside.md") is None
    assert domain_paths.infer_domain_from_path(None) is None
    assert paths["domain"] == state
    assert paths["cache_db"] == state / preferred
    assert paths["cache_db"].read_bytes() == b"legacy database"
    assert not (state / legacy).exists()
    assert set(paths) == {"domain", *DOMAIN_STATE_FILES}
    (state / legacy).write_bytes(b"leave intact")
    assert domain_paths.domain_state_paths("anthro")["cache_db"].read_bytes() == b"legacy database"
    assert (state / legacy).read_bytes() == b"leave intact"


def test_source_override_and_pdf_creation_behavior(tmp_path, monkeypatch):
    layout = DataLayout(tmp_path / "data", {"pdf": tmp_path / "pdfs"}, version=3)
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    pdf = layout.source_dir(PDF, "alpha")
    assert pdf in domain_paths.domain_source_roots("alpha")
    assert not pdf.exists()
    assert domain_paths.domain_pdf_dir("alpha") == pdf
    assert pdf.is_dir()
    assert not domain_paths.domain_markdown_dir("alpha").exists()


def test_symlink_roots_and_loops(tmp_path, monkeypatch):
    layout = DataLayout(tmp_path / "data", version=3)
    monkeypatch.setattr(domain_paths, "data_layout", lambda: layout)
    pdf = layout.source_dir(PDF, "Alpha")
    pdf.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (pdf / "books").symlink_to(external, target_is_directory=True)
    (external / "loop").symlink_to(pdf, target_is_directory=True)
    roots = domain_paths.domain_source_roots("alpha")
    assert pdf in roots and external.resolve() in roots
    assert len(roots) == len(set(roots))


def test_config_errors_propagate(monkeypatch):
    def fail():
        raise ValueError("invalid layout configuration")

    monkeypatch.setattr(domain_paths.Config, "from_env", fail)
    with pytest.raises(ValueError, match="invalid layout configuration"):
        domain_paths.data_layout()


def test_old_import_path_exports_canonical_functions():
    from ki_knowledge.django_site import domain_paths as legacy

    for name in domain_paths.__all__:
        if name != "normalize_registry_domain":
            assert getattr(legacy, name) is getattr(domain_paths, name), name
    assert legacy._LINKED_DIRS_CACHE is domain_paths._LINKED_DIRS_CACHE


def test_django_cache_adapter_preserves_keys_and_invalidation(monkeypatch):
    from ki_knowledge.django_site import domain_paths as legacy

    cache = Mock()
    monkeypatch.setattr(legacy, "django_cache", cache)
    key = legacy._domain_summary_cache_key(" Alpha.Name ")
    assert key == "ki-knowledge:domain-summary:alpha.name"
    legacy._cached_set(key, {"sources": 1})
    cache.set.assert_called_once_with(key, {"sources": 1}, timeout=60)
    cache.get.return_value = {"sources": 1}
    assert legacy._cached_get(key) == {"sources": 1}
    legacy.invalidate_domain_summary_cache("Alpha.Name")
    assert [call.args[0] for call in cache.delete.call_args_list] == [
        key, "ki-knowledge:domain-source-ids:alpha.name",
    ]


def test_service_facade_keeps_distinct_registry_defaults(monkeypatch):
    from ki_knowledge.django_site import services

    monkeypatch.delenv("KNOWLEDGE_DEFAULT_DOMAIN", raising=False)
    monkeypatch.setenv("KNOWLEDGE_DOMAIN", "filesystem-default")
    monkeypatch.setattr("ki_knowledge.django_site.domain_registry.available_data_domains", lambda: ["alpha", "beta"])
    assert services.default_semantic_domain() == "alpha"
    assert services.normalize_semantic_domain("A.B") == "a-b"
    assert domain_paths.normalize_semantic_domain("A.B") == "a.b"
    monkeypatch.setenv("KNOWLEDGE_DEFAULT_DOMAIN", "Registry.Name")
    assert services.default_semantic_domain() == "registry-name"
    assert domain_paths.default_semantic_domain() == "filesystem-default"


def test_service_import_does_not_load_django_or_api():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from ki_knowledge.services.domain_paths import domain_state_paths
assert not any(name.startswith(("django", "fastapi", "ki_knowledge.api", "ki_knowledge.django_site")) for name in sys.modules)
"""],
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

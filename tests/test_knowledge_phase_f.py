"""Tests for Phase-F workspace improvements."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.ui.knowledge_workspace import (
    WorkspaceState,
    add_snapshot,
    build_markdown_tree,
    diff_snapshot,
    is_favorite_file,
    load_workspace_state,
    mark_recent_file,
    restore_snapshot,
    save_workspace_state,
    set_favorite_file,
    snapshots_for_file,
)


def test_workspace_state_persists_recents_favorites_and_snapshots(tmp_path: Path):
    state = WorkspaceState()
    file_path = tmp_path / "doc.md"
    file_path.write_text("# One\n", encoding="utf-8")

    mark_recent_file(state, str(file_path))
    set_favorite_file(state, str(file_path), True)
    add_snapshot(state, str(file_path), "# One\n", label="initial")
    add_snapshot(state, str(file_path), "# Two\n", label="second")
    save_workspace_state(tmp_path, state)

    reloaded = load_workspace_state(tmp_path)
    assert reloaded.recent_files[0] == str(file_path)
    assert is_favorite_file(reloaded, file_path)
    assert snapshots_for_file(reloaded, str(file_path))[0]["label"] == "second"
    assert restore_snapshot(reloaded, str(file_path), 1) == "# One\n"
    assert "@@" in diff_snapshot(reloaded, str(file_path), 0, current_content="# Three\n")


def test_build_markdown_tree_groups_files_by_directory(tmp_path: Path):
    root = tmp_path / "dev_data"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "a.md").write_text("# A\n", encoding="utf-8")
    (nested / "b.md").write_text("# B\n", encoding="utf-8")

    tree = build_markdown_tree(root)

    assert tree is not None
    assert tree.files[0].name == "a.md"
    assert "nested" in tree.children
    assert tree.children["nested"].files[0].name == "b.md"
    assert sorted(path.name for path in tree.iter_files()) == ["a.md", "b.md"]


def test_markdown_import_can_filter_block_types(tmp_path: Path):
    db_path = tmp_path / "phase_f.sqlite"
    store = KnowledgeStore(db_path)
    md = tmp_path / "sample.md"
    md.write_text("# Title\n\nParagraph\n\n- Item\n", encoding="utf-8")

    blocks = store.import_markdown_file(md, allowed_block_types=["paragraph", "list_item"])

    assert all(block.block_type in {"heading", "paragraph", "list_item"} for block in blocks)
    assert any(block.block_type == "heading" for block in blocks)
    assert not any(block.block_type == "code_block" for block in blocks)


def test_phase_f_generation_api_supports_new_artifacts(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "phase_f_api.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(db_path))

    import ki_knowledge.api.knowledge_app as knowledge_app

    knowledge_app._DB_PATH = str(db_path)
    client = TestClient(knowledge_app.app)

    md = tmp_path / "phase_f.md"
    md.write_text("# One\n\nSome content for the summary.\n\n## Two\n\nMore content for a glossary.\n", encoding="utf-8")
    import_response = client.post(
        "/api/knowledge/import",
        json={"path": str(md), "import_format": "markdown"},
    )
    assert import_response.status_code == 200
    source_id = f"markdown:{md.resolve()}"

    for artifact_type in ("summary_note", "glossary", "study_guide"):
        response = client.post(
            "/api/knowledge/generate",
            json={"source_id": source_id, "artifact_type": artifact_type, "max_items": 2},
        )
        assert response.status_code == 200
        assert response.json()["artifact_type"] == artifact_type

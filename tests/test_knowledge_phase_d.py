"""Tests for Phase-D Streamlit helper/client layer."""

from __future__ import annotations

import json
from pathlib import Path

from ki_knowledge.ui.knowledge_api_client import (
    KnowledgeAPIClient,
    artifact_title,
    discover_markdown_files,
    short_text,
)


def test_artifact_payload_parses_json_content():
    client = KnowledgeAPIClient("http://localhost:8090/api/knowledge")
    payload = client.artifact_payload(
        {
            "artifact_id": "artifact:test",
            "content": json.dumps({"questions": [{"id": "q1"}]}),
        }
    )
    assert payload["questions"][0]["id"] == "q1"


def test_artifact_payload_falls_back_to_raw_content():
    client = KnowledgeAPIClient("http://localhost:8090/api/knowledge")
    payload = client.artifact_payload({"artifact_id": "artifact:test", "content": "plain text"})
    assert payload["raw_content"] == "plain text"


def test_artifact_title_and_short_text_helpers():
    title = artifact_title(
        {
            "artifact_id": "artifact:quiz:test",
            "artifact_type": "generated_quiz_module",
            "metadata": {"question_count": 4},
        }
    )
    assert "generated_quiz_module" in title
    assert "(4)" in title
    assert short_text("eins zwei drei vier", limit=8).endswith("…")


def test_discover_markdown_files_finds_nested_markdown(tmp_path: Path):
    root = tmp_path / "docs"
    nested = root / "nested"
    nested.mkdir(parents=True)
    (root / "a.md").write_text("# A\n", encoding="utf-8")
    (nested / "b.md").write_text("# B\n", encoding="utf-8")
    (nested / "c.txt").write_text("ignore", encoding="utf-8")

    files = discover_markdown_files(root)

    assert [path.name for path in files] == ["a.md", "b.md"]


def test_default_markdown_directory_prefers_existing_data_dirs(monkeypatch, tmp_path: Path):
    home_dir = tmp_path / "home"
    data_dir = home_dir / "dev_data" / "kicli"
    data_dir.mkdir(parents=True)
    monkeypatch.delenv("KNOWLEDGE_MARKDOWN_ROOT", raising=False)
    monkeypatch.setenv("HOME", str(home_dir))

    from ki_knowledge.ui.knowledge_api_client import default_markdown_directory

    assert default_markdown_directory() == str(data_dir)

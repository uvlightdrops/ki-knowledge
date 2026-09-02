"""Tests for Phase-C generated learning artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator
from ki_knowledge.knowledge.ingest import KnowledgeIngestService


def _seed_source_with_content(store: KnowledgeStore) -> str:
    result = KnowledgeIngestService(store).import_iasem_quiz_payload(
        {
            "quiz": {
                "id": "care-c",
                "title": "Care Module",
                "description": "Deeskalation und Awareness",
                "sections": [
                    {
                        "title": "Deeskalation",
                        "summary": "Ruhig sprechen und Distanz wahren.",
                        "kerninhalte": ["Ruhe", "Beobachtung", "klare Kommunikation"],
                    },
                    {
                        "title": "Awareness",
                        "summary": "Grenzen wahrnehmen und respektieren.",
                        "kerninhalte": ["Respekt", "Unterstützung", "Prävention"],
                    },
                ],
            }
        },
        source_path="/tmp/care.yaml",
        source_name="care.yaml",
    )
    return result["source_id"]


def test_generator_creates_generated_quiz_artifact(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "phase_c.sqlite")
    source_id = _seed_source_with_content(store)

    artifact = KnowledgeArtifactGenerator(store).generate_quiz_module(source_id, max_questions=2)
    payload = json.loads(artifact.content)

    assert artifact.artifact_type == "generated_quiz_module"
    assert payload["title"].startswith("Generated quiz")
    assert len(payload["questions"]) == 2
    assert payload["questions"][0]["correct_option_id"] == "A"


def test_generator_creates_flashcard_artifact(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "phase_c_cards.sqlite")
    source_id = _seed_source_with_content(store)

    artifact = KnowledgeArtifactGenerator(store).generate_flashcards(source_id, max_cards=2)
    payload = json.loads(artifact.content)

    assert artifact.artifact_type == "flashcard_set"
    assert len(payload["cards"]) == 2
    assert "front" in payload["cards"][0]
    assert "back" in payload["cards"][0]


def test_generation_api_creates_artifacts(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "phase_c_api.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(db_path))

    import ki_knowledge.api.knowledge_app as knowledge_app

    knowledge_app._DB_PATH = str(db_path)
    client = TestClient(knowledge_app.app)

    quiz_path = tmp_path / "care.yaml"
    quiz_path.write_text(
        """
quiz:
  id: care-api
  title: Care API
  description: Deeskalation
  sections:
    - title: Deeskalation
      summary: Ruhig bleiben und beobachten.
      kerninhalte:
        - Ruhe
        - Beobachten
""".strip(),
        encoding="utf-8",
    )

    import_response = client.post(
        "/api/knowledge/import",
        json={"path": str(quiz_path), "import_format": "iasem_quiz"},
    )
    assert import_response.status_code == 200
    source_id = import_response.json()["source_id"]

    quiz_response = client.post(
        "/api/knowledge/generate",
        json={"source_id": source_id, "artifact_type": "generated_quiz_module", "max_items": 1},
    )
    assert quiz_response.status_code == 200
    assert quiz_response.json()["artifact_type"] == "generated_quiz_module"

    cards_response = client.post(
        "/api/knowledge/generate",
        json={"source_id": source_id, "artifact_type": "flashcard_set", "max_items": 1},
    )
    assert cards_response.status_code == 200
    assert cards_response.json()["artifact_type"] == "flashcard_set"

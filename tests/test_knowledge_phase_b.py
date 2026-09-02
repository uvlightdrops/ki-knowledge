"""Tests for Phase-B unified knowledge runtime."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.ingest import KnowledgeIngestService
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeSource


def test_store_persists_sources_records_and_artifacts(tmp_path: Path):
    db_path = tmp_path / "phase_b.sqlite"
    store = KnowledgeStore(db_path)

    source = KnowledgeSource(
        source_id="source:test",
        source_type="manual",
        title="Test Source",
        location="/tmp/test.txt",
        metadata={"team": "knowledge"},
    )
    store.upsert_source(source)
    store.upsert_record(
        KnowledgeBlockRecord(
            block_id="block:test",
            source_id=source.source_id,
            block_type="note",
            title="Test Block",
            content="Shared runtime content",
            path="Test / Block",
            order_index=0,
            tags=["demo"],
        )
    )
    store.upsert_artifact(
        KnowledgeArtifact(
            artifact_id="artifact:test",
            artifact_type="summary",
            source_id=source.source_id,
            source_block_ids=["block:test"],
            content="Generated summary",
            metadata={"quality": "draft"},
        )
    )

    assert store.get_source(source.source_id) is not None
    assert store.get_record("block:test") is not None
    assert store.get_artifact("artifact:test") is not None
    assert len(store.list_sources()) == 1
    assert len(store.list_records(source_id=source.source_id)) == 1
    assert len(store.list_artifacts(source_id=source.source_id)) == 1


def test_iasem_quiz_import_creates_records_relations_and_artifact(tmp_path: Path):
    db_path = tmp_path / "quiz.sqlite"
    store = KnowledgeStore(db_path)
    ingest = KnowledgeIngestService(store)

    result = ingest.import_iasem_quiz_payload(
        {
            "quiz": {
                "id": "care-1",
                "title": "Awareness Basics",
                "description": "Grundlagen der Deeskalation",
                "sections": [
                    {
                        "title": "Deeskalation",
                        "summary": "Ruhe schafft Überblick",
                        "sameAs": "wd:Q5249216",
                        "kerninhalte": ["Beobachten", "ruhig sprechen"],
                    }
                ],
                "questions": [
                    {
                        "id": "q1",
                        "question": "Was hilft zuerst?",
                        "explanation": "Ruhig bleiben hilft.",
                        "sameAs": "wd:Q5249216",
                        "options": [
                            {"id": "A", "text": "Panik"},
                            {"id": "B", "text": "Deeskalation"},
                        ],
                        "correct_option_id": "B",
                    }
                ],
            }
        },
        source_path="/tmp/awareness.yaml",
        source_name="awareness.yaml",
    )

    assert result["source_id"] == "iasem-quiz:care-1"
    assert store.get_source("iasem-quiz:care-1") is not None
    question_records = store.list_records(source_id="iasem-quiz:care-1", block_type="quiz_question")
    assert len(question_records) == 1
    artifact = store.get_artifact(result["artifact_id"])
    assert artifact is not None
    payload = json.loads(artifact.content)
    assert payload["module_id"] == "care-1"
    assert payload["questions"][0]["correct_option_id"] == "B"
    assert any(relation["relation"] == "correct_option" for relation in store.list_relations(question_records[0].block_id))


def test_iasem_knowledge_style_yaml_imports_without_questions(tmp_path: Path):
    db_path = tmp_path / "knowledge_style.sqlite"
    store = KnowledgeStore(db_path)
    ingest = KnowledgeIngestService(store)

    result = ingest.import_iasem_quiz_payload(
        {
            "id": "awareness-schema",
            "title": "Awareness Schema",
            "data": {
                "AwarenessModul": {
                    "id": "modul_awareness_grundlagen_01",
                    "titel": "Trikaya Awareness",
                    "beschreibung": "Festival-Prävention",
                    "kernkonzepte": [
                        {
                            "begriff": "Awareness",
                            "definition": "Aufmerksamkeit für Grenzen.",
                            "dimensionen": ["Grenzen respektieren"],
                            "sameAs": "wd:Q72813155",
                        }
                    ],
                    "massnahmen_praevention": [
                        {
                            "bereich": "Kommunikation",
                            "handlungsanweisungen": ["Code of Conduct sichtbar machen"],
                        }
                    ],
                }
            },
        },
        source_path="/tmp/awareness.yaml",
        source_name="awareness.yaml",
    )

    assert result["source_id"] == "iasem-quiz:modul_awareness_grundlagen_01"
    sections = store.list_records(
        source_id="iasem-quiz:modul_awareness_grundlagen_01",
        block_type="knowledge_section",
    )
    assert len(sections) == 2
    artifact = store.get_artifact(result["artifact_id"])
    assert artifact is not None


def test_knowledge_api_lists_sources_records_and_artifacts(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "api.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(db_path))

    import ki_knowledge.api.knowledge_app as knowledge_app
    knowledge_app._DB_PATH = str(db_path)

    client = TestClient(knowledge_app.app)

    quiz_path = tmp_path / "quiz.yaml"
    quiz_path.write_text(
        """
quiz:
  id: care-2
  title: Team Basics
  description: Grundlagen
  questions:
    - id: q1
      question: Was hilft zuerst?
      options:
        - id: A
          text: Ruhe
        - id: B
          text: Chaos
      correct_option_id: A
""".strip(),
        encoding="utf-8",
    )

    response = client.post(
        "/api/knowledge/import",
        json={"path": str(quiz_path), "import_format": "iasem_quiz"},
    )
    assert response.status_code == 200

    sources = client.get("/api/knowledge/sources")
    assert sources.status_code == 200
    assert len(sources.json()) == 1

    records = client.get("/api/knowledge/records?source_id=iasem-quiz:care-2")
    assert records.status_code == 200
    assert any(record["block_type"] == "quiz_question" for record in records.json())

    artifacts = client.get("/api/knowledge/artifacts?source_id=iasem-quiz:care-2")
    assert artifacts.status_code == 200
    assert len(artifacts.json()) == 1

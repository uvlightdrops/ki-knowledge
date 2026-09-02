"""Tests for Phase-E graph visualization support."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.ingest import KnowledgeIngestService
from ki_knowledge.ui.knowledge_graph_viz import graph_dict_to_networkx, graph_statistics


def _seed_graph_source(store: KnowledgeStore) -> str:
    result = KnowledgeIngestService(store).import_iasem_quiz_payload(
        {
            "quiz": {
                "id": "graph-care",
                "title": "Graph Care",
                "description": "Deeskalation",
                "sections": [
                    {
                        "title": "Deeskalation",
                        "summary": "Ruhig sprechen",
                        "sameAs": "wd:Q5249216",
                        "kerninhalte": ["Ruhe", "Distanz"],
                    }
                ],
                "questions": [
                    {
                        "id": "q1",
                        "question": "Was hilft zuerst?",
                        "options": [
                            {"id": "A", "text": "Deeskalation"},
                            {"id": "B", "text": "Panik"},
                        ],
                        "correct_option_id": "A",
                    }
                ],
            }
        },
        source_path="/tmp/graph-care.yaml",
        source_name="graph-care.yaml",
    )
    return result["source_id"]


def test_source_graph_payload_contains_nodes_and_edges(tmp_path: Path):
    store = KnowledgeStore(tmp_path / "phase_e.sqlite")
    source_id = _seed_graph_source(store)

    payload = KnowledgeGraph(str(tmp_path / "phase_e.sqlite")).source_graph_payload(store, source_id)

    assert payload["source_id"] == source_id
    assert payload["node_count"] >= 4
    assert any(edge["predicate"] == "contains" for edge in payload["edges"])
    assert any(node["node_type"] == "quiz_question" for node in payload["nodes"])


def test_graph_helpers_build_statistics():
    payload = {
        "nodes": [
            {"node_id": "n1", "label": "One", "node_type": "quiz_module", "path": "A", "metadata": {}},
            {"node_id": "n2", "label": "Two", "node_type": "knowledge_section", "path": "A / B", "metadata": {}},
        ],
        "edges": [
            {"source": "n1", "target": "n2", "predicate": "contains", "weight": 1.0, "metadata": {}},
        ],
    }
    graph = graph_dict_to_networkx(payload)
    stats = graph_statistics(graph)

    assert graph.number_of_nodes() == 2
    assert graph.number_of_edges() == 1
    assert stats["node_types"]["quiz_module"] == 1
    assert stats["edge_predicates"]["contains"] == 1


def test_graph_api_returns_source_graph(tmp_path: Path, monkeypatch):
    db_path = tmp_path / "phase_e_api.sqlite"
    monkeypatch.setenv("KNOWLEDGE_DB_PATH", str(db_path))

    import ki_knowledge.api.knowledge_app as knowledge_app

    knowledge_app._DB_PATH = str(db_path)
    client = TestClient(knowledge_app.app)

    quiz_path = tmp_path / "graph.yaml"
    quiz_path.write_text(
        """
quiz:
  id: graph-api
  title: Graph API
  description: Deeskalation
  sections:
    - title: Deeskalation
      summary: Ruhig bleiben.
      kerninhalte:
        - Ruhe
""".strip(),
        encoding="utf-8",
    )

    import_response = client.post(
        "/api/knowledge/import",
        json={"path": str(quiz_path), "import_format": "iasem_quiz"},
    )
    assert import_response.status_code == 200
    source_id = import_response.json()["source_id"]

    graph_response = client.get(f"/api/knowledge/sources/{source_id}/graph")
    assert graph_response.status_code == 200
    payload = graph_response.json()
    assert payload["source_id"] == source_id
    assert payload["node_count"] >= 2

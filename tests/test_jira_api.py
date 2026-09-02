"""Smoke tests for the FastAPI service layer."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Guard: skip all API tests if fastapi/httpx not installed
pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


def _seed_cache(cache: JiraIssueCache):
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-77",
                summary="Login service failing",
                description="Customers report 500 error on login endpoint",
                status="Open",
                issue_type="Bug",
                assignee="ops@example.com",
                labels=["infra", "auth"],
                updated_at="2026-04-01T10:00",
                text_fields={"Kommentar": "API gateway auth timeout breaks login flow."},
            ),
            JiraIssue(
                key="AE-78",
                summary="FAQ page update",
                description="Add common login questions to FAQ",
                status="In Progress",
                issue_type="Task",
                assignee="support@example.com",
                labels=["faq", "auth"],
                updated_at="2026-04-02T09:00",
                text_fields={"Comment body": "Support team needs stable login troubleshooting notes."},
            ),
        ]
    )


@pytest.fixture()
def test_client(tmp_path: Path):
    """Return a TestClient with pre-seeded cache components."""
    db_path = tmp_path / "cache.sqlite"
    graph_db = tmp_path / "graph.sqlite"

    cache = JiraIssueCache(str(db_path))
    _seed_cache(cache)

    graph = JiraKnowledgeGraph(str(graph_db))
    graph.rebuild_from_cache(cache)

    mock_backend = MagicMock()
    mock_backend.chat.return_value = "Bitte prüfe AE-77 und AE-78."

    from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
    assistant = JiraSupportAssistant(backend=mock_backend, cache=cache, graph=graph)

    import ki_knowledge.api.app as api_module

    with patch.dict(os.environ, {"JIRA_CACHE_DB": str(db_path)}):
        # Patch the lazy-init globals so no real I/O happens
        api_module._cache = cache
        api_module._graph = graph
        api_module._assistant = assistant

        from ki_knowledge.api.app import app
        yield TestClient(app)

        # Cleanup: reset module globals
        api_module._cache = None
        api_module._graph = None
        api_module._assistant = None


def test_health(test_client: TestClient):
    resp = test_client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_timeline(test_client: TestClient):
    resp = test_client.get("/api/timeline?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    # At least one day entry expected from seeded data
    assert len(data) >= 1
    first = data[0]
    assert "day" in first
    assert "issue_count" in first
    assert "issue_keys" in first
    assert "topics" in first


def test_search(test_client: TestClient):
    resp = test_client.get("/api/search?q=login&limit=5")
    assert resp.status_code == 200
    hits = resp.json()
    assert isinstance(hits, list)
    assert len(hits) >= 1
    keys = [h["key"] for h in hits]
    assert "AE-77" in keys


def test_ask(test_client: TestClient):
    resp = test_client.post("/api/ask", json={"question": "login service problem", "limit": 5})
    assert resp.status_code == 200
    data = resp.json()
    assert "answer" in data
    assert "sources" in data
    assert "graph_expanded" in data
    assert isinstance(data["sources"], list)


def test_graph_neighbors(test_client: TestClient):
    resp = test_client.get("/api/graph/AE-77/neighbors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["key"] == "AE-77"
    assert isinstance(data["neighbors"], list)
    assert len(data["neighbors"]) > 0


def test_search_missing_query(test_client: TestClient):
    resp = test_client.get("/api/search")
    assert resp.status_code == 422  # validation error — q is required


def test_domain_terms_endpoint(test_client: TestClient):
    resp = test_client.get("/api/domain/terms?limit=10&min_count=1")
    assert resp.status_code == 200
    terms = resp.json()
    assert isinstance(terms, list)
    assert len(terms) >= 1
    values = {item["term"] for item in terms}
    assert "auth" in values


def test_semantic_field_endpoints(test_client: TestClient):
    rebuild = test_client.post("/api/semantic/fields/rebuild")
    assert rebuild.status_code == 200
    payload = rebuild.json()
    assert payload["embedded_fields"] >= 2

    search = test_client.get("/api/semantic/fields/search?q=login timeout&field_kind=comment")
    assert search.status_code == 200
    hits = search.json()
    assert len(hits) >= 1
    assert hits[0]["field_kind"] == "comment"


def test_semantic_term_pipeline_endpoints(test_client: TestClient):
    extract = test_client.post("/api/semantic/terms/extract?limit=20&min_count=1&promote=true")
    assert extract.status_code == 200
    payload = extract.json()
    assert payload["candidates"] >= 1
    assert payload["promoted"] >= 1

    enqueue = test_client.post("/api/semantic/enrich/enqueue?limit=20")
    assert enqueue.status_code == 200
    assert enqueue.json()["enqueued"] >= 1

    import ki_knowledge.api.app as api_module

    api_module._assistant.backend.chat.return_value = """
    {"definition":"Auth beschreibt Authentifizierung und Autorisierung.",
     "short_facts":["Auth nutzt Identitaetsmerkmale."],
     "related_terms":[{"label":"Identity","relation":"related_to","weight":0.8}],
     "confidence":0.8}
    """
    run = test_client.post("/api/semantic/enrich/run?batch_size=10")
    assert run.status_code == 200
    assert run.json()["done"] >= 1

    terms = test_client.get("/api/semantic/terms?limit=10")
    assert terms.status_code == 200
    items = terms.json()
    assert len(items) >= 1
    term_id = items[0]["term_id"]

    detail = test_client.get(f"/api/semantic/terms/{term_id}")
    assert detail.status_code == 200
    data = detail.json()
    assert "term" in data
    assert "facts" in data


def test_semantic_refine_endpoints(test_client: TestClient):
    extract = test_client.post("/api/semantic/terms/extract?limit=20&min_count=1&promote=true")
    assert extract.status_code == 200

    import ki_knowledge.api.app as api_module

    api_module._assistant.backend.chat.return_value = """
    {"definition":"Gateway steuert API-Traffic und Policy-Pruefung.",
     "short_facts":["Gateway kann Rate Limiting umsetzen."],
     "related_terms":[{"label":"Rate Limiting","relation":"related_to","weight":0.7}],
     "confidence":0.81}
    """

    plan = test_client.get("/api/semantic/refine/plan?limit=10&min_facts=3&min_relations=2&min_confidence=0.9")
    assert plan.status_code == 200
    assert "items" in plan.json()

    run = test_client.post(
        "/api/semantic/refine/run?limit=10&min_facts=3&min_relations=2&min_confidence=0.9&batch_size=10"
    )
    assert run.status_code == 200
    payload = run.json()
    assert "planned" in payload
    assert "done" in payload

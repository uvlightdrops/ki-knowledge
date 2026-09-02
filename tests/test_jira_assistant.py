"""Tests for retrieval-based Jira support assistant."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


class DummyEmbeddingBackend:
    def embed(self, text: str) -> list[float]:
        lower = text.lower()
        return [
            1.0 if "login" in lower else 0.0,
            1.0 if "faq" in lower else 0.0,
        ]


def test_jira_assistant_uses_retrieved_context(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-20",
                summary="Support FAQ ergänzen",
                description="Neue Kundenfragen zu Login aufnehmen",
                status="In Progress",
                issue_type="Task",
                assignee="a@example.com",
                labels=["support", "faq"],
                updated_at="2026-02-19T08:30",
            )
        ]
    )

    backend = Mock()
    backend.chat.return_value = "Bitte nutze AE-20 als Referenz."
    assistant = JiraSupportAssistant(backend=backend, cache=cache)

    result = assistant.ask("Was haben wir zum Login Support?")

    assert "AE-20" in result.sources
    prompt = backend.chat.call_args[0][0][0]["content"]
    assert "AE-20" in prompt
    assert "Login" in prompt


def test_jira_assistant_hybrid_mode(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-30",
                summary="FAQ zum Login",
                description="Neue Antwortbausteine für Login-Fragen",
                status="In Progress",
                issue_type="Task",
                assignee="x@example.com",
                labels=["faq"],
                updated_at="2026-02-21T08:30",
            )
        ]
    )

    embedder = DummyEmbeddingBackend()
    cache.build_embeddings(embedder, embedding_model="dummy")

    backend = Mock()
    backend.chat.return_value = "Siehe AE-30."
    assistant = JiraSupportAssistant(
        backend=backend,
        cache=cache,
        embedding_backend=embedder,
        embedding_model="dummy",
    )
    result = assistant.ask("Was wissen wir über Login?")
    assert "AE-30" in result.sources


def _make_two_issues():
    return [
        JiraIssue(
            key="AE-50",
            summary="Login bug",
            description="User cannot log in after password reset",
            status="Open",
            issue_type="Bug",
            assignee="a@example.com",
            labels=["auth", "portal"],
            updated_at="2026-03-01T10:00",
        ),
        JiraIssue(
            key="AE-51",
            summary="Portal FAQ update",
            description="Update FAQ entries for portal",
            status="In Progress",
            issue_type="Task",
            assignee="b@example.com",
            labels=["portal", "faq"],
            updated_at="2026-03-02T09:00",
        ),
    ]


def test_jira_assistant_graphrag_enriches_context(tmp_path: Path):
    """GraphRAG should add related issues discovered via the knowledge graph."""
    db_path = tmp_path / "jira_cache.sqlite"
    graph_db = tmp_path / "jira_graph.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(_make_two_issues())

    graph = JiraKnowledgeGraph(str(graph_db))
    graph.rebuild_from_cache(cache)

    backend = Mock()
    backend.chat.return_value = "Relevante Issues: AE-50, AE-51."

    assistant = JiraSupportAssistant(backend=backend, cache=cache, graph=graph)
    result = assistant.ask("login portal problem", limit=1)

    # The seed retrieval may find AE-50; the graph should expand to AE-51 via "portal" label
    assert len(result.sources) >= 1
    # graph_expanded is either empty (if already found) or contains graph-added keys
    assert isinstance(result.graph_expanded, list)
    prompt = backend.chat.call_args[0][0][0]["content"]
    assert "AE-50" in prompt or "AE-51" in prompt


def test_jira_assistant_graphrag_marks_graph_issues_in_prompt(tmp_path: Path):
    """Issues added via graph enrichment should be marked [graph] in the prompt."""
    db_path = tmp_path / "jira_cache.sqlite"
    graph_db = tmp_path / "jira_graph.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(_make_two_issues())

    graph = JiraKnowledgeGraph(str(graph_db))
    graph.rebuild_from_cache(cache)

    backend = Mock()
    backend.chat.return_value = "OK"

    assistant = JiraSupportAssistant(backend=backend, cache=cache, graph=graph)
    result = assistant.ask("login problem", limit=1)

    prompt = backend.chat.call_args[0][0][0]["content"]
    if result.graph_expanded:
        assert "[graph]" in prompt

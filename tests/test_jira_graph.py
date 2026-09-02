"""Tests for Jira knowledge graph layer."""

from pathlib import Path

from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


def test_jira_graph_build_and_neighbors(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-100",
                summary="Portal login support",
                description="Support ticket for customer login",
                status="To Do",
                issue_type="Bug",
                assignee="alice@example.com",
                labels=["support", "portal"],
                updated_at="2026-03-01T10:00",
            ),
            JiraIssue(
                key="AE-101",
                summary="Portal FAQ update",
                description="Knowledge base update",
                status="In Progress",
                issue_type="Task",
                assignee="bob@example.com",
                labels=["support", "faq"],
                updated_at="2026-03-02T09:00",
            ),
        ]
    )

    graph = JiraKnowledgeGraph(str(db_path))
    stats = graph.rebuild_from_cache(cache)
    assert stats["nodes"] > 0
    assert stats["edges"] > 0

    neighbors = graph.issue_neighbors("AE-100", limit=20)
    relation_types = {n.relation for n in neighbors}
    assert "has_label" in relation_types
    assert "assigned_to" in relation_types
    assert "related_label" in relation_types


def test_jira_graph_cypher_export(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-200",
                summary="Monitoring",
                description="Splunk alert tuning",
                status="Done",
                issue_type="Task",
                assignee="ops@example.com",
                labels=["splunk"],
                updated_at="2026-03-05T12:00",
            )
        ]
    )
    graph = JiraKnowledgeGraph(str(db_path))
    graph.rebuild_from_cache(cache)

    cypher = graph.export_cypher(limit_nodes=20, limit_edges=20)
    assert "MERGE" in cypher
    assert "issue:AE-200" in cypher

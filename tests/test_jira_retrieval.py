"""Service contracts using only temporary SQLite stores and local embeddings."""

import os
import subprocess
import sys

import pytest

from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.services.jira_retrieval import JiraRetrievalService


@pytest.fixture
def retrieval(tmp_path):
    cache = JiraIssueCache(str(tmp_path / "cache.sqlite"))
    cache.ingest_issues([
        JiraIssue(
            key="AE-1", summary="Login timeout",
            description="Login service timeout after password reset in the gateway",
            status="Open", issue_type="Bug", assignee="", labels=["auth"],
            updated_at="2026-10-28T12:00",
            text_fields={"Comment": "Login gateway timeout needs investigation by support"},
        ),
        JiraIssue(
            key="AE-2", summary="Gateway documentation", description="Gateway support",
            status="Open", issue_type="Task", assignee="", labels=["auth"],
            updated_at="2026-10-27T12:00",
        ),
    ])
    return JiraRetrievalService.from_paths(cache.db_path, tmp_path / "graph.sqlite")


def test_search_preserves_result_contract(retrieval):
    result = retrieval.hybrid_search(" login ", limit=1)
    assert set(result) == {"hits", "query", "cache_db", "issue_count", "embedding_model"}
    assert result["query"] == "login"
    assert len(result["hits"]) == 1
    assert result["hits"][0].issue.key == "AE-1"
    assert result["cache_db"] == retrieval.cache.db_path
    assert result["issue_count"] == 2
    assert result["embedding_model"] == "tfidf"


def test_empty_query_is_an_error(retrieval):
    with pytest.raises(ValueError, match="query missing"):
        retrieval.hybrid_search(" ")


def test_timeline_preserves_result_contract(retrieval):
    result = retrieval.daily_timeline(days=1)
    assert set(result) == {"timeline", "days", "cache_db", "issue_count"}
    assert result["days"] == 1
    assert len(result["timeline"]) == 1
    assert result["timeline"][0].issue_keys == ["AE-1"]


def test_graph_rebuild_and_default_issue(retrieval):
    rebuilt = retrieval.graph_explorer(issue_key=" AE-1 ", limit=1, rebuild=True)
    assert set(rebuilt) == {"issue_key", "neighbors", "stats", "graph_db", "cache_db", "issue_count"}
    assert rebuilt["issue_key"] == "AE-1"
    assert len(rebuilt["neighbors"]) == 1
    assert rebuilt["stats"]["nodes"] > 0
    assert rebuilt["stats"]["edges"] > 0
    assert retrieval.graph_explorer(issue_key="AE-1")["stats"] == rebuilt["stats"]
    assert retrieval.graph_explorer()["issue_key"] in {"AE-1", "AE-2"}


def test_domain_analysis_preserves_result_contract(retrieval):
    result = retrieval.domain_analysis(
        query=" login ", min_count=1, limit_terms=5, limit_hits=1,
    )
    assert set(result) == {
        "terms", "hits", "query", "limit_terms", "min_count", "limit_hits",
        "embedding_model", "embedded_fields", "cache_db", "issue_count",
    }
    assert result["query"] == "login"
    assert result["embedded_fields"] > 0
    assert len(result["hits"]) == 1
    assert result["terms"]


def test_empty_stores_have_explicit_empty_results(tmp_path):
    service = JiraRetrievalService.from_paths(tmp_path / "cache", tmp_path / "graph")
    with pytest.raises(RuntimeError, match="must be fit"):
        service.hybrid_search("login")
    assert service.daily_timeline()["timeline"] == []
    graph = service.graph_explorer()
    assert graph["issue_key"] == "" and graph["neighbors"] == []
    assert graph["stats"] == {"nodes": 0, "edges": 0}
    analysis = service.domain_analysis()
    assert analysis["hits"] == [] and analysis["terms"] == []
    assert analysis["embedding_model"] == "tfidf-fields-empty"


def test_embedding_failure_propagates(retrieval, monkeypatch):
    def fail(*args, **kwargs):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(retrieval.cache, "build_embeddings", fail)
    with pytest.raises(RuntimeError, match="embedding unavailable"):
        retrieval.hybrid_search("login")


def test_domain_adapters_do_not_share_runtime_or_change_environment(tmp_path, monkeypatch):
    from ki_knowledge.django_site import jira_workflow

    def paths(domain=None):
        root = tmp_path / (domain or "default")
        root.mkdir(exist_ok=True)
        return {"cache_db": root / "cache", "graph_db": root / "graph"}

    monkeypatch.setattr(jira_workflow, "domain_db_paths", paths)
    for domain, key in (("alpha", "A-1"), ("beta", "B-1")):
        cache = JiraIssueCache(str(paths(domain)["cache_db"]))
        cache.ingest_issues([JiraIssue(
            key=key, summary="Login", description="Login", status="Open",
            issue_type="Bug", assignee="", labels=[], updated_at="2026-10-28",
        )])
    before = dict(os.environ)
    for domain, key in (("alpha", "A-1"), ("beta", "B-1"), ("alpha", "A-1")):
        result = jira_workflow.jira_hybrid_search("login", domain=domain)
        assert [hit.issue.key for hit in result["hits"]] == [key]
        assert result["cache_db"] == str(paths(domain)["cache_db"])
    assert dict(os.environ) == before


def test_domain_specific_path_overrides_win(tmp_path, monkeypatch):
    from ki_knowledge.django_site import jira_workflow

    cache_path = tmp_path / "custom-cache"
    graph_path = tmp_path / "custom-graph"
    monkeypatch.setenv("JIRA_CACHE_DB_ALPHA", str(cache_path))
    monkeypatch.setenv("JIRA_GRAPH_DB_ALPHA", str(graph_path))
    monkeypatch.setenv("JIRA_CACHE_DB", str(tmp_path / "wrong-cache"))
    monkeypatch.setenv("JIRA_GRAPH_DB", str(tmp_path / "wrong-graph"))
    result = jira_workflow.jira_graph_explorer(domain="alpha")
    assert result["cache_db"] == str(cache_path)
    assert result["graph_db"] == str(graph_path)
    assert not (tmp_path / "wrong-cache").exists()
    assert not (tmp_path / "wrong-graph").exists()


def test_service_import_does_not_load_web_adapters():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from ki_knowledge.services.jira_retrieval import JiraRetrievalService
assert not any(name.startswith(("django", "fastapi", "ki_knowledge.api", "ki_knowledge.django_site")) for name in sys.modules)
"""],
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

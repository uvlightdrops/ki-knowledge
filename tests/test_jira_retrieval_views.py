"""Verify the HTML adapters and old service facade use the shared service."""

import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.http import HttpResponse
from django.test import RequestFactory

from ki_knowledge.django_site import jira_workflow, services, views_jira as views_data_sources
from ki_knowledge.services.jira_retrieval import JiraRetrievalService


@pytest.mark.parametrize(
    "view_name,method,query,arguments",
    [
        ("jira_hybrid_search_view", "hybrid_search", {"q": "login", "limit": "3"},
         {"query": "login", "limit": 3}),
        ("jira_daily_timeline_view", "daily_timeline", {"days": "7"}, {"days": 7}),
        ("jira_graph_explorer_view", "graph_explorer",
         {"issue_key": "A-1", "limit": "3", "rebuild": "1"},
         {"issue_key": "A-1", "limit": 3, "rebuild": True}),
        ("jira_domain_analysis_view", "domain_analysis",
         {"q": "login", "terms": "5", "min_count": "1", "hits": "3"},
         {"query": "login", "limit_terms": 5, "min_count": 1, "limit_hits": 3}),
    ],
)
def test_html_views_reach_shared_service(
    view_name, method, query, arguments, monkeypatch, tmp_path,
):
    service = JiraRetrievalService.from_paths(tmp_path / "cache", tmp_path / "graph")
    calls = []

    def run(self, *args, **kwargs):
        if args:
            kwargs["query"] = args[0]
        calls.append(kwargs)
        return {"result_marker": "shared"}

    monkeypatch.setattr(JiraRetrievalService, method, run)
    monkeypatch.setattr(jira_workflow, "_retrieval", lambda domain: service)
    monkeypatch.setattr(views_data_sources, "_active_semantic_domain", lambda request: "alpha")
    monkeypatch.setattr(views_data_sources, "jira_cache_db_path", lambda domain: "temporary")
    captured = {}

    def render(request, template, context):
        captured.update(context)
        return HttpResponse("ok")

    monkeypatch.setattr(views_data_sources, "render", render)
    response = getattr(views_data_sources, view_name)(RequestFactory().get("/", query))
    assert response.status_code == 200
    assert calls == [arguments]
    assert captured["active_domain"] == "alpha"
    result = captured["result"] if method == "hybrid_search" else captured
    assert result["result_marker"] == "shared"


@pytest.mark.parametrize(
    "name,args,kwargs",
    [
        ("jira_hybrid_search", ("login",), {"limit": 3}),
        ("jira_daily_timeline", (), {"days": 7}),
        ("jira_graph_explorer", (), {"issue_key": "A-1", "rebuild": True}),
        ("jira_domain_analysis", (), {"query": "login", "min_count": 1}),
    ],
)
def test_legacy_facade_preserves_domain_and_result(name, args, kwargs, monkeypatch):
    calls = []
    expected = {"marker": "unchanged"}

    def implementation(*received, **options):
        calls.append((received, options))
        return expected

    monkeypatch.setattr(jira_workflow, name, implementation)
    result = getattr(services, name)(*args, domain="alpha", **kwargs)
    assert result is expected
    assert calls[0][1]["domain"] == "alpha"
    for key, value in kwargs.items():
        assert calls[0][1][key] == value

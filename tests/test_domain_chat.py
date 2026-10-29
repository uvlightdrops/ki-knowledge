"""Domain chat contracts with synthetic corpus, local SQLite and mocked providers."""

import os
from types import SimpleNamespace

import django
import pytest
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.conf import settings
from django.test import RequestFactory
from django.urls import resolve, reverse
from ki_core.core.models import Role

from ki_knowledge.django_site import block_search, knowledge_summary, domain_registry, support_chat as services, views_common
from ki_knowledge.django_site import views_chat as views
from ki_knowledge.django_site.layout_targets import layout_targets_for_area, nav_areas_config
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.sql_backend import connect
from ki_knowledge.knowledge.contributions import export_contribution
from ki_knowledge.knowledge.models import KnowledgeBlockRecord, KnowledgeSource


class Session(dict):
    modified = False


def request(method="get", *, domain="alpha", data=None, session=None, route="support-chat"):
    req = getattr(RequestFactory(), method)(reverse(route), data or {})
    req.session = session if session is not None else Session(semantic_active_domain=domain)
    req.user = SimpleNamespace(username="test", id=1, is_authenticated=True)
    return req


@pytest.fixture
def corpus(tmp_path, monkeypatch):
    target = tmp_path / "knowledge.sqlite"
    monkeypatch.setattr(settings, "KNOWLEDGE_STORE_TARGET", target)
    roots = lambda domain: [tmp_path / domain]
    monkeypatch.setattr(knowledge_summary, "domain_source_roots", roots)
    monkeypatch.setattr(domain_registry, "domain_source_roots", roots)
    monkeypatch.setattr(block_search, "embedding_settings", lambda: ("http://unused", "nomic-embed-text"))
    monkeypatch.setattr(views, "chat_settings", lambda: {"provider": "mock", "model": "mock-1"})
    db = KnowledgeStore(target)
    for domain in ("alpha", "beta", "default"):
        for kind in ("markdown", "nextcloud_markdown", "owl", "jira_issue", "pdf", "custom"):
            sid = f"{domain}-{kind}"
            location = f"https://nextcloud.invalid/{domain}/doc.md" if kind == "nextcloud_markdown" else str(tmp_path / domain / f"{kind}.md")
            meta = {"domain": domain} if kind == "nextcloud_markdown" else {}
            db.upsert_source(KnowledgeSource(sid, kind, sid, location, meta))
            db.upsert_record(KnowledgeBlockRecord(sid, sid, "paragraph", sid, f"{domain} evidence for {kind}"))
            db.add_embedding(sid, "nomic-embed-text", [1.0, 0.0])
        origin = KnowledgeStore(tmp_path / f"{domain}-origin.sqlite")
        origin.upsert_source(KnowledgeSource("source", "custom", "Contribution", "/foreign/path"))
        origin.upsert_record(KnowledgeBlockRecord("record", "source", "paragraph", "Contribution", f"{domain} contribution evidence", object_type="text"))
        payload = export_contribution(origin, domain=domain, origin_node_id="node", revision="v1", source_ids=["source"])
        db.ingest_contribution(payload)
    for record in db.list_records():
        db.add_embedding(record.block_id, "nomic-embed-text", [1.0, 0.0])

    def forbidden(*args, **kwargs):
        raise AssertionError("No live provider, model discovery or HTTP requests in chat tests")

    monkeypatch.setattr(requests.sessions.Session, "request", forbidden)
    monkeypatch.setattr(services, "chat_client", forbidden)
    monkeypatch.setattr(views, "ollama_available_models", forbidden)
    monkeypatch.setattr(views_common, "maybe_send_automatic_heartbeat", forbidden)
    monkeypatch.setattr(block_search.OllamaEmbeddingProvider, "embed_many", lambda self, texts: [[1.0, 0.0]])
    return db


def mock_chat(monkeypatch, *, answer="Grounded answer [1]", error=None):
    calls = []

    def chat(req):
        calls.append(req)
        if error:
            raise error
        return SimpleNamespace(message=SimpleNamespace(content=answer))

    monkeypatch.setattr(services, "chat_client", lambda **kwargs: SimpleNamespace(chat=chat))
    return calls


@pytest.mark.parametrize("domain", ["alpha", "beta", "default"])
def test_retrieval_excludes_other_domains_and_includes_remote_and_contributed(corpus, domain):
    hits = services.support_search("evidence", domain=domain, limit=20)
    expected = {source.source_id for source in services._support_sources(domain)}
    assert {hit["source_id"] for hit in hits} == expected
    assert len(hits) == 7
    assert all(domain in hit["snippet"] for hit in hits)
    assert any(hit["source_type"] == "nextcloud_markdown" for hit in hits)
    assert any(hit["path"].startswith("contribution:") for hit in hits)
    assert services.support_chat_index_status(domain) == {
        "sources": 7, "model": "nomic-embed-text", "blocks": 7, "embedded": 7,
    }


def test_source_filters_keep_aliases_and_never_silently_expand_unknown(corpus):
    assert len(services.support_search("evidence", domain="alpha", source_types="all")) == 7
    assert [hit["source_type"] for hit in services.support_search("evidence", domain="alpha", source_types="csv")] == ["jira_issue"]
    assert [hit["source_type"] for hit in services.support_search("evidence", domain="alpha", source_types="nextcloud_markdown")] == ["nextcloud_markdown"]
    with pytest.raises(RuntimeError, match="Kein nutzbarer Vektorindex"):
        services.support_search("evidence", domain="alpha", source_types="typo")


def test_only_current_nonheading_vectors_and_bounded_context(corpus, monkeypatch):
    for i in range(25):
        bid = f"extra-{i}"
        corpus.upsert_record(KnowledgeBlockRecord(bid, "alpha-markdown", "paragraph", "Extra", "x" * 3000))
        corpus.add_embedding(bid, "nomic-embed-text", [1.0, 0.0])
    corpus.upsert_record(KnowledgeBlockRecord("heading", "alpha-markdown", "heading", "Heading", "not evidence"))
    corpus.add_embedding("heading", "nomic-embed-text", [1.0, 0.0])
    with connect(settings.KNOWLEDGE_STORE_TARGET) as conn:
        conn.execute("UPDATE knowledge_embeddings SET created_at = '2000-01-01' WHERE block_id = ?", ["alpha-markdown"])
    calls = mock_chat(monkeypatch)
    result = services.support_chat_answer("question", domain="alpha", limit=100)
    assert len(result["hits"]) == 20
    assert all(len(hit["snippet"]) <= 2000 for hit in result["hits"])
    assert not {"heading", "alpha-markdown"}.intersection(hit["block_id"] for hit in result["hits"])
    assert [detail["citation"] for detail in result["source_details"]] == list(range(1, 21))
    assert len(calls) == 1
    status = services.support_chat_index_status("alpha")
    assert status["embedded"] == status["blocks"] - 1


def test_canonical_get_is_local_and_has_one_chat_link(corpus):
    response = resolve(reverse("support-chat")).func(request())
    assert response.status_code == 200
    html = response.content.decode()
    assert "<h1>Domain Chat</h1>" in html
    assert html.count('href="/knowledge/chat/support/"') == 1
    assert 'href="/knowledge/chat/ollama/"' not in html
    assert "7/7" in html and "Nextcloud" in html and "Contributions" in html
    assert "2000 Zeichen" in html
    assert 'name="domain" value="alpha"' in html
    area = next(area for area in nav_areas_config() if area["key"] == "internal-knowledge")
    assert [(label, path) for label, path, _ in area["submenu"] if "/chat/" in path] == [("Chat", reverse("support-chat"))]
    assert [(t.key, t.label) for t in layout_targets_for_area("knowledge") if "/chat/" in t.path] == [("support-chat", "Chat")]


@pytest.mark.parametrize("route", ["jira-support-chat", "ollama-chat"])
def test_legacy_get_redirects_without_reading_provider_or_changing_history(corpus, route):
    session = Session(ollama_chat_history=[{"question": "old", "answer": "preserved"}])
    req = request(route=route, data={"domain": "beta"}, session=session)
    response = resolve(reverse(route)).func(req)
    assert response.status_code == 302
    assert response.url == reverse("support-chat") + "?domain=beta"
    assert session == {"ollama_chat_history": [{"question": "old", "answer": "preserved"}]}


def test_conversation_continuity_and_domain_history_isolation(corpus, monkeypatch):
    calls = mock_chat(monkeypatch)
    session = Session(
        semantic_active_domain="alpha",
        jira_support_chat_history=[{"question": "LEGACY secret", "answer": "secret source"}],
        ollama_chat_history=[{"question": "FREE secret", "answer": "secret"}],
    )
    queries = []
    monkeypatch.setattr(block_search.OllamaEmbeddingProvider, "embed_many", lambda self, texts: queries.extend(texts) or [[1.0, 0.0]])
    for domain, question in [("alpha", "Explain the subject"), ("alpha", "What about that?"), ("beta", "Other question")]:
        response = views.support_chat_view(request("post", data={"domain": domain, "question": question}, session=session))
        assert response.url == reverse("support-chat") + f"?domain={domain}"
    second = calls[1].messages
    assert [(m.role, m.content) for m in second[1:3]] == [
        (Role.USER, "Explain the subject"), (Role.ASSISTANT, "Grounded answer [1]"),
    ]
    assert "Explain the subject" in queries[1] and "What about that?" in queries[1]
    assert len(calls[2].messages) == 2
    assert "alpha" not in calls[2].messages[-1].content
    assert all("secret" not in m.content for call in calls for m in call.messages)
    beta_html = views.support_chat_view(request(session=session)).content.decode()
    assert "Explain the subject" not in beta_html and "LEGACY secret" not in beta_html
    alpha_html = views.support_chat_view(request(data={"domain": "alpha"}, session=session)).content.decode()
    assert "Explain the subject" in alpha_html and "beta evidence" not in alpha_html
    assert "Source:" in alpha_html and "Block:" in alpha_html and "[1]" in alpha_html
    views.support_chat_view(request("post", data={"domain": "alpha", "action": "clear"}, session=session))
    assert session["domain_chat_history"]["alpha"] == []
    assert len(session["domain_chat_history"]["beta"]) == 1
    assert session["jira_support_chat_history"][0]["question"] == "LEGACY secret"
    assert session["ollama_chat_history"][0]["question"] == "FREE secret"


@pytest.mark.parametrize("failure", ["missing", "embedding", "invalid_vector", "llm", "empty"])
def test_failures_are_visible_and_do_not_add_fabricated_history(corpus, monkeypatch, failure):
    calls = mock_chat(monkeypatch, answer="" if failure == "empty" else "answer", error=RuntimeError("LLM unavailable") if failure == "llm" else None)
    if failure == "missing":
        with connect(settings.KNOWLEDGE_STORE_TARGET) as conn:
            conn.execute("DELETE FROM knowledge_embeddings")
    elif failure == "embedding":
        def fail(self, texts):
            raise requests.ConnectionError("embedding offline")
        monkeypatch.setattr(block_search.OllamaEmbeddingProvider, "embed_many", fail)
    elif failure == "invalid_vector":
        monkeypatch.setattr(block_search.OllamaEmbeddingProvider, "embed_many", lambda self, texts: [[]])
    req = request("post", data={"question": "question"})
    response = views.support_chat_view(req)
    assert response.status_code == 503
    html = response.content.decode()
    assert 'role="alert"' in html and "Chat fehlgeschlagen" in html
    assert "domain_chat_history" not in req.session
    assert len(calls) == (1 if failure in {"llm", "empty"} else 0)


def test_no_relevant_hits_does_not_call_llm(corpus, monkeypatch):
    monkeypatch.setattr(block_search.OllamaEmbeddingProvider, "embed_many", lambda self, texts: [[0.0, 1.0]])
    result = services.support_chat_answer("unrelated", domain="alpha")
    assert result["sources"] == [] and "keine passenden Quellen" in result["answer"]


def test_legacy_jira_post_uses_canonical_domain_chat(corpus, monkeypatch):
    calls = mock_chat(monkeypatch)
    response = views.jira_support_chat_view(request("post", data={"question": "question"}, route="jira-support-chat"))
    assert response.status_code == 302 and "chat/support/" in response.url
    assert len(calls) == 1


@pytest.mark.parametrize("action", ["save_entry", "import_entry", "semantic_entry"])
def test_free_chat_post_save_import_functions_remain_available(corpus, monkeypatch, tmp_path, action):
    monkeypatch.setattr(views, "_active_semantic_domain", lambda req: "alpha")
    monkeypatch.setattr(views, "ollama_runtime_settings", lambda: {"provider": "mock", "model": "mock-1", "base_url": ""})
    saved = tmp_path / "old-chat.md"
    saves, imports = [], []
    monkeypatch.setattr(views, "save_ollama_chat_markdown", lambda **kwargs: saves.append(kwargs) or saved)
    monkeypatch.setattr(views, "import_markdown_file", lambda *args, **kwargs: imports.append(args) or {"imported": 1})
    monkeypatch.setattr(views, "run_dashboard_task", lambda *args, **kwargs: {"enqueued": 1, "done": 1})
    req = request("post", route="ollama-chat", data={"action": action, "entry_index": "0"})
    req.session["ollama_chat_history"] = [{"question": "old", "answer": "retained"}]
    response = views.ollama_chat_view(req)
    assert response.status_code == 302 and len(saves) == 1
    assert len(imports) == (0 if action == "save_entry" else 1)
    assert req.session["ollama_chat_history"][0]["saved_path"] == str(saved)


def test_free_chat_post_continuity_excludes_unknown_and_other_domain_history(corpus, monkeypatch):
    monkeypatch.setattr(views, "_active_semantic_domain", lambda req: "alpha")
    monkeypatch.setattr(views, "ollama_runtime_settings", lambda: {"provider": "mock", "model": "mock-1", "base_url": ""})
    history_sent = []
    monkeypatch.setattr(views, "ollama_chat_answer", lambda question, **kwargs: history_sent.extend(kwargs["history"]) or {
        "question": question, "answer": "new answer", "model": "mock-1", "base_url": "", "messages": [],
    })
    req = request("post", route="ollama-chat", data={"question": "new question"})
    req.session["ollama_chat_history"] = [
        {"question": "unknown", "answer": "unscoped"},
        {"question": "beta", "answer": "beta secret", "domain": "beta"},
        {"question": "alpha", "answer": "alpha answer", "domain": "alpha"},
    ]
    response = views.ollama_chat_view(req)
    assert response.status_code == 302
    assert history_sent == [
        {"role": "user", "content": "alpha"}, {"role": "assistant", "content": "alpha answer"},
    ]
    assert req.session["ollama_chat_history"][0]["domain"] == "alpha"
    assert len(req.session["ollama_chat_history"]) == 4


def test_empty_domain_get_reports_index_gap_without_network(corpus):
    response = views.support_chat_view(request(data={"domain": "empty"}))
    assert response.status_code == 200
    assert "Kein nutzbarer Vektorindex" in response.content.decode()


def test_current_only_search_does_not_change_legacy_store_search(corpus):
    with connect(settings.KNOWLEDGE_STORE_TARGET) as conn:
        conn.execute("UPDATE knowledge_embeddings SET created_at = '2000-01-01' WHERE block_id = ?", ["alpha-markdown"])
    assert corpus.similar_blocks([1.0, 0.0], model="nomic-embed-text", source_ids=["alpha-markdown"])
    assert not corpus.similar_blocks(
        [1.0, 0.0], model="nomic-embed-text", source_ids=["alpha-markdown"], current_only=True,
    )

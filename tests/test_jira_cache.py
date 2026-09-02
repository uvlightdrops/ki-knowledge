"""Tests for Jira structured cache and daily timeline."""

from pathlib import Path

from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue


class DummyEmbeddingBackend:
    def embed(self, text: str) -> list[float]:
        lower = text.lower()
        return [
            1.0 if "login" in lower else 0.0,
            1.0 if "monitoring" in lower else 0.0,
        ]


def test_jira_cache_builds_daily_timeline(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))

    issues = [
        JiraIssue(
            key="AE-1",
            summary="Splunk dashboard aufsetzen",
            description="Monitoring für Login-Flows",
            status="In Progress",
            issue_type="Task",
            assignee="a@example.com",
            labels=["splunk", "monitoring"],
            updated_at="2026-02-16T11:12",
        ),
        JiraIssue(
            key="AE-2",
            summary="Alerting verbessern",
            description="Splunk Alert Regeln erweitern",
            status="To Do",
            issue_type="Story",
            assignee="b@example.com",
            labels=["splunk", "alerting"],
            updated_at="2026-02-16T15:42",
        ),
        JiraIssue(
            key="AE-3",
            summary="Dokumentation ergänzen",
            description="Runbook für Incident Handling",
            status="Done",
            issue_type="Task",
            assignee="c@example.com",
            labels=["runbook"],
            updated_at="2026-02-17T08:10",
        ),
    ]

    imported = cache.ingest_issues(issues)
    assert imported == 3

    timeline = cache.daily_timeline(limit_days=7)
    assert len(timeline) == 2

    first_day = timeline[0]
    assert first_day.day == "2026-02-16"
    assert first_day.issue_count == 2
    assert "AE-1" in first_day.issue_keys
    assert "AE-2" in first_day.issue_keys
    assert "splunk" in first_day.topics


def test_jira_cache_search_issues(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))

    issues = [
        JiraIssue(
            key="AE-10",
            summary="Support Portal Fehlerbild",
            description="Kunde meldet Login-Probleme im Portal",
            status="To Do",
            issue_type="Bug",
            assignee="s@example.com",
            labels=["support", "portal"],
            updated_at="2026-02-18T09:15",
        ),
        JiraIssue(
            key="AE-11",
            summary="Monitoring Dashboard",
            description="Grafana Datenquellen erweitern",
            status="Done",
            issue_type="Task",
            assignee="m@example.com",
            labels=["monitoring"],
            updated_at="2026-02-18T10:15",
        ),
    ]
    cache.ingest_issues(issues)

    results = cache.search_issues("Portal")
    assert len(results) == 1
    assert results[0].key == "AE-10"


def test_jira_cache_hybrid_search(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-20",
                summary="Kunden Login Problem",
                description="Support braucht Login Analyse",
                status="To Do",
                issue_type="Bug",
                assignee="s@example.com",
                labels=["support"],
                updated_at="2026-02-20T08:00",
            ),
            JiraIssue(
                key="AE-21",
                summary="Monitoring Dashboard",
                description="Systemmetriken erweitern",
                status="In Progress",
                issue_type="Task",
                assignee="m@example.com",
                labels=["monitoring"],
                updated_at="2026-02-20T08:30",
            ),
        ]
    )

    backend = DummyEmbeddingBackend()
    embedded = cache.build_embeddings(backend, embedding_model="dummy")
    assert embedded == 2

    hits = cache.hybrid_search(
        "Login Unterstützung",
        backend=backend,
        embedding_model="dummy",
        limit=3,
    )
    assert len(hits) >= 1
    assert hits[0].issue.key == "AE-20"
    assert hits[0].semantic_score >= 0.0


def test_tfidf_embedding_provider_basic():
    from ki_knowledge.integrations.embeddings import TFIDFEmbeddingProvider

    corpus = [
        "login support portal probleme",
        "monitoring grafana alerts",
        "dokumentation runbook splunk",
    ]
    provider = TFIDFEmbeddingProvider()
    provider.fit(corpus)

    vec = provider.embed("login support")
    assert len(vec) > 0
    # login-related vector should have higher cosine to first doc than third
    vec2 = provider.embed("monitoring alerts")
    assert vec != vec2


def test_jira_cache_extract_domain_terms_from_labels_and_comments(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-30",
                summary="OAuth token expires too early",
                description="Auth service refresh-token handling fails for API gateway.",
                status="Open",
                issue_type="Bug",
                assignee="sec@example.com",
                labels=["auth", "oauth", "api-gateway"],
                updated_at="2026-02-21T08:00",
                text_fields={
                    "Kommentar 1": "OAuth flow fails after gateway timeout and token refresh.",
                },
            ),
            JiraIssue(
                key="AE-31",
                summary="Gateway login retries",
                description="Retry strategy for login requests behind API gateway.",
                status="In Progress",
                issue_type="Task",
                assignee="ops@example.com",
                labels=["auth", "gateway"],
                updated_at="2026-02-21T09:00",
                text_fields={
                    "Comment body": "Gateway retries should keep OAuth session stable.",
                },
            ),
        ]
    )

    terms = cache.extract_domain_terms(limit=10, min_count=2)
    term_values = {item.term: item for item in terms}
    assert "auth" in term_values
    assert "gateway" in term_values
    assert "oauth" in term_values
    assert "label" in term_values["oauth"].sources


def test_jira_cache_semantic_field_embeddings_and_search(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-40",
                summary="Login timeout in gateway",
                description="Customers see login timeout errors in the API gateway auth path.",
                status="Open",
                issue_type="Bug",
                assignee="ops@example.com",
                labels=["auth"],
                updated_at="2026-02-22T08:00",
                text_fields={"Kommentar": "Gateway drops session during login handshake."},
            ),
            JiraIssue(
                key="AE-41",
                summary="Monitoring panel updates",
                description="Dashboards for latency and error rates.",
                status="Done",
                issue_type="Task",
                assignee="obs@example.com",
                labels=["monitoring"],
                updated_at="2026-02-22T09:00",
                text_fields={"Comment": "Alert thresholds refined for splunk dashboards."},
            ),
        ]
    )

    backend = DummyEmbeddingBackend()
    created = cache.build_field_embeddings(
        backend=backend,
        embedding_model="dummy-fields",
        min_text_len=10,
    )
    assert created >= 3

    hits = cache.semantic_field_search(
        query="login issue",
        backend=backend,
        embedding_model="dummy-fields",
        limit=5,
        field_kind="comment",
    )
    assert len(hits) >= 1
    assert hits[0].issue_key == "AE-40"
    assert hits[0].field_kind == "comment"


def test_jira_domain_terms_prioritize_labels_over_text_noise(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="AE-50",
                summary="Auth hardening",
                description="Please update system description and ticket details for this issue.",
                status="Open",
                issue_type="Task",
                assignee="a@example.com",
                labels=["oauth", "auth"],
                updated_at="2026-03-01T10:00",
                text_fields={"Kommentar": "Please update system and ticket text quickly."},
            ),
            JiraIssue(
                key="AE-51",
                summary="Gateway auth flow",
                description="Auth and OAuth login flow tuning.",
                status="Open",
                issue_type="Task",
                assignee="b@example.com",
                labels=["auth"],
                updated_at="2026-03-01T11:00",
                text_fields={"Comment": "Ticket text and issue description are now updated."},
            ),
        ]
    )

    terms = cache.extract_domain_terms(limit=10, min_count=1)
    values = [item.term for item in terms]
    assert "auth" in values
    assert "oauth" in values
    assert "ticket" not in values
    assert terms[0].term in {"auth", "oauth"}

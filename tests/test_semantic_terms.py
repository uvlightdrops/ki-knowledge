"""Tests for semantic term persistence and enrichment workflow."""

from pathlib import Path

from ki_knowledge.integrations.jira_cache import DomainTerm, JiraIssueCache
from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.semantic_terms import SemanticEnrichmentService, SemanticTermStore


class DummyBackend:
    def chat(self, messages: list[dict], **options) -> str:
        prompt = str(messages[0].get("content", ""))
        if '"matches"' in prompt:
            return """
            {
              "matches": [
                {"label":"OAuth2","confidence":0.9,"reason":"OAuth flow and token handling is discussed."},
                {"label":"API Gateway","confidence":0.82,"reason":"The text references gateway retries."}
              ]
            }
            """
        return """
        {
          "definition": "OAuth ist ein Autorisierungs-Framework fuer delegierten Zugriff.",
          "short_facts": ["OAuth nutzt Access Tokens.", "OAuth wird oft mit OpenID Connect kombiniert."],
          "related_terms": [{"label":"OpenID Connect","relation":"related_to","weight":0.8}],
          "confidence": 0.86
        }
        """


def test_semantic_store_candidates_and_promotion(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    candidates = [
        DomainTerm(
            term="OAuth2",
            count=10,
            issue_count=4,
            sources=["label"],
            sample_issue_keys=["AE-1", "AE-2"],
        ),
        DomainTerm(
            term="authorization",
            count=3,
            issue_count=2,
            sources=["description"],
            sample_issue_keys=["AE-3"],
        ),
    ]
    created = store.store_domain_candidates(candidates)
    assert created == 2

    promoted = store.promote_candidates(limit=10)
    assert promoted == 2

    terms = store.list_terms(limit=20)
    normalized = {item.normalized_label for item in terms}
    assert "oauth" in normalized
    assert "authorization" in normalized


def test_semantic_enrichment_writes_append_only_facts(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    term_id = store.upsert_term("OAuth2", source="test")
    enqueued = store.enqueue_jobs(limit=10)
    assert enqueued == 1

    service = SemanticEnrichmentService(
        store=store,
        backend=DummyBackend(),
        model_id="dummy-model",
    )
    result = service.run_batch(batch_size=5)
    assert result["done"] == 1

    facts = store.current_facts(term_id)
    fact_types = {item.fact_type for item in facts}
    assert "definition" in fact_types
    assert "short_fact" in fact_types
    relations = store.term_relations(term_id)
    assert len(relations) >= 1


def test_semantic_refinement_gap_detection_and_enqueue(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    term_id = store.upsert_term("API Gateway", source="test")
    # Create only one low-confidence fact -> should be considered a gap.
    store.add_fact(
        term_id=term_id,
        fact_type="short_fact",
        content="API Gateway steht vor Services.",
        confidence=0.35,
        model_id="test-model",
        prompt_version="v1",
        prompt_hash="p1",
        response_hash="r1",
    )

    gaps = store.list_term_gaps(limit=20, min_facts=2, min_relations=1, min_confidence=0.7)
    assert any(item.term_id == term_id for item in gaps)

    enqueued = store.enqueue_refinement_jobs(
        limit=20,
        min_facts=2,
        min_relations=1,
        min_confidence=0.7,
        job_type="refine",
    )
    assert enqueued >= 1


def test_semantic_monitoring_snapshot_shape(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    term_id = store.upsert_term("Service Mesh", source="test")
    store.add_fact(
        term_id=term_id,
        fact_type="short_fact",
        content="Service Mesh verwaltet Service-zu-Service Kommunikation.",
        confidence=0.72,
        model_id="test-model",
        prompt_version="v1",
        prompt_hash="p1",
        response_hash="r1",
    )
    store.enqueue_jobs(limit=5)
    snapshot = store.monitoring_snapshot()
    assert "totals" in snapshot
    assert snapshot["totals"]["terms"] >= 1
    assert "job_status" in snapshot
    assert snapshot["job_status"].get("pending", 0) >= 1
    assert "gaps" in snapshot
    assert "recent_jobs" in snapshot


def test_semantic_store_lists_domain_terms_from_promoted_candidates(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    created = store.store_domain_candidates(
        [
            DomainTerm(
                term="OAuth2",
                count=9,
                issue_count=4,
                sources=["label", "description"],
                sample_issue_keys=["AE-1", "AE-2"],
            ),
            DomainTerm(
                term="API Gateway",
                count=6,
                issue_count=3,
                sources=["description"],
                sample_issue_keys=["AE-3"],
            ),
        ]
    )
    assert created == 2
    promoted = store.promote_candidates(limit=10)
    assert promoted == 2

    terms = store.list_domain_terms(limit=10, min_count=1, sort="relevance", order="desc")
    values = {item.term: item for item in terms}
    assert "OAuth2" in values
    assert values["OAuth2"].count >= 9
    assert values["OAuth2"].issue_count >= 4


def test_jira_cache_excluded_terms_are_filtered(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    cache = JiraIssueCache(str(db_path))
    cache.ingest_issues(
        [
            JiraIssue(
                key="ABC-1",
                summary="Service Mesh rollout",
                description="Wir machen bitte den release plan fuer den Cluster.",
                status="Open",
                issue_type="Task",
                assignee=None,
                labels=["Service Mesh"],
                created_at="2026-08-12T07:00:00",
                updated_at="2026-08-12T07:10:00",
            )
        ]
    )
    cache.add_excluded_term("machen", kind="stop_word")
    cache.add_excluded_term("service mesh", kind="exception")

    terms = cache.extract_domain_terms(limit=20, min_count=1)
    extracted = {item.term for item in terms}
    assert "machen" not in extracted
    assert "service mesh" not in extracted


def test_semantic_term_forget_deprecates_and_removes_candidates(tmp_path: Path):
    db_path = tmp_path / "jira_cache.sqlite"
    store = SemanticTermStore(str(db_path))
    created = store.store_domain_candidates(
        [
            DomainTerm(
                term="OAuth2",
                count=9,
                issue_count=4,
                sources=["label", "description"],
                sample_issue_keys=["AE-1", "AE-2"],
            )
        ]
    )
    assert created == 1
    promoted = store.promote_candidates(limit=10)
    assert promoted == 1

    assert store.forget_term("OAuth2") is True
    deprecated = store.list_terms(status="deprecated", limit=20)
    assert any(item.normalized_label == "oauth" for item in deprecated)

    terms = store.list_domain_terms(limit=10, min_count=1, sort="relevance", order="desc")
    assert all(item.term != "OAuth2" for item in terms)


def test_semantic_record_term_link_jobs(tmp_path: Path):
    semantic_db = tmp_path / "jira_cache.sqlite"
    knowledge_db = tmp_path / "knowledge.sqlite"
    semantic_store = SemanticTermStore(str(semantic_db))
    knowledge_store = KnowledgeStore(str(knowledge_db))
    source_path = str(tmp_path / "ops-guide.md")
    knowledge_store.import_markdown_text(
        text="# Ops\nOAuth retries via API Gateway require stable tokens.",
        source_path=source_path,
        source_name="ops-guide.md",
    )
    records = knowledge_store.list_records(limit=20)
    target_records = [item.block_id for item in records if item.block_type == "paragraph"]
    assert target_records

    semantic_store.upsert_term("OAuth2", source="test")
    semantic_store.upsert_term("API Gateway", source="test")
    enqueued = semantic_store.enqueue_record_link_jobs(target_records, job_type="record_terms")
    assert enqueued >= 1

    service = SemanticEnrichmentService(
        store=semantic_store,
        backend=DummyBackend(),
        model_id="dummy-model",
        knowledge_db_path=str(knowledge_db),
    )
    result = service.run_batch(batch_size=10, job_types=("record_terms",))
    assert result["done"] >= 1

    links = semantic_store.list_record_term_links(record_id=target_records[0], limit=20)
    linked_labels = {item["term_label"] for item in links}
    assert "OAuth2" in linked_labels
    assert "API Gateway" in linked_labels

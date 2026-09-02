from __future__ import annotations

from fastapi import Query

from ki_knowledge.api.knowledge_app import app as app
import ki_knowledge.api.knowledge_app as knowledge_app

_cache = None
_graph = None
_assistant = None


def _sync_legacy_globals() -> None:
    if _cache is not None:
        knowledge_app._cache = _cache
    if _graph is not None:
        knowledge_app._graph_runtime = _graph
    if _assistant is not None:
        knowledge_app._assistant = _assistant


def _get_components():
    _sync_legacy_globals()
    return knowledge_app._get_components()


def _field_embedding_backend(cache, assistant, issue_limit: int = 5000):
    _sync_legacy_globals()
    return knowledge_app._field_embedding_backend(cache=cache, assistant=assistant, issue_limit=issue_limit)


def _semantic_model_id(assistant) -> str:
    return knowledge_app._semantic_model_id(assistant)


def _services():
    from ki_knowledge.django_site import services

    return services


@app.get("/api/health")
def api_health():
    return {"status": "ok"}


@app.get("/api/timeline")
def api_timeline(days: int = Query(default=14, ge=1, le=365)):
    return _services().jira_daily_timeline(days=days)["timeline"]


@app.get("/api/search")
def api_search(q: str = Query(..., min_length=1), limit: int = Query(default=8, ge=1, le=50)):
    return [
        {
            "key": hit.issue.key,
            "id": hit.issue.key,
            "title": hit.issue.summary,
            "status": hit.issue.status,
            "entity_type": hit.issue.issue_type,
            "labels": hit.issue.labels,
            "combined_score": round(hit.combined_score, 4),
        }
        for hit in _services().jira_hybrid_search(query=q, limit=limit)["hits"]
    ]


@app.post("/api/ask")
def api_ask(payload: dict):
    question = str(payload.get("question", "")).strip()
    limit = int(payload.get("limit", 8))
    _sync_legacy_globals()
    _, _, assistant = knowledge_app._get_components()
    result = assistant.ask(question, limit=limit)
    return {
        "answer": result.answer,
        "sources": result.sources,
        "graph_expanded": result.graph_expanded,
    }


@app.get("/api/graph/{entity_id}/neighbors")
def api_graph_neighbors(entity_id: str, limit: int = Query(default=25, ge=1, le=100)):
    _sync_legacy_globals()
    if _graph is not None:
        neighbors = _graph.issue_neighbors(entity_id, limit=limit)
        return {
            "key": entity_id,
            "neighbors": [
                {
                    "node_id": item.neighbor_id,
                    "node_type": item.neighbor_type,
                    "label": item.neighbor_id,
                    "relation": item.relation,
                    "weight": item.weight,
                }
                for item in neighbors
            ],
        }
    result = _services().jira_graph_explorer(issue_key=entity_id, limit=limit)
    return {
        "key": entity_id,
        "neighbors": [
            {
                "node_id": item.neighbor_id,
                "node_type": item.neighbor_type,
                "label": item.neighbor_id,
                "relation": item.relation,
                "weight": item.weight,
            }
            for item in result["neighbors"]
        ],
    }


@app.get("/api/domain/terms")
def api_domain_terms(
    limit: int = Query(default=40, ge=1, le=200),
    min_count: int = Query(default=2, ge=1, le=100),
):
    return [
        {
            "term": item.term,
            "count": item.count,
            "entity_count": item.issue_count,
            "sources": item.sources,
            "sample_entity_ids": item.sample_issue_keys,
        }
        for item in _services().jira_domain_analysis(limit_terms=limit, min_count=min_count)["terms"]
    ]


@app.post("/api/semantic/fields/rebuild")
def api_rebuild_field_semantics(issue_limit: int = Query(default=5000, ge=1, le=10000)):
    del issue_limit
    result = _services().run_dashboard_task("semantic_fields_rebuild")
    return {
        "embedded_fields": result["embedded_fields"],
        "embedding_model": result["embedding_model"],
    }


@app.get("/api/semantic/fields/search")
def api_semantic_field_search(
    q: str = Query(..., min_length=2),
    limit: int = Query(default=10, ge=1, le=50),
    field_kind: str | None = Query(default=None, pattern="^(description|comment)$"),
):
    return [
        {
            "entity_id": item.issue_key,
            "entity_title": item.issue_summary,
            "field_name": item.field_name,
            "field_kind": item.field_kind,
            "score": round(item.score, 4),
            "top_terms": item.top_terms,
            "excerpt": item.excerpt,
        }
        for item in _services().jira_domain_analysis(query=q, limit_hits=limit)["hits"]
        if field_kind is None or item.field_kind == field_kind
    ]


@app.post("/api/semantic/terms/extract")
def api_semantic_extract_terms(
    limit: int = Query(default=300, ge=1, le=2000),
    min_count: int = Query(default=2, ge=1, le=100),
    promote: bool = Query(default=True),
):
    analysis = _services().jira_domain_analysis(limit_terms=limit, min_count=min_count)
    store = _services().semantic_store()
    candidates = store.store_domain_candidates(analysis["terms"])
    promoted = store.promote_candidates(limit=limit) if promote else 0
    return {"candidates": candidates, "promoted": promoted}


@app.post("/api/semantic/terms/promote")
def api_semantic_promote_terms(limit: int = Query(default=500, ge=1, le=5000)):
    del limit
    result = _services().run_dashboard_task("semantic_extract_promote")
    return {"promoted": result["promoted"]}


@app.post("/api/semantic/enrich/enqueue")
def api_semantic_enqueue(
    job_type: str = Query(default="definition"),
    only_status: str = Query(default="new", pattern="^(new|enriched|reviewed|deprecated)$"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    del job_type, only_status, limit
    result = _services().run_dashboard_task("semantic_enqueue")
    return {"enqueued": result["enqueued"]}


@app.post("/api/semantic/enrich/run")
def api_semantic_run(batch_size: int = Query(default=20, ge=1, le=200)):
    del batch_size
    result = _services().run_dashboard_task("semantic_run")
    return result


@app.get("/api/semantic/terms")
def api_semantic_list_terms(
    status: str | None = Query(default=None, pattern="^(new|enriched|reviewed|deprecated)$"),
    limit: int = Query(default=200, ge=1, le=2000),
):
    return [
        {
            "term_id": item.term_id,
            "canonical_label": item.canonical_label,
            "normalized_label": item.normalized_label,
            "language": item.language,
            "status": item.status,
            "created_at": item.created_at,
            "updated_at": item.updated_at,
        }
        for item in _services().semantic_terms(status=status, limit=limit)
    ]


@app.get("/api/semantic/terms/{term_id}")
def api_semantic_term(term_id: str):
    result = _services().semantic_term_detail(term_id)
    if result is None:
        return {"detail": "Term not found"}
    return result


@app.get("/api/semantic/refine/plan")
def api_semantic_refine_plan(
    limit: int = Query(default=100, ge=1, le=1000),
    min_facts: int = Query(default=2, ge=1, le=20),
    min_relations: int = Query(default=1, ge=0, le=20),
    min_confidence: float = Query(default=0.65, ge=0.0, le=1.0),
):
    gaps = _services().semantic_store().list_term_gaps(
        limit=limit,
        min_facts=min_facts,
        min_relations=min_relations,
        min_confidence=min_confidence,
    )
    return {"items": gaps}


@app.post("/api/semantic/refine/run")
def api_semantic_refine_run(
    limit: int = Query(default=100, ge=1, le=1000),
    min_facts: int = Query(default=2, ge=1, le=20),
    min_relations: int = Query(default=1, ge=0, le=20),
    min_confidence: float = Query(default=0.65, ge=0.0, le=1.0),
    batch_size: int = Query(default=20, ge=1, le=200),
):
    store = _services().semantic_store()
    planned = store.list_term_gaps(
        limit=limit,
        min_facts=min_facts,
        min_relations=min_relations,
        min_confidence=min_confidence,
    )
    enqueued = store.enqueue_refinement_jobs(
        limit=limit,
        min_facts=min_facts,
        min_relations=min_relations,
        min_confidence=min_confidence,
        job_type="refine",
    )
    result = _services().run_dashboard_task("semantic_refine_run")
    return {"planned": len(planned), "enqueued": enqueued, **result}

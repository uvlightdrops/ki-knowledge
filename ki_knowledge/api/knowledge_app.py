from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from ki_core.config import Config

from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.embeddings import TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_assistant import JiraSupportAssistant
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator
from ki_knowledge.knowledge.ingest import KnowledgeIngestService
from ki_knowledge.knowledge.ontology_ingest import import_ontology_to_store

_CONFIG = Config.from_env()
_DEFAULT_DATA_ROOT = (
    Path(_CONFIG.knowledge_data_root).expanduser()
    if _CONFIG.knowledge_data_root
    else Path.home() / "dev_data" / "ki-knowledge"
)
_DB_PATH = os.getenv("KNOWLEDGE_DB_PATH", str(_DEFAULT_DATA_ROOT / "knowledge.db"))

app = FastAPI(title="Knowledge API", version="0.1.0")
_cache = None
_graph_runtime = None
_assistant = None


class ImportRequest(BaseModel):
    path: str
    import_format: str = "markdown"
    source_name: str | None = None
    block_types: list[str] | None = None
    build_embeddings: bool = False
    rebuild_graph: bool = False


class GenerateRequest(BaseModel):
    source_id: str
    artifact_type: str
    max_items: int = Field(default=6, ge=1, le=100)


class RelationRequest(BaseModel):
    source_block_id: str
    target_block_id: str
    relation: str = "related_to"
    weight: float = 1.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PDFImportJobResponse(BaseModel):
    job_id: str
    pdf_path: str
    domain: str
    status: str
    pages_total: int
    pages_processed: int
    progress_percent: float
    error_message: str | None
    created_at: str
    started_at: str | None
    completed_at: str | None
    source_id: str | None = None
    artifact_id: str | None = None


class PDFImportListResponse(BaseModel):
    jobs: list[PDFImportJobResponse]
    summary: dict[str, int]


def _store() -> KnowledgeStore:
    return KnowledgeStore(_DB_PATH)


def _graph() -> KnowledgeGraph:
    return KnowledgeGraph(_DB_PATH)


def _get_components():
    global _cache, _graph_runtime, _assistant
    if _cache is None:
        cache_db = os.getenv(
            "KI_CACHE_DB",
            _CONFIG.knowledge_cache_db or str(Path(_DB_PATH).with_name(".ki_cache.sqlite")),
        )
        graph_db = os.getenv(
            "KI_GRAPH_DB",
            _CONFIG.knowledge_graph_db or str(Path(_DB_PATH).with_name(".ki_graph.sqlite")),
        )
        _cache = JiraIssueCache(cache_db)
        _graph_runtime = JiraKnowledgeGraph(graph_db)
        tfidf = TFIDFEmbeddingProvider()
        corpus = [issue.full_text for issue in _cache.list_issues(limit=5000)]
        if corpus:
            tfidf.fit(corpus)
            _assistant = JiraSupportAssistant(
                backend=None,  # pragma: no cover - compatibility only
                cache=_cache,
                embedding_backend=tfidf,
                embedding_model="tfidf",
                graph=_graph_runtime,
            )
        else:
            _assistant = JiraSupportAssistant(backend=None, cache=_cache, graph=_graph_runtime)
    return _cache, _graph_runtime, _assistant


def _field_embedding_backend(cache: JiraIssueCache, assistant: JiraSupportAssistant, issue_limit: int = 5000):
    if assistant.embedding_backend and assistant.embedding_model:
        return assistant.embedding_backend, assistant.embedding_model
    tfidf = TFIDFEmbeddingProvider()
    corpus = cache.semantic_text_corpus(issue_limit=issue_limit)
    if not corpus:
        raise HTTPException(status_code=503, detail="No description/comment texts available")
    tfidf.fit(corpus)
    return tfidf, "tfidf-fields"


def _semantic_model_id(assistant: JiraSupportAssistant) -> str:
    return getattr(assistant, "embedding_model", None) or "ki-model"


def _pdf_batch_processor():
    from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor

    db_path = Path(_DB_PATH).expanduser().with_name(".pdf_import_jobs.sqlite")
    return PDFBatchProcessor(str(db_path))


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": "ki-knowledge-api",
        "status": "ok",
        "health": "/health",
        "docs": "/docs",
    }


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/knowledge/import")
def import_source(req: ImportRequest) -> dict[str, Any]:
    store = _store()
    graph = _graph()
    path = Path(req.path).expanduser()
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {path}")

    if req.import_format == "markdown":
        blocks = store.import_markdown_file(
            path,
            source_name=req.source_name,
            allowed_block_types=req.block_types,
        )
        source_id = f"markdown:{path.resolve()}"
    elif req.import_format == "iasem_quiz":
        result = KnowledgeIngestService(store).import_iasem_quiz_file(path)
        source_id = result["source_id"]
        blocks = store.list_records(source_id=source_id, limit=1000)
    elif req.import_format == "ontology":
        count, source_id = import_ontology_to_store(
            path.read_text(encoding="utf-8"),
            source_url=str(path.resolve()),
            content_type=path.suffix,
            title=req.source_name or path.stem,
            store=store,
        )
        blocks = store.list_records(source_id=source_id, limit=max(count, 1))
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported import_format: {req.import_format}")

    if req.rebuild_graph:
        graph.rebuild_from_store(store)

    return {"source_id": source_id, "imported": len(blocks)}


@app.get("/api/knowledge/sources")
def list_sources(source_type: str | None = None) -> list[dict[str, Any]]:
    return [asdict(item) for item in _store().list_sources(source_type=source_type)]


@app.get("/api/knowledge/sources/{source_id}")
def get_source(source_id: str) -> dict[str, Any]:
    source = _store().get_source(source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    return asdict(source)


@app.get("/api/knowledge/sources/{source_id}/graph")
def get_source_graph(source_id: str, limit: int = Query(default=400, ge=1, le=5000)) -> dict[str, Any]:
    return _graph().source_graph_payload(_store(), source_id, limit=limit)


@app.get("/api/knowledge/search")
def search_blocks(q: str = Query(..., min_length=1), limit: int = Query(default=10, ge=1, le=200)) -> list[dict[str, Any]]:
    return [asdict(item) for item in _store().search_blocks(q, limit=limit)]


@app.get("/api/knowledge/records")
def list_records(
    source_id: str | None = None,
    block_type: str | None = None,
    limit: int = Query(default=200, ge=1, le=5000),
) -> list[dict[str, Any]]:
    return [asdict(item) for item in _store().list_records(source_id=source_id, block_type=block_type, limit=limit)]


@app.get("/api/knowledge/records/{block_id}")
def get_record(block_id: str) -> dict[str, Any]:
    record = _store().get_record(block_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return asdict(record)


@app.get("/api/knowledge/artifacts")
def list_artifacts(source_id: str | None = None, artifact_type: str | None = None) -> list[dict[str, Any]]:
    return [asdict(item) for item in _store().list_artifacts(source_id=source_id, artifact_type=artifact_type)]


@app.post("/api/knowledge/generate")
def generate_artifact(req: GenerateRequest) -> dict[str, Any]:
    generator = KnowledgeArtifactGenerator(_store())
    if req.artifact_type == "generated_quiz_module":
        artifact = generator.generate_quiz_module(req.source_id, max_questions=req.max_items)
    elif req.artifact_type == "flashcard_set":
        artifact = generator.generate_flashcards(req.source_id, max_cards=req.max_items)
    elif req.artifact_type == "summary_note":
        artifact = generator.generate_summary_note(req.source_id, max_sections=req.max_items)
    elif req.artifact_type == "glossary":
        artifact = generator.generate_glossary(req.source_id, max_terms=req.max_items)
    elif req.artifact_type == "study_guide":
        artifact = generator.generate_study_guide(req.source_id, max_items=req.max_items)
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported artifact_type: {req.artifact_type}")
    return asdict(artifact)


@app.get("/api/knowledge/blocks/{block_id}/neighbors")
def neighbors(block_id: str, limit: int = Query(default=20, ge=1, le=500)) -> list[dict[str, Any]]:
    return [asdict(item) for item in _graph().neighbors(block_id, limit=limit)]


@app.post("/api/knowledge/relations")
def add_relation(req: RelationRequest) -> dict[str, str]:
    relation_id = _store().add_relation(
        req.source_block_id,
        req.target_block_id,
        relation=req.relation,
        weight=req.weight,
        metadata=req.metadata,
    )
    return {"id": relation_id}


@app.post("/api/pdf/import/enqueue")
def api_pdf_enqueue(
    pdf_path: str = Query(..., description="Path to PDF file"),
    domain: str = Query(default="default"),
):
    processor = _pdf_batch_processor()
    try:
        job_id = processor.create_job(pdf_path, domain)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"job_id": job_id, "status": "enqueued"}


@app.get("/api/pdf/import/jobs", response_model=PDFImportListResponse)
def api_pdf_list_jobs(domain: str | None = Query(default=None), status: str | None = Query(default=None)):
    processor = _pdf_batch_processor()
    jobs = processor.list_jobs(domain=domain, status=status)
    summary = {
        "total": len(jobs),
        "pending": sum(1 for job in jobs if job.status == "pending"),
        "processing": sum(1 for job in jobs if job.status == "processing"),
        "done": sum(1 for job in jobs if job.status == "done"),
        "failed": sum(1 for job in jobs if job.status == "failed"),
    }
    return PDFImportListResponse(
        jobs=[
            PDFImportJobResponse(
                job_id=job.job_id,
                pdf_path=job.pdf_path,
                domain=job.domain,
                status=job.status,
                pages_total=job.pages_total,
                pages_processed=job.pages_processed,
                progress_percent=round((job.pages_processed / job.pages_total * 100) if job.pages_total > 0 else 0, 1),
                error_message=job.error_message,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                source_id=job.source_id,
                artifact_id=job.artifact_id,
            )
            for job in jobs
        ],
        summary=summary,
    )


@app.get("/api/pdf/import/jobs/{job_id}", response_model=PDFImportJobResponse)
def api_pdf_get_job(job_id: str):
    processor = _pdf_batch_processor()
    job = processor.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return PDFImportJobResponse(
        job_id=job.job_id,
        pdf_path=job.pdf_path,
        domain=job.domain,
        status=job.status,
        pages_total=job.pages_total,
        pages_processed=job.pages_processed,
        progress_percent=round((job.pages_processed / job.pages_total * 100) if job.pages_total > 0 else 0, 1),
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        source_id=job.source_id,
        artifact_id=job.artifact_id,
    )


@app.post("/api/pdf/import/jobs/{job_id}/process")
def api_pdf_process_job(job_id: str):
    processor = _pdf_batch_processor()
    job = processor.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if job.status != "pending":
        raise HTTPException(status_code=400, detail=f"Job not pending (status: {job.status})")
    return processor.process_job(job_id)

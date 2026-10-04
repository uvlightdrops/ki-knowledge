from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from pypdf import PdfWriter

from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor


def _pdf(path):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with path.open("wb") as handle:
        writer.write(handle)
    return path


def test_create_job_is_idempotent_for_active_and_completed_jobs(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")

    first = processor.create_job(pdf, "demo")
    second = processor.create_job(pdf, "demo")
    claimed = processor.claim_job(first)
    assert claimed is not None
    assert processor.complete_job(first, claimed.claim_token)

    third = processor.create_job(pdf, "demo")

    assert first == second == third
    assert processor.get_job(first).status == "done"
    assert processor.list_jobs(domain="demo")[0].attempt_count == 1


def test_failed_job_can_be_retried_without_primary_key_collision(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")
    job_id = processor.create_job(pdf, "demo")
    claimed = processor.claim_job(job_id)
    assert claimed is not None
    assert processor.fail_job(job_id, "temporary failure", claimed.claim_token)

    retried = processor.retry_failed_jobs(domain="demo")
    next_claim = processor.claim_job(job_id)

    assert retried == {"retried": 1}
    assert next_claim is not None
    assert next_claim.job_id == job_id
    assert next_claim.attempt_count == 2
    assert next_claim.status == "processing"


def test_completed_job_is_requeued_only_when_explicitly_forced(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")
    job_id = processor.create_job(pdf, "demo")
    claimed = processor.claim_job(job_id)
    assert claimed is not None
    assert processor.complete_job(job_id, claimed.claim_token)

    assert processor.create_job(pdf, "demo") == job_id
    assert processor.get_job(job_id).status == "done"
    assert processor.create_job(pdf, "demo", force=True) == job_id

    requeued = processor.get_job(job_id)
    assert requeued.status == "pending"
    assert requeued.attempt_count == 1
    assert requeued.source_id is None


def test_two_workers_cannot_claim_the_same_pending_job(tmp_path):
    db_path = tmp_path / "jobs.sqlite"
    pdf = _pdf(tmp_path / "sample.pdf")
    first = PDFBatchProcessor(db_path)
    second = PDFBatchProcessor(db_path)
    job_id = first.create_job(pdf, "demo")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda processor: processor.claim_job(job_id), (first, second)))

    assert sum(result is not None for result in results) == 1
    assert first.get_job(job_id).status == "processing"


def test_stale_cleanup_is_domain_scoped_and_uses_heartbeat(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    demo = processor.create_job(_pdf(tmp_path / "demo.pdf"), "demo")
    other = processor.create_job(_pdf(tmp_path / "other.pdf"), "other")
    assert processor.claim_job(demo) is not None
    assert processor.claim_job(other) is not None
    expired = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    with sqlite3.connect(processor.db_path) as conn:
        conn.execute("UPDATE pdf_import_jobs SET heartbeat_at = ? WHERE job_id IN (?, ?)", (expired, demo, other))

    result = processor.cleanup_stale_jobs(domain="demo", timeout_seconds=3600)

    assert result["timed_out"] == 1
    assert processor.get_job(demo).status == "failed"
    assert processor.get_job(demo).claim_token is None
    assert processor.get_job(other).status == "processing"


def test_cleanup_suppresses_duplicate_pending_without_deleting_job_history(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")
    original = processor.create_job(pdf, "demo")
    with sqlite3.connect(processor.db_path) as conn:
        conn.execute(
            """
            INSERT INTO pdf_import_jobs
            (job_id, pdf_path, domain, status, pages_total, created_at)
            VALUES (?, ?, ?, 'pending', 1, ?)
            """,
            ("legacy-duplicate", str(pdf.resolve()), "demo", "2000-01-01T00:00:00+00:00"),
        )

    result = processor.cleanup_stale_jobs(domain="demo")
    jobs = {job.job_id: job for job in processor.list_jobs(domain="demo")}

    assert result["duplicate_pending_removed"] == 1
    assert jobs[original].status == "pending"
    assert jobs["legacy-duplicate"].status == "failed"
    assert "superseded" in jobs["legacy-duplicate"].error_message


def test_duplicate_cleanup_never_supersedes_a_processing_job(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")
    processing_id = processor.create_job(pdf, "demo")
    claimed = processor.claim_job(processing_id)
    assert claimed is not None
    with sqlite3.connect(processor.db_path) as conn:
        conn.execute(
            """
            INSERT INTO pdf_import_jobs
            (job_id, pdf_path, domain, status, pages_total, created_at)
            VALUES (?, ?, ?, 'pending', 1, ?)
            """,
            ("legacy-duplicate", str(pdf.resolve()), "demo", "2000-01-01T00:00:00+00:00"),
        )

    result = processor.cleanup_stale_jobs(domain="demo")

    assert result["duplicates_suppressed"] == 1
    assert processor.get_job(processing_id).status == "processing"
    assert processor.get_job("legacy-duplicate").status == "failed"


def test_retry_failed_is_scoped_and_only_requeues_failed_jobs(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    demo = processor.create_job(_pdf(tmp_path / "demo.pdf"), "demo")
    other = processor.create_job(_pdf(tmp_path / "other.pdf"), "other")
    for job_id in (demo, other):
        claimed = processor.claim_job(job_id)
        assert claimed is not None
        assert processor.fail_job(job_id, "bad pdf", claimed.claim_token)

    result = processor.retry_failed_jobs(domain="demo")

    assert result["retried"] == 1
    assert processor.get_job(demo).status == "pending"
    assert processor.get_job(other).status == "failed"


def test_job_schema_adds_lease_columns_to_existing_database(tmp_path):
    db_path = tmp_path / "legacy.sqlite"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE pdf_import_jobs (
                job_id TEXT PRIMARY KEY, pdf_path TEXT NOT NULL, domain TEXT NOT NULL,
                status TEXT NOT NULL, pages_total INTEGER DEFAULT 0, pages_processed INTEGER DEFAULT 0,
                error_message TEXT, created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT
            )
            """
        )

    processor = PDFBatchProcessor(db_path)
    with sqlite3.connect(db_path) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(pdf_import_jobs)")}

    assert {"attempt_count", "claim_token", "heartbeat_at"} <= columns
    assert processor.list_jobs() == []


def test_worker_claims_and_finishes_only_its_pending_jobs(tmp_path, monkeypatch):
    import ki_knowledge.integrations.pdf_batch as pdf_batch

    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    pdf = _pdf(tmp_path / "sample.pdf")
    job_id = processor.create_job(pdf, "demo")
    monkeypatch.setattr(pdf_batch, "extract_text_from_pdf", lambda _path: "# Title\n\nA paragraph of text.")

    class FakeStore:
        def import_markdown_text(self, *_args, **_kwargs):
            return [object()]

    class FakeArtifactGenerator:
        def __init__(self, _store):
            pass

        def generate_summary_note(self, _source_id):
            return None

    monkeypatch.setattr(processor, "_knowledge_store", lambda: FakeStore())
    monkeypatch.setattr(pdf_batch, "KnowledgeArtifactGenerator", FakeArtifactGenerator)

    result = processor.process_pending_jobs(domain="demo", max_jobs=1)

    assert result == {"claimed": 1, "done": 1, "failed": 0, "timed_out": 0, "total_pending": 1}
    job = processor.get_job(job_id)
    assert job.status == "done"
    assert job.claim_token is None and job.heartbeat_at is None
    assert job.attempt_count == 1


def test_gui_worker_reservation_is_atomic_and_tracks_lifecycle(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")

    first = processor.reserve_worker("demo", "/tmp/worker.log")
    second = processor.reserve_worker("other", "/tmp/worker-2.log")

    assert first["started"] is True
    assert second["started"] is False
    assert second["token"] == first["token"]
    assert processor.worker_started(first["token"], 1234)
    assert processor.worker_started(first["token"], 1234)
    assert not processor.worker_started(first["token"], 5678)
    assert processor.worker_heartbeat(first["token"])
    assert processor.get_worker_run()["status"] == "running"
    assert processor.finish_worker(first["token"])
    assert processor.get_worker_run()["status"] == "done"


def test_expired_gui_worker_reservation_can_be_replaced(tmp_path):
    processor = PDFBatchProcessor(tmp_path / "jobs.sqlite")
    first = processor.reserve_worker("demo", "/tmp/worker.log")
    expired = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
    with sqlite3.connect(processor.db_path) as conn:
        conn.execute("UPDATE pdf_worker_runs SET heartbeat_at = ? WHERE token = ?", (expired, first["token"]))

    second = processor.reserve_worker("demo", "/tmp/worker-2.log")

    assert second["started"] is True
    assert second["token"] != first["token"]
    assert processor.get_worker_run()["token"] == second["token"]


def test_gui_start_launches_worker_without_shell_or_request_blocking(tmp_path, monkeypatch):
    import ki_knowledge.django_site.services as services

    processor = PDFBatchProcessor(tmp_path / "pdf-jobs.sqlite")
    pdf = _pdf(tmp_path / "queued.pdf")
    processor.create_job(pdf, "demo")
    monkeypatch.setattr(services, "get_pdf_batch_processor", lambda: processor)
    monkeypatch.setattr(services, "pdf_batch_db_path", lambda: str(processor.db_path))
    calls = []

    class Child:
        pid = 9876

    monkeypatch.setattr(services.subprocess, "Popen", lambda *args, **kwargs: calls.append((args, kwargs)) or Child())

    result = services.start_pdf_worker("demo")

    assert result["started"] is True
    assert result["pending_at_start"] == 1
    args, kwargs = calls[0]
    command = args[0]
    assert command[0] == services.sys.executable
    assert command[2:5] == ["process_pdf_jobs", "--domain", "demo"]
    assert command[-2:] == ["--worker-token", result["worker"]["token"]]
    assert kwargs["start_new_session"] is True
    assert "shell" not in kwargs
    assert processor.get_worker_run()["pid"] == 9876
    assert services.start_pdf_worker("demo")["reason"] == "active"

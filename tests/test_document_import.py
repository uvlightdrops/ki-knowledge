"""Import orchestration with a real temporary job store and explicit repository."""

import subprocess
import sys
from unittest.mock import Mock

import pytest

from ki_knowledge.integrations.document_import_jobs import DocumentImportJobStore
from ki_knowledge.services.document_import import DocumentImportService


@pytest.fixture
def service(tmp_path):
    return DocumentImportService(
        DocumentImportJobStore(tmp_path / "jobs.sqlite"), Mock(),
    )


def test_enqueue_does_not_execute_documents(service):
    job_id = service.enqueue(7, [1, 2, 1])
    job = service.jobs.get_job(job_id)
    assert job.project_id == 7
    assert job.document_ids == [1, 2, 1]
    assert job.documents_requested == 3
    assert job.status == "pending"
    service.documents.mark_imported.assert_not_called()
    assert service.enqueue(7, [1, 2, 1]) != job_id


def test_run_records_processing_and_done(service):
    job_id = service.enqueue(7, [1, 2])

    def update(project_id, document_ids):
        assert service.jobs.get_job(job_id).status == "processing"
        assert project_id == 7 and document_ids == [1, 2]
        return 1

    service.documents.mark_imported.side_effect = update
    result = service.run(job_id)
    assert result == {"job_id": job_id, "documents_requested": 2, "documents_imported": 1}
    job = service.jobs.get_job(job_id)
    assert job.status == "done" and job.documents_imported == 1
    assert job.started_at and job.completed_at and job.error_message is None


def test_synchronous_helper_finishes_before_return(service):
    service.documents.mark_imported.return_value = 2
    result = service.enqueue_and_run(7, [1, 2])
    assert service.jobs.get_job(result["job_id"]).status == "done"
    service.documents.mark_imported.assert_called_once_with(7, [1, 2])


def test_unknown_job_does_not_execute_documents(service):
    with pytest.raises(ValueError, match="Unknown job_id"):
        service.run("missing")
    service.documents.mark_imported.assert_not_called()


def test_failure_persists_error_and_retry_clears_stale_state(service):
    job_id = service.enqueue(7, [1])
    service.documents.mark_imported.side_effect = RuntimeError("write failed")
    with pytest.raises(RuntimeError, match="write failed"):
        service.run(job_id)
    failed = service.jobs.get_job(job_id)
    assert failed.status == "failed" and failed.error_message == "write failed"
    assert failed.documents_imported == 0 and failed.completed_at

    def retry(*args):
        job = service.jobs.get_job(job_id)
        assert job.status == "processing"
        assert job.completed_at is None and job.error_message is None
        return 1

    service.documents.mark_imported.side_effect = retry
    assert service.run(job_id)["documents_imported"] == 1
    assert service.jobs.get_job(job_id).error_message is None


def test_completion_store_failure_is_not_reported_as_success(service, monkeypatch):
    job_id = service.enqueue(7, [1])
    service.documents.mark_imported.return_value = 1

    def fail(*args, **kwargs):
        raise RuntimeError("job completion failed")

    monkeypatch.setattr(service.jobs, "mark_done", fail)
    with pytest.raises(RuntimeError, match="job completion failed"):
        service.run(job_id)
    job = service.jobs.get_job(job_id)
    assert job.status == "failed" and job.error_message == "job completion failed"


def test_core_and_runner_import_without_django():
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from ki_knowledge.services.document_import import DocumentImportService
from ki_knowledge.services import import_runner
assert not any(name.startswith(("django", "ki_knowledge.django_site")) for name in sys.modules)
"""],
        text=True, capture_output=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr

"""Exercise the real ORM adapter only in a child process with an in-memory DB."""

import subprocess
import sys


def test_real_orm_import_status_and_rollback(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", """
import os
from pathlib import Path
import sys
from unittest.mock import patch

os.environ["DJANGO_SETTINGS_MODULE"] = "ki_knowledge.django_site.settings"
from django.conf import settings
settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
settings.WAGTAILSEARCH_BACKENDS = {"default": {"BACKEND": "wagtail.search.backends.dummy"}}
import django
django.setup()
from django.core.management import call_command
call_command("migrate", verbosity=0, interactive=False, run_syncdb=True)

from ki_knowledge.django_site.document_import import DjangoImportDocuments
from ki_knowledge.django_site.infosite_models import InfoSiteProject, SourceDocument
from ki_knowledge.integrations.document_import_jobs import DocumentImportJobStore
from ki_knowledge.services.document_import import DocumentImportService
from ki_knowledge.services import import_runner

project = InfoSiteProject.objects.create(title="Test")
foreign = InfoSiteProject.objects.create(title="Other")
first = SourceDocument.objects.create(project=project, file_path="first.md")
second = SourceDocument.objects.create(project=project, file_path="second.md", import_status="failed")
other = SourceDocument.objects.create(project=foreign, file_path="other.md")
jobs = DocumentImportJobStore(Path(sys.argv[1]) / "jobs.sqlite")
service = DocumentImportService(jobs, DjangoImportDocuments())
job_id = service.enqueue(project.id, [first.id, second.id])
save = SourceDocument.save

def fail_second(self, *args, **kwargs):
    if self.pk == second.pk:
        raise RuntimeError("second save failed")
    return save(self, *args, **kwargs)

with patch.object(SourceDocument, "save", fail_second):
    try:
        service.run(job_id)
    except RuntimeError as error:
        assert str(error) == "second save failed"
    else:
        raise AssertionError("Expected persisted failure")
first.refresh_from_db()
second.refresh_from_db()
assert first.import_status == "discovered" and not first.imported and first.imported_at is None
assert second.import_status == "failed" and not second.imported
assert jobs.get_job(job_id).status == "failed"
assert service.run(job_id)["documents_imported"] == 2
first.refresh_from_db()
second.refresh_from_db()
assert first.import_status == second.import_status == "imported"
assert first.imported and second.imported and first.imported_at and second.imported_at
stamp = first.imported_at
result = service.enqueue_and_run(project.id, [first.id, first.id, other.id, 999999])
assert result["documents_requested"] == 4 and result["documents_imported"] == 0
first.refresh_from_db()
other.refresh_from_db()
assert first.imported_at == stamp
assert other.import_status == "discovered" and not other.imported
assert jobs.get_job(result["job_id"]).status == "done"
with patch.object(import_runner, "get_job_store", return_value=jobs):
    result = import_runner.enqueue_and_run_import(project.id, [first.id])
    assert result["documents_imported"] == 0
    assert jobs.get_job(result["job_id"]).status == "done"
""", str(tmp_path)],
        capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr

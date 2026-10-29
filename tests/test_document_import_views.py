"""HTTP import controls keep synchronous success/failure notifications."""

import os
from types import SimpleNamespace
from unittest.mock import Mock

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.db.backends.utils import CursorWrapper
from django.test import RequestFactory
from django.urls import reverse

from ki_knowledge.django_site import infosite_views
from ki_knowledge.services import import_runner


@pytest.fixture
def controls(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("This HTTP test must not query a database")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)
    monkeypatch.setattr(
        infosite_views, "get_object_or_404", lambda *args, **kwargs: SimpleNamespace(id=7),
    )
    notices = Mock()
    monkeypatch.setattr(infosite_views, "messages", notices)
    execute = Mock(return_value={
        "job_id": "dimp_test", "documents_requested": 2, "documents_imported": 2,
    })
    monkeypatch.setattr(import_runner, "enqueue_and_run_import", execute)
    return notices, execute


@pytest.mark.parametrize("count,level", [(2, "success"), (0, "info")])
def test_selected_documents_run_inline_before_redirect(controls, count, level):
    notices, execute = controls
    execute.return_value["documents_imported"] = count
    request = RequestFactory().post("/", {"selected_files[]": ["1", "2"]})
    response = infosite_views.infosite_import_selected(request, 7)
    execute.assert_called_once_with(7, [1, 2])
    assert response.status_code == 302
    assert response.url == reverse("infosite:import_control", kwargs={"project_id": 7})
    getattr(notices, level).assert_called_once()
    assert "dimp_test" in getattr(notices, level).call_args.args[1]


@pytest.mark.parametrize("selection,level", [([], "warning"), (["1", "bad"], "error")])
def test_invalid_or_empty_selection_does_not_create_job(controls, selection, level):
    notices, execute = controls
    request = RequestFactory().post("/", {"selected_files[]": selection})
    response = infosite_views.infosite_import_selected(request, 7)
    assert response.status_code == 302
    execute.assert_not_called()
    getattr(notices, level).assert_called_once()


def test_failure_notifies_user_without_success(controls):
    notices, execute = controls
    execute.side_effect = RuntimeError("write failed")
    response = infosite_views.infosite_import_selected(
        RequestFactory().post("/", {"selected_files[]": ["1"]}), 7,
    )
    assert response.status_code == 302
    assert "write failed" in notices.error.call_args.args[1]
    notices.success.assert_not_called()
    notices.info.assert_not_called()


def test_get_cannot_start_import(controls):
    _, execute = controls
    response = infosite_views.infosite_import_selected(RequestFactory().get("/"), 7)
    assert response.status_code == 405
    execute.assert_not_called()

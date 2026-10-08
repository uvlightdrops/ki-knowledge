from __future__ import annotations

import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.db.backends.utils import CursorWrapper  # noqa: E402
from django.http import HttpResponse  # noqa: E402
from django.test import RequestFactory  # noqa: E402
from django.urls import reverse  # noqa: E402

from ki_knowledge.django_site import views_data_sources  # noqa: E402
from ki_knowledge.django_site.layout_targets import layout_targets_for_area  # noqa: E402
from ki_knowledge.integrations.pdf_inventory import PdfInventory, PdfInventoryEntry  # noqa: E402


@pytest.fixture(autouse=True)
def _no_database(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("database access is not allowed in this test")

    monkeypatch.setattr(CursorWrapper, "execute", forbidden)
    monkeypatch.setattr(CursorWrapper, "executemany", forbidden)


@pytest.fixture
def captured(monkeypatch):
    monkeypatch.setattr("ki_knowledge.django_site.widget_catalog_preview.catalog_active_domain", lambda request: "anthro")
    calls = []

    def fake_render(request, template, context):
        calls.append((template, context))
        return HttpResponse("ok")

    monkeypatch.setattr(views_data_sources, "render", fake_render)
    return calls


def _inventory():
    inventory = PdfInventory(roots=[{"label": "data root", "path": "/data", "status": "ok"}])
    inventory.entries = [
        PdfInventoryEntry(path="/data/b.pdf", relative_path="b.pdf", root_label="data root", title="Alpha", title_source="filename"),
        PdfInventoryEntry(path="/data/a.pdf", relative_path="a.pdf", root_label="data root", title="Beta", title_source="metadata"),
    ]
    return inventory


def test_inventory_route_is_discoverable():
    assert reverse("pdf-inventory") == "/data-sources/pdf/inventory/"
    assert any(target.path == "/data-sources/pdf/inventory/" for target in layout_targets_for_area("datasources"))


def test_inventory_view_does_not_scan_without_explicit_request(monkeypatch, captured):
    monkeypatch.setattr(views_data_sources, "scan_configured_pdf_inventory", lambda **kw: pytest.fail("scanned"))

    response = views_data_sources.pdf_inventory_view(RequestFactory().get("/data-sources/pdf/inventory/?root=/etc"))

    assert response.status_code == 200
    template, context = captured[0]
    assert template == "kicli_django/pdf_inventory.html"
    assert context["inventory"] is None and context["scan_requested"] is False


def test_inventory_view_scans_on_request_and_sorts_by_path(monkeypatch, captured):
    calls = []

    def fake_scan(**kwargs):
        calls.append(kwargs)
        return _inventory()

    monkeypatch.setattr(views_data_sources, "scan_configured_pdf_inventory", fake_scan)

    views_data_sources.pdf_inventory_view(RequestFactory().get("/x/?scan=1&text=1&sort=path"))

    _, context = captured[0]
    assert calls == [{"domain": "anthro", "include_first_page_text": True}]
    assert [entry.relative_path for entry in context["inventory"].entries] == ["a.pdf", "b.pdf"]
    assert context["summary"]["metadata_titles"] == 1


def test_inventory_template_renders_provenance_and_errors():
    from django.template import engines

    inventory = _inventory()
    inventory.entries[0].error = "encrypted: password required"
    template = engines["django"].from_string(
        open(os.path.join(os.path.dirname(views_data_sources.__file__), "templates", "kicli_django", "pdf_inventory.html"))
        .read()
        .replace('{% extends "base.html" %}', "")
    )
    html = template.render({"inventory": inventory, "summary": inventory.summary, "scan_requested": True, "include_text": False, "sort": "title"})

    assert "Alpha" in html and "Beta" in html
    assert "encrypted: password required" in html
    assert "badge-warning\">filename" in html

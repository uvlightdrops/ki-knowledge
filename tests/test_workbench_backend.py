"""Migrate and exercise real ORM/API behavior without touching a configured DB."""

from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def run_scenario(scenario):
    workspace = Path.cwd() / f".workbench-test-{uuid.uuid4().hex}"
    workspace.mkdir()
    try:
        result = subprocess.run(
            [sys.executable, "-c", scenario, str(workspace)],
            capture_output=True, text=True, timeout=180,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    finally:
        shutil.rmtree(workspace)


def test_workbench_migrated_backend():
    run_scenario(BACKEND_SCENARIO)


def test_workbench_archive_preserves_history_and_links():
    run_scenario(BACKEND_SCENARIO + ARCHIVE_SCENARIO)


def test_workbench_drafts_and_explicit_chat():
    run_scenario(DRAFT_CHAT_SCENARIO)


def test_workbench_existing_snapshot_migration():
    run_scenario(MIGRATION_SCENARIO)


def test_workbench_general_inventory_without_infosite():
    run_scenario(INVENTORY_SCENARIO)


ARCHIVE_SCENARIO = r'''
client.force_login(owner)
document_endpoint = f'documents/{doc["id"]}'
annotation_endpoint = f'annotations/{annotation["id"]}'
live_doc = request("get", document_endpoint)
live_annotation = next(item for item in request("get", "annotations")["annotations"] if item["id"] == annotation["id"])
counts = [model.objects.count() for model in (WorkbenchRevision, WorkbenchAnchor, WorkbenchRelation)]
original_file = file.read_bytes()
for endpoint, item in ((document_endpoint, live_doc), (annotation_endpoint, live_annotation)):
    request("post", endpoint + "/archive", {"archived": True}, status=428)
    request("post", endpoint + "/archive", {"archived": True}, status=412, HTTP_IF_MATCH='"0"')
    request("post", endpoint + "/archive", {"archived": "yes"}, status=422, HTTP_IF_MATCH=item["etag"])
    client.force_login(other)
    request("post", endpoint + "/archive", {"archived": True}, status=404, HTTP_IF_MATCH=item["etag"])
    client.force_login(owner)
    assert client.post(base + endpoint + "/archive?domain=beta", data=json.dumps({"archived": True}),
        content_type="application/json", HTTP_IF_MATCH=item["etag"]).status_code == 404
    guarded = Client(enforce_csrf_checks=True)
    guarded.force_login(owner)
    assert guarded.post(base + endpoint + "/archive?domain=alpha", data=json.dumps({"archived": True}),
        content_type="application/json", HTTP_IF_MATCH=item["etag"]).status_code == 403

hidden_mark = request("post", annotation_endpoint + "/archive", {"archived": True}, HTTP_IF_MATCH=live_annotation["etag"])
assert hidden_mark["archived"] and hidden_mark["version"] == live_annotation["version"] + 1
assert not request("get", document_endpoint)["annotations"]
assert not request("get", "relations")["relations"]
assert client.get(base + "annotations?domain=alpha&archived=1").json()["annotations"][0]["id"] == annotation["id"]
request("patch", annotation_endpoint, {"note": "cannot edit archived"}, status=404, HTTP_IF_MATCH=hidden_mark["etag"])
request("post", annotation_endpoint + "/archive", {"archived": False}, status=412, HTTP_IF_MATCH=live_annotation["etag"])
restored_mark = request("post", annotation_endpoint + "/archive", {"archived": False}, HTTP_IF_MATCH=hidden_mark["etag"])
assert not restored_mark["archived"]
assert request("get", "relations")["relations"] == [relation]

hidden_doc = request("post", document_endpoint + "/archive", {"archived": True}, HTTP_IF_MATCH=live_doc["etag"])
request("get", document_endpoint, status=404)
request("get", document_endpoint + "/revisions", status=404)
assert all(item["id"] != doc["id"] for item in request("get", "documents")["documents"])
assert all(item["id"] != annotation["id"] for item in request("get", "annotations")["annotations"])
assert not request("get", "relations")["relations"]
assert client.get(base + "documents?domain=alpha&archived=1").json()["documents"][0]["id"] == doc["id"]
try:
    service.persist_capture(owner, domain, canonical, "same source", file, {}, source=source)
except service.WorkbenchError as error:
    assert error.code == "archived"
else:
    raise AssertionError("Archived capture silently reused or duplicated")
restored_doc = request("post", document_endpoint + "/archive", {"archived": False}, HTTP_IF_MATCH=hidden_doc["etag"])
assert not restored_doc["archived"]
assert request("get", document_endpoint)["revision"]["text"] == canonical
assert request("get", document_endpoint)["annotations"][0]["id"] == annotation["id"]
assert request("get", "relations")["relations"] == [relation]
assert counts == [model.objects.count() for model in (WorkbenchRevision, WorkbenchAnchor, WorkbenchRelation)]
assert file.read_bytes() == original_file
'''


BACKEND_SCENARIO = r'''
import hashlib
import json
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import patch
import uuid

os.environ["DJANGO_SETTINGS_MODULE"] = "ki_knowledge.django_site.settings"
from django.conf import settings
settings.DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
settings.WAGTAILSEARCH_BACKENDS = {
    "default": {"BACKEND": "modelsearch.backends.database", "AUTO_UPDATE": False},
}
settings.ROOT_URLCONF = "workbench_test_urls"
settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
settings.SECURE_SSL_REDIRECT = False
settings.SESSION_COOKIE_SECURE = False
settings.CSRF_COOKIE_SECURE = False
settings.KNOWLEDGE_STORE_TARGET = str(Path(sys.argv[1]) / "knowledge.sqlite3")
import django
django.setup()
from django.apps import apps
assert apps.get_model("django_site", "WorkbenchDocument").__module__.endswith("workbench_models")
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.http import HttpResponse
from django.test import Client
from django.test import override_settings
from django.urls import include, path, reverse
from ki_knowledge.django_site import widget_shell_models
from ki_knowledge.django_site import views_workbench as views
from ki_knowledge.django_site import workbench_service as service
from ki_knowledge.django_site.infosite_models import Domain, InfoSiteProject, SourceDocument
from ki_knowledge.django_site.workbench_models import (
    WorkbenchDocument, WorkbenchRevision, WorkbenchAnnotation,
    WorkbenchAnchor, WorkbenchRelation,
)

urls = ModuleType("workbench_test_urls")
urls.urlpatterns = [path("knowledge/workbench/", include("ki_knowledge.django_site.workbench_urls"))]
sys.modules[urls.__name__] = urls
assert apps.get_model("django_site", "WorkbenchDocument") is WorkbenchDocument
call_command("migrate", verbosity=0, interactive=False)
call_command("makemigrations", "django_site", check=True, dry_run=True, verbosity=0)

root = Path(sys.argv[1]) / "markdown"
root.mkdir()
outside = Path(sys.argv[1]) / "outside.md"
outside.write_text("outside secret", encoding="utf-8")
file = root / "source.md"
raw = "# Héllo\r\n😀e\u0301 selected\rnext\n"
file.write_bytes(raw.encode("utf-8"))
canonical = raw.replace("\r\n", "\n").replace("\r", "\n")
owner = get_user_model().objects.create_user(username="owner", is_staff=True)
other = get_user_model().objects.create_user(username="other", is_staff=True)
ordinary = get_user_model().objects.create_user(username="ordinary")
project = InfoSiteProject.objects.create(title="Project", domain="alpha")
foreign_project = InfoSiteProject.objects.create(title="Foreign", domain="beta")
domain = Domain.objects.get(slug="alpha")
source = SourceDocument.objects.create(project=project, file_path=str(file), title="A source", file_type="markdown")
foreign_source = SourceDocument.objects.create(project=foreign_project, file_path=str(file))
bad_source = SourceDocument.objects.create(project=project, file_path=str(outside))
link = root / "escape.md"
link.symlink_to(outside)
linked_source = SourceDocument.objects.create(project=project, file_path=str(link))
traversal = SourceDocument.objects.create(project=project, file_path=str(root / ".." / "outside.md"))
base = "/knowledge/workbench/api/"
client = Client()

def request(method, endpoint, data=None, status=200, **headers):
    kwargs = {"content_type": "application/json", **headers}
    if data is not None:
        kwargs["data"] = json.dumps(data)
    response = getattr(client, method)(base + endpoint + "?domain=alpha", **kwargs)
    assert response.status_code == status, (method, endpoint, response.status_code, response.content)
    return response.json() if response.content and response.get("Content-Type", "").startswith("application/json") else response

with patch("ki_knowledge.django_site.sources_browser.domain_source_dir", side_effect=lambda kind, domain: root if kind == "markdown" else root / kind), \
     patch("ki_knowledge.django_site.sources_browser._pdf_job_states", return_value={}), \
     patch("ki_knowledge.django_site.knowledge_summary.domain_source_roots", return_value=[root]), \
     patch("ki_knowledge.django_site.views_common.maybe_send_automatic_heartbeat") as heartbeat:
    request("get", "documents", status=401)
    client.force_login(ordinary)
    request("get", "sources", status=403)
    request("post", "documents", {"source_id": source.pk}, status=403)
    client.force_login(owner)
    assert request("get", "documents") == {"documents": []}
    assert request("get", "annotations") == {"annotations": []}
    assert request("get", "relations") == {"relations": []}
    available = request("get", "sources")
    assert [item["title"] for item in available["sources"]] == ["source.md"]
    assert available["sources"][0]["id"].startswith("src_")
    assert available["excluded"][0]["title"] == "escape.md"
    assert WorkbenchDocument.objects.count() == 0
    for rejected in (foreign_source.pk, bad_source.pk, linked_source.pk, traversal.pk):
        request("post", "documents", {"source_id": rejected}, status=404 if rejected == foreign_source.pk else 422)
    for data in ({}, {"path": str(file)}, {"source_id": True}, {"source_id": 2**100}, {"source_id": source.pk, "domain": "beta"}):
        assert request("post", "documents", data, status=422)["error"]["fields"]
    response = client.post(base + "documents?domain=alpha", data="{", content_type="application/json")
    assert response.status_code == 422
    with override_settings(DATA_UPLOAD_MAX_MEMORY_SIZE=10):
        response = client.post(base + "documents?domain=alpha",
            data=json.dumps({"source_id": source.pk}), content_type="application/json")
        assert response.status_code == 413 and response.json()["error"]["code"] == "request_too_large"
    doc = request("post", "documents", {"source_id": source.pk}, status=201)
    assert doc["revision"]["text"] == canonical
    assert doc["revision"]["content_sha256"] == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert len(doc["revision"]["content_sha256"]) == 64
    assert request("post", "documents", {"source_id": source.pk})["id"] == doc["id"]
    assert request("post", "documents", {"source_id": available["sources"][0]["id"]})["id"] == doc["id"]
    assert WorkbenchDocument.objects.count() == WorkbenchRevision.objects.count() == 1
    revision_count = WorkbenchRevision.objects.count()
    file.write_bytes(b"will roll back")
    with patch.object(WorkbenchRevision.objects, "create", side_effect=RuntimeError("persist failed")):
        try:
            service.capture(owner, domain, {"source_id": source.pk})
        except RuntimeError as error:
            assert str(error) == "persist failed"
        else:
            raise AssertionError("Expected failed revision persistence")
    assert WorkbenchDocument.objects.count() == WorkbenchRevision.objects.count() == revision_count
    file.write_bytes(raw.encode("utf-8"))
    assert request("get", "documents")["documents"][0]["id"] == doc["id"]
    start = canonical.index("😀")
    end = canonical.index("\nnext")
    anchor = {
        "revision_id": doc["revision"]["id"], "start": start, "end": end,
        "exact": canonical[start:end], "prefix": canonical[:start], "suffix": canonical[end:],
        "title": "Passage", "category": "claim", "tags": ["tag"], "note": "Note",
    }
    annotation = request("post", f'documents/{doc["id"]}/annotations', anchor, status=201)
    assert annotation["version"] == 1 and annotation["etag"] == '"1"'
    assert annotation["exact"] == "😀e\u0301 selected"
    assert annotation["document_id"] == doc["id"] and annotation["document_title"] == "A source"
    # UTF-16 end offsets count the astral emoji twice; codepoint offsets must not.
    utf16_end = len(canonical[:end].encode("utf-16-le")) // 2
    assert utf16_end == end + 1
    rejected_utf16 = request(
        "post", f'documents/{doc["id"]}/annotations',
        {**anchor, "end": utf16_end}, status=422,
    )
    assert "exact" in rejected_utf16["error"]["fields"]
    for replacement in (
        {"revision_id": str(uuid.uuid4())}, {"start": -1}, {"end": start},
        {"start": True}, {"end": len(canonical) + 1}, {"exact": "wrong"},
        {"prefix": "wrong"}, {"suffix": "wrong"}, {"representation": "html"},
        {"offset_unit": "utf16"}, {"tags": [""]}, {"title": "x"*256},
        {"note": "\ud800"}, {"owner": other.pk},
    ):
        request("post", f'documents/{doc["id"]}/annotations', {**anchor, **replacement}, status=422)
    assert WorkbenchAnnotation.objects.count() == WorkbenchAnchor.objects.count() == 1
    with patch.object(WorkbenchAnchor.objects, "create", side_effect=RuntimeError("anchor failed")):
        try:
            service.create_annotation(WorkbenchDocument.objects.get(pk=doc["id"]), anchor)
        except RuntimeError as error:
            assert str(error) == "anchor failed"
        else:
            raise AssertionError("Expected failed anchor persistence")
    assert WorkbenchAnnotation.objects.count() == WorkbenchAnchor.objects.count() == 1
    endpoint = f'annotations/{annotation["id"]}'
    request("patch", endpoint, {"note": "Changed"}, status=428)
    request("patch", endpoint, {"note": "Changed"}, status=412, HTTP_IF_MATCH='"0"')
    updated = request("patch", endpoint, {"title": "Updated", "note": "Changed"}, HTTP_IF_MATCH=annotation["etag"])
    assert updated["version"] == 2 and updated["etag"] == '"2"'
    request("patch", endpoint, {"note": "lost update"}, status=412, HTTP_IF_MATCH='"1"')
    request("patch", endpoint, {"start": 2}, status=422, HTTP_IF_MATCH='"2"')
    # Force an intervening database change after the initial read: conditional UPDATE must fail.
    original_metadata = service.metadata
    def competing_update(data, partial=False):
        WorkbenchAnnotation.objects.filter(pk=annotation["id"]).update(version=3, note="competing")
        return original_metadata(data, partial)
    with patch.object(service, "metadata", side_effect=competing_update):
        request("patch", endpoint, {"note": "lost"}, status=412, HTTP_IF_MATCH='"2"')
    assert WorkbenchAnnotation.objects.get(pk=annotation["id"]).note == "competing"
    # Capturing a changed file produces a distinct historical snapshot without moving anchors.
    file.write_text("A second snapshot", encoding="utf-8")
    second = request("post", "documents", {"source_id": source.pk}, status=201)
    assert second["id"] != doc["id"]
    assert request("get", f'documents/{doc["id"]}')["revision"]["text"] == canonical
    second_anchor = {
        "revision_id": second["revision"]["id"], "start": 0, "end": 1,
        "exact": "A", "prefix": "", "suffix": " second",
    }
    target = request("post", f'documents/{second["id"]}/annotations', second_anchor, status=201)
    assert len(request("get", "annotations")["annotations"]) == 2
    relation_data = {"source_id": annotation["id"], "target_id": target["id"], "type": "supports", "rationale": "Evidence"}
    relation = request("post", "relations", relation_data, status=201)
    request("post", "relations", relation_data, status=409)
    request("post", "relations", {**relation_data, "target_id": annotation["id"]}, status=422)
    request("post", "relations", {**relation_data, "type": "invalid"}, status=422)
    assert request("get", "relations")["relations"] == [relation]
    for document_id in (doc["id"], second["id"]):
        assert request("get", f"documents/{document_id}")["relations"] == [relation]
    for model in (WorkbenchRevision.objects.first(), WorkbenchAnchor.objects.first()):
        try:
            model.save()
        except ValidationError:
            pass
        else:
            raise AssertionError("Immutable object was updated")
    client.force_login(other)
    assert request("get", "documents")["documents"] == []
    assert request("get", "annotations")["annotations"] == []
    assert request("get", "relations")["relations"] == []
    request("get", f'documents/{doc["id"]}', status=404)
    request("post", f'documents/{doc["id"]}/annotations', anchor, status=404)
    request("patch", endpoint, {"note": "stolen"}, status=404, HTTP_IF_MATCH='"3"')
    request("post", "relations", relation_data, status=404)
    other_doc = request("post", "documents", {"source_id": source.pk}, status=201)
    assert other_doc["id"] != second["id"]
    client.force_login(owner)
    for endpoint_url in ("documents", "annotations", "relations"):
        response = client.get(base + endpoint_url + "?domain=beta")
        assert response.status_code == 200 and not response.json()[endpoint_url]
    response = client.get(base + f'documents/{doc["id"]}?domain=beta')
    assert response.status_code == 404
    before_domains = Domain.objects.count()
    response = client.get(base + "documents?domain=unregistered")
    assert response.status_code == 404 and Domain.objects.count() == before_domains
    request("delete", f'documents/{doc["id"]}', status=405)
    response = client.get(base + "sources?domain=alpha")
    assert response.status_code == 200
    # Explicit bounded-read, invalid encoding, and stat consistency failures.
    file.write_bytes(b"x" * (service.MAX_SOURCE_BYTES + 1))
    assert request("post", "documents", {"source_id": source.pk}, status=422)["error"]["code"] == "source_too_large"
    file.write_bytes(b"\xff")
    assert request("post", "documents", {"source_id": source.pk}, status=422)["error"]["code"] == "invalid_encoding"
    file.write_bytes(b"valid")
    fstat = os.fstat
    calls = [0]
    def changed_stat(fd):
        actual = fstat(fd)
        calls[0] += 1
        if calls[0] == 2:
            return SimpleNamespace(
                st_dev=actual.st_dev, st_ino=actual.st_ino, st_size=actual.st_size,
                st_mtime_ns=actual.st_mtime_ns + 1, st_ctime_ns=actual.st_ctime_ns,
            )
        return actual
    with patch.object(service.os, "fstat", side_effect=changed_stat):
        assert request("post", "documents", {"source_id": source.pk}, status=409)["error"]["code"] == "source_changed"
    # Non-staff owners keep private snapshot access if source-capture privilege is revoked.
    owner.is_staff = False
    owner.save(update_fields=["is_staff"])
    request("get", f'documents/{doc["id"]}')
    request("get", "sources", status=403)
    assert not heartbeat.called

anonymous = Client()
assert anonymous.get(reverse("workbench")).status_code == 302
assert anonymous.get(reverse("workbench"))["Location"].startswith("/admin/login/")
csrf_client = Client(enforce_csrf_checks=True)
csrf_client.force_login(owner)
assert csrf_client.post(base + "documents?domain=alpha", {"source_id": source.pk}, content_type="application/json").status_code == 403
with patch.object(views, "render", return_value=HttpResponse("workbench")) as render:
    response = csrf_client.get(reverse("workbench") + "?domain=alpha")
    assert response.status_code == 200 and "csrftoken" in response.cookies
    context = render.call_args.args[2]
    assert context["workbench_bootstrap"]["apiBase"] == reverse("workbench-api-root")
    assert context["workbench_bootstrap"]["domain"] == "alpha"
    assert context["workbench_bootstrap"]["canCapture"] is False
csrf_token = csrf_client.cookies["csrftoken"].value
response = csrf_client.patch(
    base + f'annotations/{annotation["id"]}?domain=alpha',
    data=json.dumps({"note": "Valid CSRF and private-owner update"}),
    content_type="application/json", HTTP_X_CSRFTOKEN=csrf_token, HTTP_IF_MATCH='"3"',
)
assert response.status_code == 200 and response.json()["version"] == 4
print("Workbench migrations, ORM, API, authorization, anchors, concurrency and CSRF verified.")
'''


DRAFT_CHAT_SCENARIO = BACKEND_SCENARIO.split("\nwith patch", 1)[0] + r'''
from ki_core.core.errors import ProviderError, TimeoutError as ProviderTimeoutError
from ki_knowledge.django_site.workbench_models import WorkbenchConversation, WorkbenchMessage

with patch("ki_knowledge.django_site.sources_browser.domain_source_dir", side_effect=lambda kind, domain: root if kind == "markdown" else root / kind):
    request("post", "drafts", {"title": "Anonymous"}, status=401)
    client.force_login(ordinary)
    standalone = request("post", "drafts", {"title": "My own note"}, status=201)
    assert standalone["kind"] == "draft" and standalone["source_id"] is None
    assert standalone["origin_revision_id"] is None and standalone["revision"]["text"] == ""
    assert standalone["revision"]["cause"] == "manual_create"
    assert standalone["revision"]["content_sha256"] == hashlib.sha256(b"").hexdigest()
    assert standalone["etag"] == '"1"' and standalone["is_head"]
    unicode_note = request("post", "drafts",
        {"title": "Unicode note", "text": "😀e\u0301\r\nline\rend"}, status=201)
    assert unicode_note["revision"]["text"] == "😀e\u0301\nline\nend"
    assert unicode_note["revision"]["content_sha256"] == hashlib.sha256("😀e\u0301\nline\nend".encode()).hexdigest()
    for data in ({}, {"title": ""}, {"title": " "}, {"title": "x"*256},
        {"title": "Bad", "domain": "beta"}, {"title": "Bad", "source_id": source.pk},
        {"title": "Bad", "text": "\ud800"}):
        request("post", "drafts", data, status=422)
    try:
        service.create_empty_draft(ordinary, domain,
            {"title": "Too many UTF-8 bytes", "text": "😀" * (service.MAX_SOURCE_BYTES // 4 + 1)})
    except service.WorkbenchError as error:
        assert error.status == 422 and "text" in error.fields
    else:
        raise AssertionError("Expected UTF-8 byte limit validation")
    before_documents = WorkbenchDocument.objects.count()
    before_revisions = WorkbenchRevision.objects.count()
    with patch.object(WorkbenchRevision.objects, "create", side_effect=RuntimeError("new draft failed")):
        try:
            service.create_empty_draft(ordinary, domain, {"title": "Failed note"})
        except RuntimeError as error:
            assert str(error) == "new draft failed"
        else:
            raise AssertionError("Expected failed standalone draft persistence")
    assert WorkbenchDocument.objects.count() == before_documents
    assert WorkbenchRevision.objects.count() == before_revisions
    client.force_login(owner)
    request("get", f'documents/{standalone["id"]}', status=404)
    response = client.post(base + "drafts?domain=unregistered",
        data=json.dumps({"title": "No domain creation"}), content_type="application/json")
    assert response.status_code == 404 and not Domain.objects.filter(slug="unregistered").exists()
    reference = request("post", "documents", {"source_id": source.pk}, status=201)
    original_bytes = file.read_bytes()
    request("post", f'documents/{reference["id"]}/revisions',
        {"base_revision_id": reference["revision"]["id"], "text": "No"},
        HTTP_IF_MATCH=reference["etag"], status=403)
    draft = request("post", f'documents/{reference["id"]}/drafts', {}, status=201)
    assert draft["kind"] == "draft" and draft["source_id"] is None
    assert draft["origin_revision_id"] == reference["revision"]["id"]
    assert draft["revision"]["text"] == canonical and draft["revision"]["cause"] == "clone"
    assert draft["etag"] == '"1"' and draft["is_head"] is True
    first_revision = draft["revision"]["id"]
    mark = {
        "revision_id": first_revision, "start": 0, "end": 1, "exact": "#", "prefix": "", "suffix": " Héllo",
        "title": "Original marker", "note": "Must survive", "tags": ["history"],
    }
    annotation = request("post", f'documents/{draft["id"]}/annotations', mark, status=201)
    text = "Changed 😀 text\r\n"
    save = {"base_revision_id": first_revision, "text": text}
    endpoint = f'documents/{draft["id"]}/revisions'
    request("post", endpoint, save, status=428)
    request("post", endpoint, save, status=412, HTTP_IF_MATCH='"0"')
    request("post", endpoint, {**save, "base_revision_id": str(uuid.uuid4())},
        status=412, HTTP_IF_MATCH=draft["etag"])
    current = request("post", endpoint, save, status=201, HTTP_IF_MATCH=draft["etag"])
    assert current["version"] == 2 and current["etag"] == '"2"'
    assert current["revision"]["parent_id"] == first_revision
    assert current["revision"]["text"] == "Changed 😀 text\n"
    assert current["annotations"] == [] and len(current["historical_annotations"]) == 1
    assert current["historical_annotations"][0]["id"] == annotation["id"]
    assert current["historical_annotations"][0]["stale"] is True
    assert file.read_bytes() == original_bytes
    request("post", endpoint, save, status=412, HTTP_IF_MATCH=draft["etag"])
    historical = request("get", f'{endpoint}/{first_revision}')
    assert historical["revision"]["text"] == canonical and historical["is_head"] is False
    assert historical["annotations"][0]["id"] == annotation["id"]
    revisions = request("get", endpoint)["revisions"]
    assert [item["id"] for item in revisions] == [first_revision, current["revision"]["id"]]
    request("get", f'{endpoint}/{reference["revision"]["id"]}', status=404)
    # A previously loaded object cannot overwrite the new head even with its own stale version.
    stale = WorkbenchDocument.objects.get(pk=draft["id"])
    third = request("post", endpoint,
        {"base_revision_id": current["revision"]["id"], "text": "New 😀 passage"},
        HTTP_IF_MATCH=current["etag"], status=201)
    try:
        service.save_revision(stale, {"base_revision_id": stale.head_revision_id, "text": "Lost"}, '"2"')
    except service.WorkbenchError as error:
        assert error.status == 412
    else:
        raise AssertionError("Stale object overwrote newer head")
    durable = WorkbenchDocument.objects.get(pk=draft["id"])
    revision_count = durable.revisions.count()
    with patch.object(WorkbenchRevision.objects, "create", side_effect=RuntimeError("revision failed")):
        try:
            service.save_revision(durable,
                {"base_revision_id": durable.head_revision_id, "text": "Failed save"}, third["etag"])
        except RuntimeError as error:
            assert str(error) == "revision failed"
        else:
            raise AssertionError("Expected failed revision persistence")
    durable.refresh_from_db()
    assert durable.head_revision_id == uuid.UUID(third["revision"]["id"])
    assert durable.version == third["version"] and durable.revisions.count() == revision_count
    # An anchor is explicitly added on the new revision; the original anchor remains unchanged.
    reassign = {
        "revision_id": third["revision"]["id"], "start": 4, "end": 5,
        "exact": "😀", "prefix": "New ", "suffix": " passage",
    }
    anchor_endpoint = f'annotations/{annotation["id"]}/anchors'
    request("post", anchor_endpoint, reassign, status=428)
    request("post", anchor_endpoint, reassign, status=412, HTTP_IF_MATCH='"0"')
    request("post", anchor_endpoint, {**reassign, "exact": "x"}, status=422, HTTP_IF_MATCH='"1"')
    reassigned = request("post", anchor_endpoint, reassign, status=201, HTTP_IF_MATCH='"1"')
    assert reassigned["version"] == 2 and reassigned["exact"] == "😀" and not reassigned["stale"]
    assert reassigned["title"] == "Original marker" and reassigned["note"] == "Must survive"
    request("post", anchor_endpoint, reassign, status=409, HTTP_IF_MATCH='"2"')
    assert WorkbenchAnchor.objects.filter(annotation_id=annotation["id"]).count() == 2
    old = request("get", f'{endpoint}/{first_revision}')["annotations"][0]
    assert old["exact"] == "#" and old["revision_id"] == first_revision
    assert request("get", f'documents/{draft["id"]}')["historical_annotations"] == []
    assert len(request("get", f'documents/{draft["id"]}')["annotations"]) == 1
    assert file.read_bytes() == original_bytes

    # Provider configuration is visible without sending any text.
    with patch.object(service.llm_provider, "chat_settings", return_value={"provider": "mock", "model": "test", "base_url": ""}):
        config = request("get", "provider")
        assert config["model"] == "test" and config["max_context_chars"] == 60000
        assert request("get", "chat/config") == config
        conversation = request("post", "conversations", {
            "document_id": draft["id"], "revision_id": third["revision"]["id"],
        }, status=201)
        assert conversation["messages"] == [] and not conversation["pending"]
        conv_endpoint = f'conversations/{conversation["id"]}'
        listing = request("get", "conversations")["conversations"]
        assert listing[0]["id"] == conversation["id"]
        response = client.get(base + "conversations?domain=alpha&document_id=" + draft["id"])
        assert response.status_code == 200 and len(response.json()["conversations"]) == 1
        assert request("get", conv_endpoint) == conversation
        counts = (WorkbenchDocument.objects.count(), WorkbenchRevision.objects.count())
        payload = {
            "request_id": str(uuid.uuid4()), "message": "Discuss this unsaved draft.",
            "buffer_text": "Unsaved 😀 argument", "base_revision_id": third["revision"]["id"],
            "reference_revision_ids": [reference["revision"]["id"]],
        }
        adapter = SimpleNamespace(chat=lambda request: None, timeout=300)
        captured = []
        def answer(chat_request):
            captured.append(chat_request)
            # Reentrant repeated request observes the durable pending turn rather than sending twice.
            repeated = request("post", conv_endpoint + "/messages", payload)
            assert repeated["status"] == "pending"
            request("post", conv_endpoint + "/messages",
                {**payload, "request_id": str(uuid.uuid4())}, status=409)
            return SimpleNamespace(message=SimpleNamespace(content="An answer, not an edit."), model="test")
        adapter.chat = answer
        with patch.object(service.llm_provider, "chat_client", return_value=adapter) as provider:
            turn = request("post", conv_endpoint + "/messages", payload, status=201)
            assert turn["status"] == "complete" and turn["answer"] == "An answer, not an edit."
            assert turn["provider"] == "mock" and turn["model"] == "test"
            assert adapter.timeout == 60 and provider.call_count == 1
            assert request("post", conv_endpoint + "/messages", payload)["id"] == turn["id"]
            assert provider.call_count == 1
        nested_payload = {
            "request_id": str(uuid.uuid4()), "message": "Nested browser context",
            "context": {
                "reference_revision_ids": [reference["revision"]["id"]],
                "buffer_text": "Nested unsaved 😀 buffer",
                "base_revision_id": third["revision"]["id"],
            },
        }
        with patch.object(service.llm_provider, "chat_client", return_value=SimpleNamespace(
            chat=lambda req: SimpleNamespace(message=SimpleNamespace(content="Nested context answer")),
        )) as nested_provider:
            nested_turn = request("post", conv_endpoint + "/messages", nested_payload, status=201)
            assert nested_turn["context"]["sources"][0]["text"] == "Nested unsaved 😀 buffer"
            assert nested_turn["context"]["sources"][1]["revision_id"] == reference["revision"]["id"]
            assert nested_turn["context"]["unsaved"] is True
            assert request("post", conv_endpoint + "/messages", nested_payload)["id"] == nested_turn["id"]
            assert nested_provider.call_count == 1
        request("post", conv_endpoint + "/messages",
            {**nested_payload, "request_id": str(uuid.uuid4()), "buffer_text": "Mixed"}, status=422)
        request("post", conv_endpoint + "/messages",
            {**nested_payload, "request_id": str(uuid.uuid4()), "context": []}, status=422)
        request("post", conv_endpoint + "/messages",
            {**nested_payload, "request_id": str(uuid.uuid4()), "context": {"domain": "beta"}}, status=422)
        sources = turn["context"]["sources"]
        assert turn["context"]["unsaved"] is True
        assert sources[0]["unsaved"] is True and sources[0]["text"] == payload["buffer_text"]
        assert sources[0]["content_sha256"] == hashlib.sha256(payload["buffer_text"].encode()).hexdigest()
        assert sources[1]["text"] == canonical and not sources[1]["unsaved"]
        assert sources[1]["revision_id"] == reference["revision"]["id"]
        assert "citations" not in turn
        prompt = "\n".join(message.content for message in captured[0].messages)
        assert "untrusted source data" in prompt
        assert payload["buffer_text"] in prompt and canonical.splitlines()[0] in prompt
        assert "outside secret" not in prompt
        assert (WorkbenchDocument.objects.count(), WorkbenchRevision.objects.count()) == counts
        assert request("get", f'documents/{draft["id"]}')["revision"]["text"] == "New 😀 passage"
        request("post", conv_endpoint + "/messages", {**payload, "message": "Reused ID"}, status=409)
        request("post", conv_endpoint + "/messages",
            {**payload, "reference_revision_ids": [], "request_id": payload["request_id"]}, status=409)
        # Invalid contexts never trigger provider calls or persist a turn.
        bad_payloads = [
            {"message": "x" * 8001}, {"buffer_text": "x" * 60001},
            {"reference_revision_ids": [str(uuid.uuid4())]},
            {"reference_revision_ids": [third["revision"]["id"]]},
            {"base_revision_id": first_revision},
        ]
        for replacement in bad_payloads:
            request("post", conv_endpoint + "/messages",
                {**payload, "request_id": str(uuid.uuid4()), **replacement},
                status=404 if "reference_revision_ids" in replacement else (412 if "base_revision_id" in replacement else 422))
        assert WorkbenchMessage.objects.count() == 2
        # Each provider failure leaves a concrete durable failed turn and releases the reservation.
        for exception, expected in (
            (ProviderError("provider down"), "ProviderError"),
            (ProviderTimeoutError("timeout"), "timed out"),
        ):
            failure_data = {"request_id": str(uuid.uuid4()), "message": "Try provider"}
            with patch.object(service.llm_provider, "chat_client", side_effect=exception):
                failed = request("post", conv_endpoint + "/messages", failure_data, status=502)
            assert failed["status"] == "failed" and expected in failed["error"]["message"]
            persisted = request("get", conv_endpoint)
            assert persisted["messages"][-1]["status"] == "failed" and not persisted["pending"]
        # A worker death leaves a durable pending turn; a later explicit send recovers it.
        from datetime import timedelta
        from django.utils import timezone
        abandoned_id = uuid.uuid4()
        abandoned = WorkbenchMessage.objects.create(
            conversation_id=conversation["id"], request_id=abandoned_id, message="Interrupted",
            provider="mock", model="test",
        )
        WorkbenchMessage.objects.filter(pk=abandoned.pk).update(
            created_at=timezone.now() - timedelta(seconds=service.CHAT_RESERVATION_SECONDS + 1),
        )
        WorkbenchConversation.objects.filter(pk=conversation["id"]).update(pending_request=abandoned_id)
        assert request("get", conv_endpoint)["pending"] is True
        abandoned.refresh_from_db()
        assert abandoned.status == "pending"  # Read-only GET did not recover or write.
        late_turn = []
        recovery_payload = {"request_id": str(uuid.uuid4()), "message": "Recover abandoned turn"}
        def late_answer(chat_request):
            in_flight = WorkbenchMessage.objects.get(
                conversation_id=conversation["id"], request_id=recovery_payload["request_id"],
            )
            WorkbenchMessage.objects.filter(pk=in_flight.pk).update(
                created_at=timezone.now() - timedelta(seconds=service.CHAT_RESERVATION_SECONDS + 1),
            )
            service.expire_abandoned_request(WorkbenchConversation.objects.get(pk=conversation["id"]))
            late_turn.append(in_flight.pk)
            return SimpleNamespace(message=SimpleNamespace(content="Late response must not replace failed turn."))
        with patch.object(service.llm_provider, "chat_client", return_value=SimpleNamespace(chat=late_answer)):
            recovered = request("post", conv_endpoint + "/messages", recovery_payload, status=502)
        abandoned.refresh_from_db()
        assert abandoned.status == "failed" and "expired" in abandoned.error
        assert recovered["status"] == "failed"
        assert WorkbenchMessage.objects.get(pk=late_turn[0]).answer == ""
        assert not request("get", conv_endpoint)["pending"]
        # Annotation conversations send only the exact selected quote, not the containing document.
        selected = request("post", "conversations", {
            "document_id": draft["id"], "revision_id": first_revision, "annotation_id": annotation["id"],
        }, status=201)
        with patch.object(service.llm_provider, "chat_client", return_value=SimpleNamespace(
            chat=lambda req: SimpleNamespace(message=SimpleNamespace(content="About the selected quote.")),
        )):
            selected_turn = request("post", f'conversations/{selected["id"]}/messages', {
                "request_id": str(uuid.uuid4()), "message": "What is selected?",
            }, status=201)
        assert selected_turn["context"]["sources"][0]["text"] == "#"
        assert selected_turn["context"]["sources"][0]["annotation_id"] == annotation["id"]
        assert selected_turn["context"]["sources"][0]["start"] == 0
        request("post", f'conversations/{selected["id"]}/messages', {
            **payload, "request_id": str(uuid.uuid4()),
        }, status=422)
        # New head invalidates an unsaved context based on the prior head.
        request("post", endpoint, {"base_revision_id": third["revision"]["id"], "text": "Fourth"},
            HTTP_IF_MATCH=third["etag"], status=201)
        request("post", conv_endpoint + "/messages", {**payload, "request_id": str(uuid.uuid4())}, status=412)
    # A staff user has no global access to another owner's authoring or conversations.
    client.force_login(other)
    for path in (
        f'documents/{draft["id"]}', endpoint, f'{endpoint}/{first_revision}',
        conv_endpoint, f'conversations/{selected["id"]}',
    ):
        request("get", path, status=404)
    request("post", f'documents/{draft["id"]}/drafts', {}, status=404)
    request("post", anchor_endpoint, reassign, HTTP_IF_MATCH='"2"', status=404)
    request("post", "conversations", {
        "document_id": draft["id"], "revision_id": first_revision,
    }, status=404)
    request("post", conv_endpoint + "/messages", {"request_id": str(uuid.uuid4()), "message": "steal"}, status=404)
    assert request("get", "conversations")["conversations"] == []
    own_reference = request("post", "documents", {"source_id": source.pk}, status=201)
    own_conversation = request("post", "conversations", {
        "document_id": own_reference["id"], "revision_id": own_reference["revision"]["id"],
    }, status=201)
    with patch.object(service.llm_provider, "chat_client") as no_provider:
        rejected = request("post", f'conversations/{own_conversation["id"]}/messages', {
            "request_id": str(uuid.uuid4()), "message": "Read private material",
            "reference_revision_ids": [reference["revision"]["id"]],
        }, status=404)
        assert not no_provider.called
        assert reference["title"] not in json.dumps(rejected)
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(other)
    assert csrf_client.post(base + f'conversations/{own_conversation["id"]}/messages?domain=alpha',
        {"request_id": str(uuid.uuid4()), "message": "Without CSRF"}, content_type="application/json").status_code == 403
    client.force_login(owner)
    response = client.get(base + conv_endpoint + "?domain=beta")
    assert response.status_code == 404
    response = client.get(base + "conversations?domain=beta")
    assert response.status_code == 200 and response.json()["conversations"] == []
    assert file.read_bytes() == original_bytes
print("Draft history, head conflicts, reanchoring, exact chat context, failures and isolation verified.")
'''


MIGRATION_SCENARIO = BACKEND_SCENARIO.split('call_command("migrate", verbosity=0, interactive=False)')[0] + r'''
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
executor = MigrationExecutor(connection)
executor.migrate([("django_site", "0020_workbench")])
historical = executor.loader.project_state([("django_site", "0020_workbench")]).apps
User = historical.get_model("auth", "User")
Domain = historical.get_model("django_site", "Domain")
Project = historical.get_model("django_site", "InfoSiteProject")
Source = historical.get_model("django_site", "SourceDocument")
Document = historical.get_model("django_site", "WorkbenchDocument")
Revision = historical.get_model("django_site", "WorkbenchRevision")
Annotation = historical.get_model("django_site", "WorkbenchAnnotation")
Anchor = historical.get_model("django_site", "WorkbenchAnchor")
owner = User.objects.create(username="migration-user")
domain = Domain.objects.create(slug="migration")
project = Project.objects.create(title="Migrated project", domain="migration")
source = Source.objects.create(project=project, file_path="source.md")
document = Document.objects.create(owner=owner, domain=domain, source=source,
    title="Historical snapshot", capture_sha256="a"*64, origin_locator="source.md")
revision = Revision.objects.create(document=document, text="Before migration", content_sha256="a"*64)
annotation = Annotation.objects.create(document=document, title="Existing marker", note="Keep")
Anchor.objects.create(annotation=annotation, revision=revision, start=0, end=6, exact="Before")
executor = MigrationExecutor(connection)
executor.migrate(executor.loader.graph.leaf_nodes())
from ki_knowledge.django_site.workbench_models import WorkbenchDocument, WorkbenchAnnotation
converted = WorkbenchDocument.objects.get(pk=document.pk)
assert converted.head_revision_id == revision.pk and converted.kind == "reference"
assert converted.revision.text == "Before migration" and converted.version == 1
assert converted.source_id == source.pk and converted.origin_locator == "source.md"
assert converted.origin_key == "" and converted.origin_metadata == {}
marker = WorkbenchAnnotation.objects.get(pk=annotation.pk)
assert marker.anchor.exact == "Before" and marker.anchors.count() == 1 and marker.note == "Keep"
call_command("makemigrations", check=True, dry_run=True, verbosity=0)
print("Existing E1 documents, immutable revisions and annotations survive E2 migration.")
'''


INVENTORY_SCENARIO = BACKEND_SCENARIO.split('root = Path(sys.argv[1]) / "markdown"')[0] + r'''
from ki_knowledge.django_site import source_access, sources_browser, knowledge_summary
from ki_knowledge.integrations.knowledge_store import KnowledgeStore, KnowledgeSource

workspace = Path(sys.argv[1])
root = workspace / "alpha"
root.mkdir()
foreign = workspace / "beta"
foreign.mkdir()
cloud = workspace / "cloud"
cloud.mkdir()
(root / "mix").symlink_to(cloud, target_is_directory=True)
(root / "linked").symlink_to(cloud, target_is_directory=True)
plain = root / "plain.md"
plain.write_text("# Vor Import\r\n\r\nText 😀\r\n", encoding="utf-8")
registered = root / "registered.md"
registered.write_text("# Registriert\n", encoding="utf-8")
(cloud / "cloud.md").write_text("# Vertrauenswürdige verlinkte Wurzel\n", encoding="utf-8")
outside = workspace / "secret.md"
outside.write_text("not a source", encoding="utf-8")
(root / "escape.md").symlink_to(outside)
(root / "manual.pdf").write_bytes(b"%PDF")
(foreign / "foreign.md").write_text("foreign", encoding="utf-8")
alpha = Domain.objects.create(slug="alpha")
beta = Domain.objects.create(slug="beta")
owner = get_user_model().objects.create_user(username="inventory-owner", is_staff=True)
ordinary = get_user_model().objects.create_user(username="inventory-reader")
other = get_user_model().objects.create_user(username="inventory-other", is_staff=True)
store = KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)
store.upsert_source(KnowledgeSource(source_id="registered:one", source_type="markdown",
    title="Registered source", location=str(registered), metadata={}))
store.upsert_source(KnowledgeSource(source_id="registered:foreign", source_type="markdown",
    title="Foreign source", location=str(foreign / "foreign.md"), metadata={}))
store.upsert_source(KnowledgeSource(source_id="registered:missing", source_type="markdown",
    title="Missing source", location=str(root / "missing.md"), metadata={}))
def folder(kind, domain):
    base = root if domain == "alpha" else foreign
    return base if kind == "markdown" else base / kind
client = Client()
base = "/knowledge/workbench/api/"
def request(method, endpoint, data=None, status=200, domain="alpha"):
    response = getattr(client, method)(
        base + endpoint + "?domain=" + domain,
        data=json.dumps(data) if data is not None else None, content_type="application/json")
    assert response.status_code == status, (endpoint, response.status_code, response.content)
    return response.json()

with patch.object(sources_browser, "domain_source_dir", side_effect=folder), \
     patch.object(sources_browser, "domain_jira_dir", side_effect=lambda domain: folder("jira", domain)), \
     patch.object(sources_browser, "_pdf_job_states", return_value={}), \
     patch.object(knowledge_summary, "domain_source_roots", side_effect=lambda domain: [root] if domain == "alpha" else [foreign]), \
     patch("ki_knowledge.django_site.views_common.maybe_send_automatic_heartbeat"):
    assert InfoSiteProject.objects.count() == SourceDocument.objects.count() == 0
    request("get", "sources", status=401)
    client.force_login(ordinary)
    request("get", "sources", status=403)
    client.force_login(owner)
    before_sources = len(store.list_sources())
    response = request("get", "sources")
    available = {item["title"]: item for item in response["sources"]}
    assert set(available) == {"plain.md", "Registered source", "cloud.md"}, response
    assert not available["plain.md"]["registered"] and available["Registered source"]["registered"]
    reasons = {item["title"]: item["reason"] for item in response["excluded"]}
    assert {"escape.md", "manual.pdf", "Missing source"} <= reasons.keys()
    assert all(reasons.values())
    plain_id = available["plain.md"]["id"]
    registered_id = available["Registered source"]["id"]
    assert len(plain_id) == 68 and str(root) not in plain_id
    assert request("get", "sources") == response
    assert WorkbenchDocument.objects.count() == 0
    for bad in (str(plain), "../plain.md", "registered:one", "src_" + "0"*64):
        request("post", "documents", {"source_id": bad}, status=404 if bad.startswith("src_") else 422)
    request("post", "documents", {"source_id": plain_id, "path": str(plain)}, status=422)
    request("post", "documents", {"source_id": plain_id}, status=404, domain="beta")
    escaped_id = next(item["id"] for item in response["excluded"] if item["title"] == "escape.md")
    request("post", "documents", {"source_id": escaped_id}, status=422)
    first = request("post", "documents", {"source_id": plain_id}, status=201)
    assert first["source_id"] is None
    assert first["origin_metadata"] == {"kind": "discovered", "source_id": "", "folder": "md", "relative": "plain.md"}
    assert first["revision"]["text"] == "# Vor Import\n\nText 😀\n"
    assert plain.read_bytes() == "# Vor Import\r\n\r\nText 😀\r\n".encode("utf-8")
    assert request("post", "documents", {"source_id": plain_id})["id"] == first["id"]
    captured_registered = request("post", "documents", {"source_id": registered_id}, status=201)
    assert captured_registered["origin_metadata"]["source_id"] == "registered:one"
    request("post", "documents", {"source_id": available["cloud.md"]["id"]}, status=201)
    assert len(store.list_sources()) == before_sources
    assert InfoSiteProject.objects.count() == SourceDocument.objects.count() == 0
    assert store.list_records() == []
    # Registering a formerly discovered file must reuse its existing snapshot.
    store.upsert_source(KnowledgeSource(source_id="registered:plain", source_type="markdown",
        title="Now registered", location=str(plain), metadata={}))
    refreshed = request("get", "sources")
    new_id = next(item["id"] for item in refreshed["sources"] if item["title"] == "Now registered")
    assert request("post", "documents", {"source_id": new_id})["id"] == first["id"]
    request("post", "documents", {"source_id": plain_id}, status=404)
    # Alias registrations remain visible as an explicit duplicate exclusion.
    store.upsert_source(KnowledgeSource(source_id="registered:alias", source_type="markdown",
        title="Alias", location=str(plain), metadata={}))
    duplicates = request("get", "sources")
    assert len([item for item in duplicates["sources"] if item["relative"] == "plain.md"]) == 1
    assert any("bereits" in item["reason"] for item in duplicates["excluded"])
    # A formerly safe file cannot become an arbitrary outside symlink.
    registered.unlink()
    registered.symlink_to(outside)
    request("post", "documents", {"source_id": registered_id}, status=422)
    assert request("get", f'documents/{captured_registered["id"]}')["revision"]["text"] == "# Registriert\n"
    assert sources_browser.resolve_folder_file("alpha", "md", "../secret.md") is None
    assert sources_browser.resolve_folder_file("alpha", "md", str(outside)) is None
    assert sources_browser.resolve_folder_file("alpha", "md", "escape.md") is None
    assert sources_browser.resolve_folder_file("alpha", "mix", "cloud.md") is not None
    rows = source_access.inventory("alpha")
    selected = next(row for row in rows if row["title"] == "cloud.md")
    assert "?domain=alpha&source_id=src_" in selected["workbench_url"]
    client.force_login(other)
    request("get", f'documents/{first["id"]}', status=404)
    client.force_login(ordinary)
    request("post", "documents", {"source_id": new_id}, status=403)
    # Reading an owner's existing snapshot remains allowed without source access.
    WorkbenchDocument.objects.filter(pk=first["id"]).update(owner=ordinary)
    assert request("get", f'documents/{first["id"]}')["revision"]["text"].startswith("# Vor Import")
    assert InfoSiteProject.objects.count() == 0
print("General inventory, zero InfoSites, registered/discovered capture, links, deduplication, explicit exclusions and domain/owner/staff boundaries verified.")
'''

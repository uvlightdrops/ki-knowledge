import copy
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from wsgiref.simple_server import WSGIRequestHandler, make_server

import django
import pytest
import requests

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from django.conf import settings
from django.core.handlers.wsgi import WSGIHandler
from django.db import connections
from django.test import RequestFactory
from django.urls import resolve, reverse

from ki_knowledge.django_site import distributed_api, distributed_sync, knowledge_summary, views, views_sync
from ki_knowledge.django_site.infosite_models import Domain
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.sql_backend import StoreTarget, connect
from ki_knowledge.knowledge.contributions import (
    ContributionConflict, digest, export_contribution, identity, prepare_contribution,
)
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeSource
from ki_knowledge.node_sync import NodeSettings, PATH_CONTRIBUTE, SyncClient


def contributor(tmp_path, origin="a"):
    store = KnowledgeStore(tmp_path / f"{origin}.sqlite")
    store.upsert_source(KnowledgeSource("doc", "markdown", "Input", "/same/path", {"domain": "lab"}))
    store.upsert_record(KnowledgeBlockRecord("input", "doc", "paragraph", "Input", f"input from {origin}",
                                            object_type="text"))
    store.upsert_record(KnowledgeBlockRecord("output", "doc", "paragraph", "Output", f"output from {origin}",
                                            parent_block_id="input", object_type="text"))
    store.upsert_artifact(KnowledgeArtifact("result", "markdown", "doc", ["input", "output"], "generated", {}))
    store.add_relation("input", "output", "produces", 0.5, {"note": "graph"})
    return store


def envelope(store, origin="a", revision="r1"):
    return export_contribution(store, domain="lab", origin_node_id=origin, revision=revision, source_ids=["doc"])


def reseal(payload):
    payload["digest"] = digest({key: value for key, value in payload.items() if key != "digest"})
    return payload


def test_two_contributors_graph_replay_and_immutable_revisions(tmp_path):
    a, b = contributor(tmp_path, "a"), contributor(tmp_path, "b")
    central = KnowledgeStore(tmp_path / "central.sqlite")
    central.upsert_source(KnowledgeSource("doc", "local", "Local", "/local"))
    central.upsert_record(KnowledgeBlockRecord("input", "doc", "paragraph", "Local", "untouched"))
    pa, pb = envelope(a), envelope(b, "b")
    counts = {"sources": 1, "records": 2, "artifacts": 1, "relations": 1}
    assert central.ingest_contribution(pa)["imported"] == counts
    assert central.ingest_contribution(pb)["imported"] == counts
    assert central.ingest_contribution(pa)["status"] == "replayed"
    assert central.ingest_contribution(pa)["imported"] == dict.fromkeys(counts, 0)
    assert len(central.list_records()) == 5
    assert central.get_record("input").content == "untouched"
    for origin in ("a", "b"):
        source_id = identity("lab", origin, "r1", "sources", "doc")
        input_id = identity("lab", origin, "r1", "records", "input")
        output_id = identity("lab", origin, "r1", "records", "output")
        artifact_id = identity("lab", origin, "r1", "artifacts", "result")
        record = central.get_record(output_id)
        source = central.get_source(source_id)
        assert source.location == "contribution:" + source_id
        assert source.metadata["contribution"]["original_location"] == "/same/path"
        assert record.source_id == source_id and record.parent_block_id == input_id
        assert record.metadata["contribution"]["origin_node_id"] == origin
        assert record.metadata["contribution"]["original_refs"]["parent_block_id"] == "input"
        assert central.get_artifact(artifact_id).source_block_ids == [input_id, output_id]
        relation = central.list_relations(input_id)[0]
        assert relation["target_block_id"] == output_id and relation["weight"] == 0.5
        assert relation["metadata"]["contribution"]["origin_node_id"] == origin
    changed = copy.deepcopy(pa)
    changed["records"][0]["content"] = "changed"
    with pytest.raises(ContributionConflict, match="different digest"):
        central.ingest_contribution(reseal(changed))
    changed["revision"] = "r2"
    central.ingest_contribution(reseal(changed))
    assert len(central.list_records()) == 7
    assert central.get_record(identity("lab", "a", "r1", "records", "input")).content == "input from a"
    assert central.get_record(identity("lab", "a", "r2", "records", "input")).content == "changed"
    # Receipt persists across store instances.
    assert KnowledgeStore(tmp_path / "central.sqlite").ingest_contribution(pa)["status"] == "replayed"


@pytest.mark.parametrize("mutation", [
    lambda p: p.pop("origin_node_id"),
    lambda p: p.update(origin_node_id=" "),
    lambda p: p.update(domain="Other Domain"),
    lambda p: p.update(version="knowledge.contribution/2"),
    lambda p: p.update(records={}),
    lambda p: p["records"].append("bad"),
    lambda p: p["records"][0].update(object_type="alien"),
    lambda p: p["records"][0].update(order_index=True),
    lambda p: p["records"][0].update(content=[]),
    lambda p: p["records"][0].update(parent_block_id="foreign"),
    lambda p: p["records"][0].update(source_id="missing"),
    lambda p: p["records"][0].update(tags="bad"),
    lambda p: p["sources"][0].update(metadata=[]),
    lambda p: p["sources"][0]["metadata"].update(domain="wrong"),
    lambda p: p["sources"][0]["metadata"].update(contribution={"origin_node_id": "b"}),
    lambda p: p["sources"][0]["metadata"].update(provenance={"origin_node_id": "b"}),
    lambda p: p["sources"][0]["metadata"].update(provenance={"domain": "wrong"}),
    lambda p: p["records"][0]["metadata"].update(source_id="other"),
    lambda p: p["artifacts"][0].update(source_block_ids=["unknown"]),
    lambda p: p["relations"][0].update(target_block_id="elsewhere"),
    lambda p: p["relations"][0].update(weight="1"),
    lambda p: p["sources"].append(copy.deepcopy(p["sources"][0])),
    lambda p: p["relations"].append(copy.deepcopy(p["relations"][0])),
    lambda p: p.update(sources=[]),
])
def test_entire_payload_validated_without_mutation(tmp_path, mutation):
    payload = envelope(contributor(tmp_path))
    mutation(payload)
    central = KnowledgeStore(tmp_path / "central.sqlite")
    with pytest.raises(ValueError):
        central.ingest_contribution(reseal(payload))
    assert central.list_sources() == []
    assert central.list_records() == []
    with central._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM knowledge_contributions").fetchone()[0] == 0


def test_digest_finite_fields_and_reserved_import_ownership(tmp_path):
    payload = envelope(contributor(tmp_path))
    payload["digest"] = "wrong"
    with pytest.raises(ValueError, match="digest mismatch"):
        prepare_contribution(payload)
    payload["relations"][0]["weight"] = float("nan")
    with pytest.raises(ValueError, match="finite"):
        reseal(payload)
    central = KnowledgeStore(tmp_path / "central.sqlite")
    central.ingest_contribution(envelope(contributor(tmp_path, "b"), "b"))
    source_id = central.list_sources()[0].source_id
    with pytest.raises(ValueError, match="reserved"):
        export_contribution(central, domain="lab", origin_node_id="central", revision="r1", source_ids=[source_id])


def test_export_requires_explicit_closed_source_selection(tmp_path):
    local = contributor(tmp_path)
    local.upsert_source(KnowledgeSource("second", "markdown", "Other", "/other", {"domain": "lab"}))
    local.upsert_record(KnowledgeBlockRecord("second-block", "second", "paragraph", "Other", "other",
                                           object_type="text"))
    local.add_relation("input", "second-block")
    with pytest.raises(ValueError, match="outside contribution domain scope"):
        envelope(local)
    payload = export_contribution(local, domain="lab", origin_node_id="a", revision="r1",
                                  source_ids=["doc", "second"])
    assert len(prepare_contribution(payload).relations) == 2
    with pytest.raises(ValueError, match="unknown source"):
        export_contribution(local, domain="lab", origin_node_id="a", revision="r1", source_ids=["unknown"])


@pytest.mark.parametrize("kind", ["sources", "records", "artifacts", "relations"])
def test_destination_collision_rolls_back_everything(tmp_path, kind):
    central = KnowledgeStore(tmp_path / "central.sqlite")
    payload = envelope(contributor(tmp_path))
    prepared = prepare_contribution(payload)
    item = getattr(prepared, kind)[0]
    if kind == "sources":
        central.upsert_source(KnowledgeSource(item.source_id, "local", "collision", "/local"))
    elif kind == "records":
        central.upsert_source(KnowledgeSource("local", "local", "local", "/local"))
        central.upsert_record(KnowledgeBlockRecord(item.block_id, "local", "paragraph", "collision", "local"))
    elif kind == "artifacts":
        central.upsert_artifact(KnowledgeArtifact(item.artifact_id, "local", "local", [], "local", {}))
    else:
        central.add_relation(item.source_block_id, item.target_block_id, item.relation, metadata={"local": True})
    before = (central.list_sources(), central.list_records(), central.list_artifacts(), central.list_relations())
    with pytest.raises(ContributionConflict, match="already exists"):
        central.ingest_contribution(payload)
    assert before == (central.list_sources(), central.list_records(), central.list_artifacts(), central.list_relations())


def test_atomic_failure_and_concurrent_replay(tmp_path, monkeypatch):
    central = KnowledgeStore(tmp_path / "central.sqlite")
    payload = envelope(contributor(tmp_path))
    original = KnowledgeStore.upsert_artifact

    def fail(self, artifact):
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(KnowledgeStore, "upsert_artifact", fail)
    with pytest.raises(RuntimeError, match="storage failure"):
        central.ingest_contribution(payload)
    assert central.list_sources() == [] and central.list_records() == []
    monkeypatch.setattr(KnowledgeStore, "upsert_artifact", original)
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: central.ingest_contribution(payload), range(2)))
    assert sorted(result["status"] for result in results) == ["accepted", "replayed"]
    assert len(central.list_records()) == 2


@pytest.fixture()
def central_runtime(tmp_path, monkeypatch):
    # A real isolated Django domain registry, no production DB and no migrations.
    alias = "contribution_tests"
    connections.databases[alias] = {
        **connections.databases["default"], "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(tmp_path / "registry.sqlite"), "OPTIONS": {}, "ATOMIC_REQUESTS": False,
    }
    connection = connections[alias]
    with connection.schema_editor() as editor:
        editor.create_model(Domain)
    manager = Domain.objects.db_manager(alias)
    domain = manager.create(slug="lab", home_node="central", visibility="shared")
    proxy = SimpleNamespace(objects=manager)
    monkeypatch.setattr(distributed_api, "Domain", proxy)
    monkeypatch.setattr(distributed_sync, "Domain", proxy)
    monkeypatch.setattr(distributed_api, "get_node_settings", lambda: NodeSettings(node_id="central", role="master"))
    monkeypatch.setattr(distributed_api, "get_sync_secret", lambda: "secret")
    monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "secret")
    central = KnowledgeStore(tmp_path / "central.sqlite")
    monkeypatch.setattr(settings, "KNOWLEDGE_STORE_TARGET", central.target)
    monkeypatch.setattr(knowledge_summary, "domain_source_roots", lambda domain: [])
    yield central, domain
    connection.close()
    del connections[alias]
    del connections.databases[alias]


def test_domain_role_secret_policy_and_source_selection(tmp_path, central_runtime, monkeypatch):
    central, domain = central_runtime
    payload = envelope(contributor(tmp_path))
    for role in ("host", "standalone"):
        monkeypatch.setattr(distributed_api, "get_node_settings", lambda: NodeSettings(node_id="central", role=role))
        with pytest.raises(PermissionError, match="master"):
            distributed_api.import_remote_contribution(payload)
    monkeypatch.setattr(distributed_api, "get_node_settings", lambda: NodeSettings(node_id="central", role="master"))
    monkeypatch.setattr(distributed_api, "get_sync_secret", lambda: "")
    with pytest.raises(PermissionError, match="configured"):
        distributed_api.import_remote_contribution(payload)
    monkeypatch.setattr(distributed_api, "get_sync_secret", lambda: "secret")
    for home, visibility in (("", "shared"), ("other", "shared"), ("central", "private"), ("central", "public")):
        domain.home_node, domain.visibility = home, visibility
        domain.save(using="contribution_tests")
        with pytest.raises(PermissionError, match="shared and owned"):
            distributed_api.import_remote_contribution(payload)
    domain.home_node, domain.visibility = "central", "shared"
    domain.save(using="contribution_tests")
    unknown = copy.deepcopy(payload)
    unknown["domain"] = "unknown"
    unknown["sources"][0]["metadata"]["domain"] = "unknown"
    with pytest.raises(ValueError, match="unknown contribution domain"):
        distributed_api.import_remote_contribution(reseal(unknown))
    with pytest.raises(ValueError, match="central node identity"):
        distributed_api.import_remote_contribution(envelope(contributor(tmp_path, "pretender"), "central"))
    assert central.list_sources() == []
    with pytest.raises(ValueError, match="outside"):
        distributed_api.export_local_contribution(domain="lab", revision="r1", source_ids=["doc"])
    distributed_api.import_remote_contribution(payload)
    domain.refresh_from_db(using="contribution_tests")
    assert domain.last_sync_at is None and domain.sync_mode == "local"
    assert domain.visibility == "shared" and domain.home_node == "central"
    assert len(knowledge_summary._domain_scoped_sources("lab")) == 1
    assert knowledge_summary._domain_scoped_sources("other") == []
    assert knowledge_summary._domain_scoped_sources("default") == []
    central.upsert_source(KnowledgeSource("legacy", "local", "Legacy global", "/local"))
    assert [source.source_id for source in knowledge_summary._domain_scoped_sources("default", limit=1)] == ["legacy"]


class QuietHandler(WSGIRequestHandler):
    def log_message(self, *args):
        pass


def test_real_http_two_stores_central_export_distribution(tmp_path, central_runtime, monkeypatch):
    central, domain = central_runtime
    a, b = contributor(tmp_path, "a"), contributor(tmp_path, "b")
    monkeypatch.setattr(distributed_sync, "local_node_snapshot",
                        lambda: distributed_sync.LocalNodeSnapshot(
                            node_id="central", role="master", base_url="",
                            distributed_enabled=True, sync_on_connect=True, master_url=""))
    monkeypatch.setattr(distributed_sync, "ensure_local_node_config", lambda: SimpleNamespace(
        node_id="central", role="master", sync_on_connect=True, is_enabled=True, last_seen_at=None))
    monkeypatch.setattr(distributed_sync.InfoSiteProject.objects, "filter", lambda **kwargs: SimpleNamespace(
        order_by=lambda *args: SimpleNamespace(count=lambda: 0)))
    server = make_server("127.0.0.1", 0, WSGIHandler(), handler_class=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    try:
        client = SyncClient(origin, secret="secret")
        assert reverse("sync-contribute") == PATH_CONTRIBUTE
        assert resolve(PATH_CONTRIBUTE).func is views.sync_contribution_view
        for secret in ("", "wrong"):
            response = requests.post(origin + PATH_CONTRIBUTE, json=envelope(a),
                                     headers={"X-KI-Sync-Secret": secret}, timeout=5)
            assert response.status_code == 403
        monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "")
        assert requests.post(origin + PATH_CONTRIBUTE, json=envelope(a), timeout=5).status_code == 403
        monkeypatch.setattr(views_sync, "_configured_sync_secret", lambda: "secret")
        for body in ("{", "[]"):
            response = requests.post(origin + PATH_CONTRIBUTE, data=body,
                                     headers={"X-KI-Sync-Secret": "secret"}, timeout=5)
            assert response.status_code == 400
        assert client.contribute(envelope(a))["status"] == "accepted"
        assert client.contribute(envelope(b, "b"))["status"] == "accepted"
        assert client.contribute(envelope(a))["status"] == "replayed"
        changed = envelope(a)
        changed["records"][0]["content"] = "conflict"
        with pytest.raises(requests.HTTPError) as error:
            client.contribute(reseal(changed))
        assert error.value.response.status_code == 409
        assert error.value.response.json()["status"] == "conflict"
        exported = client.export(domains=["lab"], include_projects=False)
        assert len(exported["domains"][0]["knowledge_sources"]) == 2
        assert {row["metadata"]["contribution"]["origin_node_id"]
                for row in exported["domains"][0]["knowledge_records"]} == {"a", "b"}
        summary = knowledge_summary.domain_knowledge_summary("lab")
        assert (summary["sources"], summary["records"], summary["artifacts"]) == (2, 4, 2)
        # Existing snapshot importer writes the original namespace/provenance unchanged,
        # rather than attributing these records to the central transport node.
        receiving = KnowledgeStore(tmp_path / "receiving.sqlite")
        monkeypatch.setattr(distributed_sync, "store", lambda: receiving)
        # Isolate the receiving registry boundary; never mutate the central domain.
        receiving_domain = SimpleNamespace(
            slug="lab", display_name="", description="", home_node="central",
            sync_mode="local", visibility="shared", last_sync_at=None,
            save=lambda **kwargs: None)
        monkeypatch.setattr(distributed_sync, "Domain", SimpleNamespace(objects=SimpleNamespace(
            get_or_create=lambda **kwargs: (receiving_domain, True))))
        distributed_sync.apply_remote_domain_payload({"node_id": "central", "domains": exported["domains"]})
        assert len(receiving.list_records()) == 4
        for record in receiving.list_records():
            assert central.get_record(record.block_id) == record
        assert receiving.list_relations() == central.list_relations()
        domain.refresh_from_db(using="contribution_tests")
        assert domain.home_node == "central" and domain.visibility == "shared"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        assert not thread.is_alive()


def test_client_and_manual_facade_export_selected_sources(tmp_path, monkeypatch):
    local = contributor(tmp_path)
    monkeypatch.setattr(distributed_api, "get_node_settings", lambda: NodeSettings(node_id="a", role="host"))
    monkeypatch.setattr(distributed_api, "Domain", SimpleNamespace(objects=SimpleNamespace(
        filter=lambda **kwargs: SimpleNamespace(exists=lambda: True))))
    monkeypatch.setattr(knowledge_summary, "_domain_scoped_sources", lambda domain: local.list_sources())
    monkeypatch.setattr(knowledge_summary, "store", lambda: local)
    monkeypatch.setattr(distributed_api, "get_sync_secret", lambda: "secret")
    monkeypatch.setattr(distributed_api, "get_master_url", lambda: "http://central")
    seen = []
    monkeypatch.setattr(distributed_api, "sync_client", lambda origin: SimpleNamespace(
        contribute=lambda payload: seen.append((origin, payload)) or {"status": "accepted"}))
    assert distributed_api.contribute_to_master(domain="lab", revision="r1", source_ids=["doc"]) == {"status": "accepted"}
    assert seen == [("http://central", envelope(local))]
    with pytest.raises(ValueError, match="configured"):
        SyncClient("http://central").contribute(envelope(local))
    request = RequestFactory().get(PATH_CONTRIBUTE)
    assert views_sync.sync_contribution_view(request).status_code == 405


def test_identical_original_locations_do_not_alias_domain_reset(tmp_path, central_runtime):
    central, _ = central_runtime
    a = envelope(contributor(tmp_path))
    b = envelope(contributor(tmp_path, "b"), "b")
    b["domain"] = "other"
    b["sources"][0]["metadata"]["domain"] = "other"
    central.ingest_contribution(a)
    central.ingest_contribution(reseal(b))
    knowledge_summary.invalidate_domain_summary_cache("lab")
    knowledge_summary.invalidate_domain_summary_cache("other")
    assert knowledge_summary.domain_knowledge_summary("lab")["records"] == 2
    assert knowledge_summary.domain_knowledge_summary("other")["records"] == 2
    assert knowledge_summary.knowledge_base_reset_domain("lab")["deleted_records"] == 2
    assert len(central.list_records()) == 2
    assert all(record.metadata["contribution"]["domain"] == "other" for record in central.list_records())


def test_receipt_table_included_in_storage_migration(tmp_path):
    from ki_knowledge.django_site.management.commands.migrate_knowledge_store_to_postgres import (
        KNOWLEDGE_TABLES, _copy_table,
    )

    source = KnowledgeStore(tmp_path / "source.sqlite")
    source.ingest_contribution(envelope(contributor(tmp_path)))
    destination = KnowledgeStore(tmp_path / "destination.sqlite")
    assert _copy_table(tmp_path / "source.sqlite", destination.target, "knowledge_contributions",
                       KNOWLEDGE_TABLES["knowledge_contributions"], batch_size=10) == 1
    with destination._connect() as conn:
        receipt = conn.execute("SELECT * FROM knowledge_contributions").fetchone()
        assert receipt["origin_node_id"] == "a" and receipt["domain"] == "lab"


def test_default_scope_initializes_empty_store(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "KNOWLEDGE_STORE_TARGET", StoreTarget.sqlite(tmp_path / "empty.sqlite"))
    assert knowledge_summary._domain_scoped_sources("default") == []


def test_nextcloud_sources_are_scoped_by_domain_not_remote_path(tmp_path, monkeypatch):
    target = StoreTarget.sqlite(tmp_path / "nextcloud-scopes.sqlite")
    monkeypatch.setattr(settings, "KNOWLEDGE_STORE_TARGET", target)
    local = KnowledgeStore(target)
    local.upsert_source(KnowledgeSource(
        "nextcloud:document", "nextcloud_markdown", "Remote document",
        "https://cloud.example.org/remote.php/dav/files/user/lab/input/doc.md",
        {"domain": "lab"},
    ))
    assert [s.source_id for s in knowledge_summary._domain_scoped_sources("lab")] == ["nextcloud:document"]
    assert knowledge_summary._domain_scoped_sources("other") == []
    assert knowledge_summary._domain_scoped_sources("default") == []


@pytest.mark.skipif(not os.getenv("KI_TEST_POSTGRES_DSN"), reason="KI_TEST_POSTGRES_DSN unset")
def test_contribution_postgres_atomic_replay(tmp_path, monkeypatch):
    schema = f"test_contribution_{uuid.uuid4().hex[:12]}"
    target = StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema=schema)
    try:
        central = KnowledgeStore(target)
        payload = envelope(contributor(tmp_path))
        original = KnowledgeStore.upsert_artifact

        def fail(self, artifact):
            raise RuntimeError("simulated storage failure")

        monkeypatch.setattr(KnowledgeStore, "upsert_artifact", fail)
        with pytest.raises(RuntimeError, match="storage failure"):
            central.ingest_contribution(payload)
        assert central.list_sources() == [] and central.list_records() == []
        monkeypatch.setattr(KnowledgeStore, "upsert_artifact", original)
        assert central.ingest_contribution(payload)["status"] == "accepted"
        assert KnowledgeStore(target).ingest_contribution(payload)["status"] == "replayed"
        assert len(central.list_records()) == 2
    finally:
        with connect(StoreTarget.postgres(os.environ["KI_TEST_POSTGRES_DSN"], schema="public")) as conn:
            conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')

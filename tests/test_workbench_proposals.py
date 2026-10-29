"""Proposal API contracts exercised with real migrations in an isolated child."""

from test_workbench_backend import BACKEND_SCENARIO, run_scenario


def test_workbench_proposal_backend():
    run_scenario(PROPOSAL_SCENARIO)


def test_workbench_proposal_concurrent_reservations_and_acceptance():
    run_scenario(CONCURRENCY_SCENARIO)


PROPOSAL_SCENARIO = BACKEND_SCENARIO.split("\nwith patch", 1)[0] + r'''
from datetime import timedelta
from django.db import connection
from django.utils import timezone
from ki_core.core.errors import ProviderError
from ki_knowledge.django_site import workbench_proposals as proposals
from ki_knowledge.django_site.workbench_models import WorkbenchProposal

assert apps.get_model("django_site", "WorkbenchProposal") is WorkbenchProposal
client.force_login(ordinary)
draft = request("post", "drafts", {"title": "Unicode draft", "text": "before 😀e\u0301 after"}, status=201)
endpoint = f'documents/{draft["id"]}/proposals'
etag = draft["etag"]
payload = {
    "request_id": str(uuid.uuid4()), "base_revision_id": draft["revision"]["id"],
    "start": 7, "end": 10, "exact": "😀e\u0301", "prefix": "before ", "suffix": " after",
    "instruction": "Shorten this passage",
}

def new_payload(**changes):
    return {**payload, "request_id": str(uuid.uuid4()), **changes}

def answer(request_data):
    assert not connection.in_atomic_block, "Provider call must not hold a DB transaction"
    assert len(request_data.messages) == 3
    assert "untrusted source content" in request_data.messages[0].content
    assert request_data.messages[-1].content.endswith(payload["instruction"])
    reserved = WorkbenchProposal.objects.get(request_id=current_request[0])
    assert reserved.status == "generating"
    in_flight = request("post", endpoint, current_payload[0], HTTP_IF_MATCH=etag)
    assert in_flight["status"] == "generating"
    assert request("get", endpoint)["proposals"][0]["id"] == str(reserved.pk)
    return SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"AI text","rationale":"More concise."}'))

current_request = [payload["request_id"]]
current_payload = [payload]
with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(chat=answer)) as provider:
    request("post", endpoint, payload, status=428)
    request("post", endpoint, payload, status=412, HTTP_IF_MATCH='"0"')
    for changes in (
        {"start": True}, {"end": 11}, {"exact": "bad"}, {"prefix": "bad"},
        {"suffix": "bad"}, {"end": 7}, {"instruction": ""}, {"instruction": "x"*8001},
        {"base_revision_id": str(uuid.uuid4())}, {"reference_revision_ids": ["no"]},
        {"reference_revision_ids": [str(uuid.uuid4())]*9}, {"buffer_text": "unsaved"},
        {"start": -1}, {"instruction": "\ud800"}, {"replacement_markdown": "forbidden"},
    ):
        request("post", endpoint, new_payload(**changes), status=412 if "base_revision_id" in changes else 422, HTTP_IF_MATCH=etag)
    proposal = request("post", endpoint, payload, status=201, HTTP_IF_MATCH=etag)
    assert provider.call_count == 1
    assert proposal["request_id"] == payload["request_id"]
    assert proposal["status"] == "pending" and proposal["accepted_replacement"] is None
    assert proposal["context"]["sources"][0]["text"] == payload["exact"]
    assert proposal["context"]["sources"][0]["start"] == 7
    assert proposal["context"]["sources"][0]["revision_id"] == draft["revision"]["id"]
    assert proposal["context"]["sources"][0]["unsaved"] is False
    assert proposal["prompt_version"] == proposals.PROMPT_VERSION
    assert request("get", f'documents/{draft["id"]}')["revision"]["text"] == "before 😀e\u0301 after"
    assert request("post", endpoint, payload, HTTP_IF_MATCH='"999"')["id"] == proposal["id"]
    request("post", endpoint, {**payload, "instruction": "different"}, status=409, HTTP_IF_MATCH=etag)
    assert provider.call_count == 1

detail = f'proposals/{proposal["id"]}'
assert request("get", detail) == proposal
client.force_login(other)
for method, route, data in (
    ("get", endpoint, None), ("post", endpoint, payload), ("get", detail, None),
    ("post", detail+"/accept", {"replacement_markdown": "bad"}), ("post", detail+"/reject", {}),
):
    request(method, route, data, status=404, HTTP_IF_MATCH=etag)
client.force_login(ordinary)
with patch.object(views, "active_domain", return_value=Domain.objects.get(slug="beta")):
    request("get", detail, status=404)
    request("post", detail+"/accept", {"replacement_markdown": "bad"}, status=404, HTTP_IF_MATCH=etag)
    request("post", detail+"/reject", {}, status=404)
    request("post", endpoint, payload, status=404, HTTP_IF_MATCH=etag)

csrf = Client(enforce_csrf_checks=True)
csrf.force_login(ordinary)
for route, data in ((endpoint, payload), (detail+"/accept", {"replacement_markdown": ""}), (detail+"/reject", {})):
    assert csrf.post(base+route+"?domain=alpha", data=json.dumps(data), content_type="application/json").status_code == 403

# Read-only references cannot propose, even for their owner.
reference = WorkbenchDocument.objects.create(owner=ordinary, domain=domain, kind="reference", title="Reference", capture_sha256="x")
reference_head = WorkbenchRevision.objects.create(document=reference, text="Evidence", content_sha256="x")
reference.head_revision = reference_head
reference.save(update_fields=["head_revision"])
reference_endpoint = f"documents/{reference.pk}/proposals"
request("get", reference_endpoint, status=403)
request("post", reference_endpoint, payload, status=403, HTTP_IF_MATCH='"1"')

annotation = request("post", f'documents/{draft["id"]}/annotations', {
    **{key: payload[key] for key in ("start", "end", "exact", "prefix", "suffix")},
    "revision_id": draft["revision"]["id"],
}, status=201)
count = WorkbenchRevision.objects.count()
request("post", detail+"/accept", {"replacement_markdown": "Manual"}, status=428)
request("post", detail+"/accept", {"replacement_markdown": "Manual"}, status=412, HTTP_IF_MATCH='"0"')
request("post", detail+"/accept", {}, status=422, HTTP_IF_MATCH=etag)
try:
    proposals.accept(ordinary, domain, proposal["id"], {"replacement_markdown": "😀"*(service.MAX_SOURCE_BYTES//4+1)}, etag)
except service.WorkbenchError as error:
    assert error.status == 422
else:
    raise AssertionError("Oversized UTF-8 result accepted")
assert WorkbenchRevision.objects.count() == count
accepted = request("post", detail+"/accept", {"replacement_markdown": "Manual"}, HTTP_IF_MATCH=etag)
assert accepted["document"]["version"] == 2
assert accepted["document"]["revision"]["text"] == "before Manual after"
assert accepted["document"]["revision"]["cause"] == "ai_proposal"
assert accepted["proposal"]["replacement_markdown"] == "AI text"
assert accepted["proposal"]["accepted_replacement"] == "Manual"
assert accepted["document"]["historical_annotations"][0]["id"] == annotation["id"]
assert request("post", detail+"/accept", {"replacement_markdown": "Manual"}, HTTP_IF_MATCH=etag) == accepted
request("post", detail+"/accept", {"replacement_markdown": "different"}, status=409, HTTP_IF_MATCH='"2"')
request("post", detail+"/reject", {}, status=409)
assert WorkbenchRevision.objects.count() == count+1
assert request("post", endpoint, payload, HTTP_IF_MATCH=etag)["status"] == "accepted"
frozen = WorkbenchProposal.objects.get(pk=proposal["id"])
for field in ("exact", "instruction", "replacement_markdown", "rationale", "generated_response", "prompt_version"):
    item = WorkbenchProposal.objects.get(pk=frozen.pk)
    setattr(item, field, "tampered")
    try:
        item.save()
    except ValidationError:
        pass
    else:
        raise AssertionError("Immutable provenance was changed")

# Stale bases, explicit rejection, deletion, and selected reference privacy.
def make_pending(text="😀 chosen", references=None):
    document = request("post", "drafts", {"title": "Another", "text": text}, status=201)
    data = new_payload(
        base_revision_id=document["revision"]["id"], start=0, end=1, exact=text[0],
        prefix="", suffix=text[1:],
    )
    if references is not None:
        data["reference_revision_ids"] = references
    route = f'documents/{document["id"]}/proposals'
    with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(
        chat=lambda _: SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"","rationale":"Delete selected passage."}')),
    )):
        result = request("post", route, data, status=201, HTTP_IF_MATCH=document["etag"])
    return document, data, route, result

doc2, data2, route2, p2 = make_pending(references=[str(reference_head.pk)])
assert p2["context"]["sources"][1]["text"] == "Evidence"
request("post", route2, {**data2, "request_id": str(uuid.uuid4()), "reference_revision_ids": [str(reference_head.pk)]*2}, status=422, HTTP_IF_MATCH=doc2["etag"])
foreign_reference = WorkbenchDocument.objects.create(owner=other, domain=domain, kind="reference", title="Private", capture_sha256="x")
foreign_revision = WorkbenchRevision.objects.create(document=foreign_reference, text="secret", content_sha256="x")
request("post", route2, {**data2, "request_id": str(uuid.uuid4()), "reference_revision_ids": [str(foreign_revision.pk)]}, status=404, HTTP_IF_MATCH=doc2["etag"])
saved = request("post", f'documents/{doc2["id"]}/revisions', {"base_revision_id": doc2["revision"]["id"], "text": "changed"}, status=201, HTTP_IF_MATCH=doc2["etag"])
request("post", f'proposals/{p2["id"]}/accept', {"replacement_markdown": ""}, status=412, HTTP_IF_MATCH=saved["etag"])
assert request("get", f'proposals/{p2["id"]}')["status"] == "pending"
rejected = request("post", f'proposals/{p2["id"]}/reject', {})
assert rejected["status"] == "rejected"
assert request("post", f'proposals/{p2["id"]}/reject', {}) == rejected
request("post", f'proposals/{p2["id"]}/accept', {"replacement_markdown": ""}, status=409, HTTP_IF_MATCH=saved["etag"])
doc3, data3, route3, p3 = make_pending()
deleted = request("post", f'proposals/{p3["id"]}/accept', {"replacement_markdown": ""}, HTTP_IF_MATCH=doc3["etag"])
assert deleted["document"]["revision"]["text"] == " chosen"

# Durable provider failures, strict structured output, no automatic retries.
failure_doc = request("post", "drafts", {"title": "Failure", "text": "x"}, status=201)
failure_route = f'documents/{failure_doc["id"]}/proposals'
for output in (
    "not json", '```json\n{}\n```', '{"replacement_markdown":"ok"}',
    '{"replacement_markdown":3,"rationale":"why"}',
    '{"replacement_markdown":"","rationale":""}',
    '{"replacement_markdown":"","rationale":"why","extra":"bad"}',
    '{"replacement_markdown":"","rationale":"a","rationale":"b"}',
    '{"replacement_markdown":"\\ud800","rationale":"why"}',
    '{"replacement_markdown":"\ud800","rationale":"why"}',
    None, ProviderError("secret details"), TimeoutError("secret timeout"), ValueError("configuration secret"),
):
    data = new_payload(base_revision_id=failure_doc["revision"]["id"], start=0, end=1, exact="x", prefix="", suffix="")
    def failing(_):
        if isinstance(output, Exception):
            raise output
        return SimpleNamespace(message=SimpleNamespace(content=output))
    with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(chat=failing)) as adapter:
        failed = request("post", failure_route, data, status=502, HTTP_IF_MATCH=failure_doc["etag"])
        assert failed["proposal"]["status"] == "failed"
        assert "secret" not in failed["error"]["message"]
        replayed = request("post", failure_route, data, status=502, HTTP_IF_MATCH='"0"')
        assert replayed == failed and adapter.call_count == 1
        assert request("get", f'proposals/{failed["proposal"]["id"]}')["status"] == "failed"
assert WorkbenchDocument.objects.get(pk=failure_doc["id"]).version == 1
assert all(p["status"] == "failed" for p in request("get", failure_route)["proposals"])

# Unexpected adapter exceptions persist generic failure and propagate.
unexpected = new_payload(base_revision_id=failure_doc["revision"]["id"], start=0, end=1, exact="x", prefix="", suffix="")
with patch.object(proposals.llm_provider, "chat_client", side_effect=RuntimeError("adapter secret")):
    try:
        proposals.create_proposal(service.owned_document(ordinary, domain, failure_doc["id"]), unexpected, '"1"')
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unexpected adapter error was swallowed")
failed = WorkbenchProposal.objects.get(request_id=unexpected["request_id"])
assert failed.status == "failed" and "secret" not in failed.error

# Abandoned reservations recover on explicit repeat, not GET; late workers cannot overwrite.
abandoned = new_payload(base_revision_id=failure_doc["revision"]["id"], start=0, end=1, exact="x", prefix="", suffix="")
with patch.object(proposals, "generate"):
    pending = request("post", failure_route, abandoned, status=201, HTTP_IF_MATCH='"1"')
WorkbenchProposal.objects.filter(pk=pending["id"]).update(created_at=timezone.now()-timedelta(seconds=181))
assert request("get", f'proposals/{pending["id"]}')["status"] == "generating"
with patch.object(proposals.llm_provider, "chat_client") as adapter:
    expired = request("post", failure_route, abandoned, status=502, HTTP_IF_MATCH='"0"')
    assert not adapter.called
assert expired["proposal"]["status"] == "failed"
with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(
    chat=lambda _: SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"late","rationale":"late"}')),
)):
    item = WorkbenchProposal.objects.get(pk=pending["id"])
    proposals.generate(item, service.AppConfig.from_env())
    assert item.status == "failed" and item.replacement_markdown == ""

cancel_data = {**abandoned, "request_id": str(uuid.uuid4())}
with patch.object(proposals, "generate"):
    cancelled = request("post", failure_route, cancel_data, status=201, HTTP_IF_MATCH='"1"')
assert request("post", f'proposals/{cancelled["id"]}/reject', {})["status"] == "rejected"
assert request("post", failure_route, cancel_data, HTTP_IF_MATCH='"0"')["status"] == "rejected"

# Context is exactly the selection (not the whole draft); budgets remain bounded.
large = request("post", "drafts", {"title": "Large", "text": "a"*60001}, status=201)
selection = new_payload(base_revision_id=large["revision"]["id"], start=0, end=1, exact="a", prefix="", suffix="a")
with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(
    chat=lambda _: SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"b","rationale":"Rewrite."}')),
)):
    large_proposal = request("post", f'documents/{large["id"]}/proposals', selection, status=201, HTTP_IF_MATCH='"1"')
assert large_proposal["context"]["sources"][0]["text"] == "a"
too_large_context = {**selection, "request_id": str(uuid.uuid4()), "end": 60001, "exact": "a"*60001, "suffix": ""}
request("post", f'documents/{large["id"]}/proposals', too_large_context, status=422, HTTP_IF_MATCH='"1"')

# Failed acceptance persistence rolls the whole write back.
before = WorkbenchRevision.objects.count()
with patch.object(WorkbenchRevision.objects, "create", side_effect=RuntimeError("write failed")):
    try:
        proposals.accept(ordinary, domain, large_proposal["id"], {"replacement_markdown": "b"}, '"1"')
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected failed persistence")
assert WorkbenchRevision.objects.count() == before
assert WorkbenchProposal.objects.get(pk=large_proposal["id"]).status == "pending"
assert WorkbenchDocument.objects.get(pk=large["id"]).version == 1
'''


CONCURRENCY_SCENARIO = BACKEND_SCENARIO.split("\nwith patch", 1)[0].replace(
    '"NAME": ":memory:"',
    '"NAME": str(Path(sys.argv[1]) / "concurrent.sqlite3"), "OPTIONS": {"timeout": 30}',
) + r'''
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from django.db import close_old_connections, connection
from ki_knowledge.django_site import workbench_proposals as proposals
from ki_knowledge.django_site.workbench_models import WorkbenchProposal

draft = service.create_empty_draft(ordinary, domain, {"title": "Concurrent", "text": "😀 selected"})
data = {
    "request_id": str(uuid.uuid4()), "base_revision_id": str(draft.head_revision_id),
    "start": 0, "end": 1, "exact": "😀", "prefix": "", "suffix": " selected",
    "instruction": "Rewrite",
}
start = Barrier(2)
replayed = Event()
call_lock = Lock()
calls = []
def provider_answer(_):
    assert not connection.in_atomic_block
    with call_lock:
        calls.append(True)
    assert replayed.wait(20), "Concurrent replay did not complete during generation"
    return SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"New","rationale":"Rewrite."}'))

def create():
    close_old_connections()
    try:
        doc = service.owned_document(ordinary, domain, draft.pk)
        start.wait(20)
        proposal, created = proposals.create_proposal(doc, data, '"1"')
        if not created:
            replayed.set()
        return str(proposal.pk), created
    finally:
        close_old_connections()

with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(chat=provider_answer)):
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        results = [future.result(timeout=40) for future in futures]
assert len(calls) == 1 and len({item[0] for item in results}) == 1
assert sorted(item[1] for item in results) == [False, True]
proposal_id = results[0][0]
assert WorkbenchProposal.objects.get(pk=proposal_id).status == "pending"
revision_count = WorkbenchRevision.objects.count()

def run_acceptances(entries):
    barrier = Barrier(2)
    def worker(entry):
        close_old_connections()
        try:
            barrier.wait(20)
            proposal, doc = proposals.accept(ordinary, domain, entry[0], {"replacement_markdown": entry[1]}, '"1"')
            return 200, str(proposal.accepted_revision_id)
        except service.WorkbenchError as error:
            return error.status, None
        finally:
            close_old_connections()
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, entry) for entry in entries]
        return [future.result(timeout=40) for future in futures]

results = run_acceptances([(proposal_id, "Manual"), (proposal_id, "Manual")])
assert [item[0] for item in results] == [200, 200]
assert results[0][1] == results[1][1]
assert WorkbenchRevision.objects.count() == revision_count+1
assert WorkbenchDocument.objects.get(pk=draft.pk).version == 2

def new_proposal(doc):
    payload = {**data, "request_id": str(uuid.uuid4()), "base_revision_id": str(doc.head_revision_id)}
    with patch.object(proposals.llm_provider, "chat_client", return_value=SimpleNamespace(
        chat=lambda _: SimpleNamespace(message=SimpleNamespace(content='{"replacement_markdown":"New","rationale":"Rewrite."}')),
    )):
        return proposals.create_proposal(doc, payload, '"1"')[0]

doc = service.create_empty_draft(ordinary, domain, {"title": "Different proposals", "text": "😀 selected"})
p1, p2 = new_proposal(doc), new_proposal(doc)
before = WorkbenchRevision.objects.count()
results = run_acceptances([(p1.pk, "A"), (p2.pk, "B")])
assert sorted(item[0] for item in results) == [200, 412], results
assert WorkbenchRevision.objects.count() == before+1
assert sorted(WorkbenchProposal.objects.filter(document=doc).values_list("status", flat=True)) == ["accepted", "pending"]

doc = service.create_empty_draft(ordinary, domain, {"title": "Different acceptance", "text": "😀 selected"})
p = new_proposal(doc)
before = WorkbenchRevision.objects.count()
results = run_acceptances([(p.pk, "A"), (p.pk, "B")])
assert sorted(item[0] for item in results) == [200, 409], results
assert WorkbenchRevision.objects.count() == before+1
'''

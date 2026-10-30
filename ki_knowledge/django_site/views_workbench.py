"""Session-authenticated, CSRF-protected workbench HTTP adapter."""

from functools import wraps
import json

from django.contrib.auth.decorators import login_required
from django.core.exceptions import RequestDataTooBig
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET

from .infosite_models import Domain
from .views_common import _active_semantic_domain
from . import workbench_service as service
from . import workbench_proposals as proposal_service


def active_domain(request):
    slug = _active_semantic_domain(request, heartbeat=False)
    domain = Domain.objects.filter(slug=slug).first()
    if domain is None:
        raise service.WorkbenchError("domain_unavailable", "Active domain is not registered.", 404)
    return domain


def body(request):
    if request.content_type != "application/json":
        raise service.WorkbenchError("invalid_json", "Expected an application/json object.", 422)
    try:
        raw = request.body
    except RequestDataTooBig as error:
        raise service.WorkbenchError("request_too_large", "Request body exceeds the server limit.", 413) from error
    if len(raw) > 3 * service.MAX_SOURCE_BYTES:
        raise service.WorkbenchError("request_too_large", "Request body is too large.", 413)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise service.WorkbenchError("invalid_json", "Expected a valid JSON object.", 422) from error
    if not isinstance(value, dict):
        raise service.WorkbenchError("invalid_json", "Expected a JSON object.", 422)
    return value


def api(methods, staff=False):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                return HttpResponseNotAllowed(methods)
            if not request.user.is_authenticated:
                return JsonResponse({"error": {"code": "unauthenticated", "message": "Authentication required."}}, status=401)
            try:
                if staff and not request.user.is_staff:
                    raise service.WorkbenchError("forbidden", "Staff source access is required.", 403)
                domain = active_domain(request)
                return view(request, domain, *args, **kwargs)
            except service.WorkbenchError as error:
                payload = {"code": error.code, "message": error.message}
                if error.fields:
                    payload["fields"] = error.fields
                return JsonResponse({"error": payload}, status=error.status)
        return wrapped
    return decorate


@login_required(login_url="/admin/login/")
@require_GET
@ensure_csrf_cookie
def workbench(request):
    domain = _active_semantic_domain(request, heartbeat=False)
    return render(request, "kicli_django/workbench.html", {
        "domain": domain,
        "workbench_bootstrap": {
            "domain": domain, "apiBase": reverse("workbench-api-root"),
            "canCapture": bool(request.user.is_staff), "offsetUnit": "unicode-codepoint",
        },
    })


@api(["GET"])
def api_root(request, domain):
    return JsonResponse({"domain": domain.slug, "canCapture": bool(request.user.is_staff)})


@api(["GET"], staff=True)
def source_list(request, domain):
    return JsonResponse(service.source_access.capture_inventory(domain.slug))


@api(["GET", "POST"])
def document_list(request, domain):
    if request.method == "GET":
        return JsonResponse({"documents": [
            service.document_json(item, full=False) for item in service.documents(
                request.user, domain, archived=request.GET.get("archived") == "1",
            )
        ]})
    if not request.user.is_staff:
        raise service.WorkbenchError("forbidden", "Staff source access is required.", 403)
    document, created = service.capture(request.user, domain, body(request))
    return JsonResponse(service.document_json(document), status=201 if created else 200)


@api(["GET"])
def document_detail(request, domain, document_id):
    return JsonResponse(service.document_json(service.owned_document(request.user, domain, document_id)))


@api(["POST"])
def annotation_create(request, domain, document_id):
    document = service.owned_document(request.user, domain, document_id)
    annotation = service.create_annotation(document, body(request))
    response = JsonResponse(service.annotation_json(annotation), status=201)
    response["ETag"] = f'"{annotation.version}"'
    return response


@api(["GET"])
def annotation_list(request, domain):
    return JsonResponse({"annotations": [
        service.annotation_json(item) for item in service.annotations(
            request.user, domain, archived=request.GET.get("archived") == "1",
        )
    ]})


@api(["POST"])
def document_archive(request, domain, document_id):
    item = service.set_archived(
        request.user, domain, document_id, body(request), request.headers.get("If-Match"),
    )
    return JsonResponse(service.document_json(item, full=False))


@api(["POST"])
def annotation_archive(request, domain, annotation_id):
    item = service.set_archived(
        request.user, domain, annotation_id, body(request), request.headers.get("If-Match"),
        annotation=True,
    )
    return JsonResponse(service.annotation_json(item))


@api(["PATCH"])
def annotation_patch(request, domain, annotation_id):
    annotation = service.patch_annotation(
        request.user, domain, annotation_id, body(request), request.headers.get("If-Match"),
    )
    response = JsonResponse(service.annotation_json(annotation))
    response["ETag"] = f'"{annotation.version}"'
    return response


@api(["GET", "POST"])
def relation_list(request, domain):
    if request.method == "GET":
        return JsonResponse({"relations": [
            service.relation_json(item) for item in service.relations(request.user, domain)
        ]})
    relation = service.create_relation(request.user, domain, body(request))
    return JsonResponse(service.relation_json(relation), status=201)


@api(["POST"])
def draft_create(request, domain, document_id):
    source = service.owned_document(request.user, domain, document_id)
    draft = service.create_draft(source, body(request))
    response = JsonResponse(service.document_json(draft), status=201)
    response["ETag"] = f'"{draft.version}"'
    return response


@api(["POST"])
def standalone_draft_create(request, domain):
    draft = service.create_empty_draft(request.user, domain, body(request))
    response = JsonResponse(service.document_json(draft), status=201)
    response["ETag"] = f'"{draft.version}"'
    return response


@api(["GET", "POST"])
def revision_list(request, domain, document_id):
    document = service.owned_document(request.user, domain, document_id)
    if request.method == "GET":
        return JsonResponse({"revisions": [
            service.revision_json(item) for item in document.revisions.order_by("created_at", "id")
        ]})
    document = service.save_revision(document, body(request), request.headers.get("If-Match"))
    response = JsonResponse(service.document_json(document), status=201)
    response["ETag"] = f'"{document.version}"'
    return response


@api(["GET"])
def revision_detail(request, domain, document_id, revision_id):
    document = service.owned_document(request.user, domain, document_id)
    revision = service.owned_revision(document, revision_id)
    return JsonResponse(service.document_json(document, revision=revision))


@api(["POST"])
def anchor_create(request, domain, annotation_id):
    annotation, anchor = service.reanchor(
        request.user, domain, annotation_id, body(request), request.headers.get("If-Match"),
    )
    response = JsonResponse(service.annotation_json(annotation, anchor), status=201)
    response["ETag"] = f'"{annotation.version}"'
    return response


@api(["GET"])
def provider(request, domain):
    return JsonResponse(service.provider_config())


@api(["GET", "POST"])
def conversation_list(request, domain):
    if request.method == "POST":
        conversation = service.create_conversation(request.user, domain, body(request))
        return JsonResponse(service.conversation_json(conversation), status=201)
    items = service.conversations(request.user, domain)
    if request.GET.get("document_id"):
        document_id = service.uuid_value(request.GET["document_id"], "document_id")
        service.owned_document(request.user, domain, document_id)
        items = items.filter(document_id=document_id)
    return JsonResponse({"conversations": [
        service.conversation_json(item, full=False) for item in items
    ]})


@api(["GET"])
def conversation_detail(request, domain, conversation_id):
    conversation = service.owned_conversation(request.user, domain, conversation_id)
    return JsonResponse(service.conversation_json(conversation))


@api(["POST"])
def message_create(request, domain, conversation_id):
    conversation = service.owned_conversation(request.user, domain, conversation_id)
    turn, created = service.send_message(conversation, body(request))
    result = service.message_json(turn)
    if turn.status == "failed":
        result["error"] = {"code": "provider_failed", "message": turn.error}
        return JsonResponse(result, status=502)
    return JsonResponse(result, status=201 if created else 200)


@api(["GET", "POST"])
def proposal_list(request, domain, document_id):
    document = service.owned_document(request.user, domain, document_id)
    proposal_service.require_draft(document)
    if request.method == "GET":
        return JsonResponse({"proposals": [
            proposal_service.proposal_json(item)
            for item in proposal_service.proposals(request.user, domain).filter(document=document)
        ]})
    proposal, created = proposal_service.create_proposal(
        document, body(request), request.headers.get("If-Match"),
    )
    result = proposal_service.proposal_json(proposal)
    if proposal.status == "failed":
        return JsonResponse({
            "proposal": result,
            "error": {"code": "provider_failed", "message": proposal.error},
        }, status=502)
    return JsonResponse(result, status=201 if created else 200)


@api(["GET"])
def proposal_detail(request, domain, proposal_id):
    return JsonResponse(proposal_service.proposal_json(
        proposal_service.owned_proposal(request.user, domain, proposal_id),
    ))


@api(["POST"])
def proposal_accept(request, domain, proposal_id):
    proposal, document = proposal_service.accept(
        request.user, domain, proposal_id, body(request), request.headers.get("If-Match"),
    )
    response = JsonResponse({
        "proposal": proposal_service.proposal_json(proposal), "document": service.document_json(document),
    })
    response["ETag"] = f'"{document.version}"'
    return response


@api(["POST"])
def proposal_reject(request, domain, proposal_id):
    return JsonResponse(proposal_service.proposal_json(
        proposal_service.reject(request.user, domain, proposal_id, body(request)),
    ))

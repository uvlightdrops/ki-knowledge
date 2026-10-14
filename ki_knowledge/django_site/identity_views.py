from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
from email.utils import parseaddr

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from .infosite_models import AccountIdentity, LocalIdentity, NodeIdentityCredential


MAX_BODY_BYTES = 64 * 1024
MAX_IDENTITIES = 250
NODE_ID_RE = re.compile(r"[a-z0-9][a-z0-9._:-]{0,119}\Z")
LOCAL_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:@+-]{0,99}\Z")
USERNAME_MAX_BYTES = 150
EMAIL_MAX_BYTES = 254


def _clean_text(value: object, *, field: str, max_bytes: int, required: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    try:
        byte_length = len(value.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise ValueError(f"{field} is not valid UTF-8 text") from exc
    if (required and not value) or byte_length > max_bytes:
        raise ValueError(f"{field} is empty or too long")
    if any(ord(char) < 32 or 127 <= ord(char) <= 159 for char in value):
        raise ValueError(f"{field} contains control characters")
    return value


def _normalize_node_id(value: object) -> str:
    node_id = _clean_text(value, field="node_id", max_bytes=120, required=True).lower()
    if not NODE_ID_RE.fullmatch(node_id):
        raise ValueError("node_id has an invalid format")
    return node_id


def _normalize_local_id(value: object) -> str:
    local_id = _clean_text(value, field="local_id", max_bytes=100, required=True)
    if not LOCAL_ID_RE.fullmatch(local_id):
        raise ValueError("local_id has an invalid format")
    return local_id


def _parse_identity_payload(request: HttpRequest) -> tuple[str, list[dict[str, object]]]:
    raw_length = request.META.get("CONTENT_LENGTH", "")
    if raw_length:
        try:
            content_length = int(raw_length)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid Content-Length") from exc
        if content_length < 0:
            raise ValueError("invalid Content-Length")
        if content_length > MAX_BODY_BYTES:
            raise OverflowError("request body too large")
        body = request.read(MAX_BODY_BYTES + 1)
    else:
        body = request.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise OverflowError("request body too large")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("body must be valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or set(payload) != {"node_id", "identities"}:
        raise ValueError("body must contain only node_id and identities")
    node_id = _normalize_node_id(payload["node_id"])
    raw_identities = payload["identities"]
    if not isinstance(raw_identities, list) or len(raw_identities) > MAX_IDENTITIES:
        raise ValueError("identities must be a bounded list")

    identities: list[dict[str, object]] = []
    seen_local_ids: set[str] = set()
    expected_keys = {"local_id", "username", "email", "active"}
    for raw_identity in raw_identities:
        if not isinstance(raw_identity, dict) or set(raw_identity) != expected_keys:
            raise ValueError("each identity must contain only local_id, username, email, and active")
        local_id = _normalize_local_id(raw_identity["local_id"])
        if local_id in seen_local_ids:
            raise ValueError("duplicate local_id")
        seen_local_ids.add(local_id)
        username = _clean_text(
            raw_identity["username"], field="username", max_bytes=USERNAME_MAX_BYTES, required=True
        )
        email = _clean_text(raw_identity["email"], field="email", max_bytes=EMAIL_MAX_BYTES)
        if email:
            validate_email(email)
            if parseaddr(email)[1] != email:
                raise ValueError("email has an invalid format")
        active = raw_identity["active"]
        if not isinstance(active, bool):
            raise ValueError("active must be a boolean")
        identities.append(
            {"local_id": local_id, "username": username, "email": email, "active": active}
        )
    return node_id, identities


def _bearer_token(request: HttpRequest) -> str | None:
    header = request.META.get("HTTP_AUTHORIZATION", "")
    prefix = "Bearer "
    if not header.startswith(prefix):
        return None
    token = header[len(prefix):]
    if not token or len(token) > 128 or any(char.isspace() for char in token):
        return None
    return token


def _response_status(identity: LocalIdentity) -> tuple[str, str | None]:
    if identity.linked_user_id is None:
        return "pending", None
    account_identity, _ = AccountIdentity.objects.get_or_create(user=identity.linked_user)
    if identity.local_active and identity.linked_user.is_active:
        return "active", str(account_identity.global_id)
    return "revoked", str(account_identity.global_id)


@csrf_exempt
@require_POST
def identity_sync_api(request: HttpRequest) -> JsonResponse:
    if request.content_type != "application/json":
        return JsonResponse({"error": "Content-Type must be application/json"}, status=415)
    try:
        node_id, identities = _parse_identity_payload(request)
    except OverflowError:
        return JsonResponse({"error": "request body too large"}, status=413)
    except (ValueError, ValidationError):
        return JsonResponse({"error": "invalid identity request"}, status=400)

    token = _bearer_token(request)
    if token is None:
        return JsonResponse({"error": "unauthorized"}, status=401)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    results = []
    with transaction.atomic():
        credential = (
            NodeIdentityCredential.objects.select_for_update()
            .filter(node_id=node_id, is_enabled=True)
            .first()
        )
        if credential is None or not hmac.compare_digest(credential.token_hash, token_hash):
            return JsonResponse({"error": "unauthorized"}, status=401)
        for item in identities:
            local_identity, _ = LocalIdentity.objects.update_or_create(
                node=credential,
                local_id=item["local_id"],
                defaults={
                    "username": item["username"],
                    "email": item["email"],
                    "local_active": item["active"],
                },
            )
            status, global_id = _response_status(local_identity)
            results.append(
                {"local_id": local_identity.local_id, "global_id": global_id, "status": status}
            )
    return JsonResponse({"identities": results})


def _is_active_superuser(user) -> bool:
    return bool(user.is_authenticated and user.is_active and user.is_superuser)


@login_required
@user_passes_test(_is_active_superuser)
@require_http_methods(["GET", "POST"])
def identity_admin_view(request: HttpRequest) -> HttpResponse:
    one_time_token = None
    error = None
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "issue":
                node_id = _normalize_node_id(request.POST.get("node_id"))
                one_time_token = secrets.token_urlsafe(32)
                NodeIdentityCredential.objects.update_or_create(
                    node_id=node_id,
                    defaults={
                        "token_hash": hashlib.sha256(one_time_token.encode("utf-8")).hexdigest(),
                        "is_enabled": True,
                        "revoked_at": None,
                    },
                )
            elif action == "revoke":
                credential = get_object_or_404(NodeIdentityCredential, pk=request.POST.get("credential_id"))
                credential.is_enabled = False
                credential.revoked_at = timezone.now()
                credential.save(update_fields=["is_enabled", "revoked_at"])
                messages.success(request, f"Credential for {credential.node_id} revoked.")
            elif action == "link":
                local_identity = get_object_or_404(
                    LocalIdentity.objects.select_related("linked_user"),
                    pk=request.POST.get("identity_id"),
                    linked_user__isnull=True,
                )
                user = get_object_or_404(get_user_model(), pk=request.POST.get("user_id"))
                with transaction.atomic():
                    AccountIdentity.objects.get_or_create(user=user)
                    local_identity.linked_user = user
                    local_identity.save(update_fields=["linked_user", "updated_at"])
                messages.success(request, "Local identity explicitly linked to the selected Django account.")
            else:
                raise ValueError("Unknown action")
        except (ValueError, ValidationError, TypeError):
            error = "Invalid identity action or value."

        if one_time_token is None and error is None:
            return redirect("admin-identities")

    identities = LocalIdentity.objects.select_related("node", "linked_user").all()
    rows = []
    for identity in identities:
        status, global_id = _response_status(identity)
        rows.append({"identity": identity, "status": status, "global_id": global_id})
    credentials = NodeIdentityCredential.objects.all()
    users = get_user_model().objects.order_by("pk")
    response = render(
        request,
        "kicli_django/admin_identities.html",
        {
            "credentials": credentials,
            "identity_rows": rows,
            "users": users,
            "one_time_token": one_time_token,
            "error": error,
        },
    )
    if one_time_token is not None:
        response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
        response["Pragma"] = "no-cache"
    return response

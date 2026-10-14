from __future__ import annotations

import hashlib
import json
import os
import re

import django
import pytest
from django.contrib.auth import get_user_model
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ki_knowledge.django_site.settings")
django.setup()

from ki_knowledge.django_site.infosite_models import (  # noqa: E402
    AccountIdentity,
    LocalIdentity,
    NodeIdentityCredential,
)


API_URL = "/knowledge/sync/identities/"
ADMIN_URL = "/admin-overview/identities/"


def _payload(node_id="node-a", identities=None):
    return {
        "node_id": node_id,
        "identities": identities
        if identities is not None
        else [{"local_id": "local-1", "username": "same-name", "email": "same@example.test", "active": True}],
    }


def _identity(local_id="local-1", **overrides):
    return {
        "local_id": local_id,
        "username": "same-name",
        "email": "same@example.test",
        "active": True,
        **overrides,
    }


def _credential(node_id="node-a", token="node-secret-token"):
    credential = NodeIdentityCredential.objects.create(
        node_id=node_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
    )
    return credential, token


def _sync(client, payload, token="node-secret-token", method="post"):
    return getattr(client, method)(
        API_URL,
        data=json.dumps(payload),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


@pytest.mark.django_db
def test_sync_requires_enrolled_per_node_bearer_and_exact_node_id():
    client = Client()
    assert client.post(API_URL, data=json.dumps(_payload()), content_type="application/json").status_code == 401
    assert _sync(client, _payload(), token="unknown").status_code == 401

    _credential("node-b")
    assert _sync(client, _payload(node_id="node-a")).status_code == 401
    assert LocalIdentity.objects.count() == 0

    credential, token = _credential("node-a")
    assert _sync(client, _payload(), token=token).status_code == 200
    assert credential.identities.get().node.node_id == "node-a"


@pytest.mark.django_db
def test_pending_requires_explicit_pk_link_and_never_auto_links_colliding_metadata():
    User = get_user_model()
    selected = User.objects.create_user(username="same-name", email="same@example.test")
    other = User.objects.create_user(username="different-name", email="same@example.test")
    _credential()
    client = Client()

    response = _sync(client, _payload())
    assert response.status_code == 200
    result = response.json()["identities"][0]
    assert result == {"local_id": "local-1", "global_id": None, "status": "pending"}
    assert not AccountIdentity.objects.exists()

    first_identity = LocalIdentity.objects.get()
    assert first_identity.linked_user is None
    admin = Client()
    admin.force_login(User.objects.create_superuser(username="root", email="root@example.test", password="pw"))
    page = admin.get(ADMIN_URL)
    assert page.status_code == 200
    assert f"#{selected.pk} — same-name (same@example.test)".encode() in page.content
    assert f"#{other.pk} — different-name (same@example.test)".encode() in page.content

    linked = admin.post(
        ADMIN_URL,
        {"action": "link", "identity_id": first_identity.pk, "user_id": selected.pk},
        follow=True,
    )
    assert linked.status_code == 200
    response = _sync(client, _payload())
    first_result = response.json()["identities"][0]
    assert first_result["status"] == "active"
    global_id = first_result["global_id"]
    assert global_id == str(AccountIdentity.objects.get(user=selected).global_id)

    second_credential, second_token = _credential("node-b", "another-token")
    second_payload = _payload(
        node_id="node-b", identities=[_identity("different-local", username="same-name")]
    )
    assert _sync(client, second_payload, token=second_token).json()["identities"][0]["status"] == "pending"
    second_identity = second_credential.identities.get()
    admin.post(
        ADMIN_URL,
        {"action": "link", "identity_id": second_identity.pk, "user_id": selected.pk},
    )
    second_result = _sync(client, second_payload, token=second_token).json()["identities"][0]
    assert second_result == {
        "local_id": "different-local",
        "global_id": global_id,
        "status": "active",
    }


@pytest.mark.django_db
def test_sync_is_metadata_only_and_returns_only_submitted_ids():
    _credential()
    client = Client()
    response = _sync(client, _payload(identities=[_identity("local-1"), _identity("local-2")]))
    assert response.status_code == 200
    result = response.json()
    assert [entry["local_id"] for entry in result["identities"]] == ["local-1", "local-2"]
    assert all(set(entry) == {"local_id", "global_id", "status"} for entry in result["identities"])
    assert "password" not in response.content.decode().lower()
    assert "role" not in response.content.decode().lower()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"node_id": "node-a", "identities": [], "role": "admin"},
        _payload(identities=[_identity("duplicate"), _identity("duplicate")]),
        _payload(identities=[{**_identity(), "password": "not-allowed"}]),
        _payload(identities=[_identity(active="true")]),
        _payload(node_id="../invalid"),
        _payload(identities=[_identity(username="x" * 151)]),
    ],
)
def test_rejects_malformed_identity_payloads(payload):
    _credential()
    response = _sync(Client(), payload)
    assert response.status_code == 400
    assert LocalIdentity.objects.count() == 0


@pytest.mark.django_db
def test_method_content_type_and_body_limits():
    _credential()
    client = Client()
    assert client.get(API_URL).status_code == 405
    assert client.put(API_URL).status_code == 405
    assert client.post(API_URL, data="{}", content_type="text/plain").status_code == 415
    oversized = b" " * (64 * 1024 + 1)
    assert client.post(
        API_URL,
        data=oversized,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer node-secret-token",
    ).status_code == 413


@pytest.mark.django_db
def test_local_and_global_deactivation_report_revoked_and_credentials_can_be_disabled():
    User = get_user_model()
    user = User.objects.create_user(username="linked")
    credential, token = _credential()
    identity = LocalIdentity.objects.create(
        node=credential, local_id="local-1", username="linked", email="", linked_user=user
    )
    client = Client()

    assert _sync(client, _payload(identities=[_identity(active=False)])).status_code == 200
    identity.local_active = False
    identity.save(update_fields=["local_active"])
    assert _sync(client, _payload(identities=[_identity(active=False)])).json()["identities"][0]["status"] == "revoked"
    identity.local_active = True
    identity.save(update_fields=["local_active"])
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert _sync(client, _payload()).json()["identities"][0]["status"] == "revoked"
    user.is_active = True
    user.save(update_fields=["is_active"])
    assert _sync(client, _payload()).json()["identities"][0]["status"] == "active"

    credential.is_enabled = False
    credential.save(update_fields=["is_enabled"])
    assert _sync(client, _payload(), token=token).status_code == 401


@pytest.mark.django_db
def test_admin_requires_active_superuser_csrf_and_reveals_credential_once():
    User = get_user_model()
    ordinary = User.objects.create_user(username="ordinary")
    ordinary_client = Client()
    ordinary_client.force_login(ordinary)
    assert ordinary_client.get(ADMIN_URL).status_code == 302

    inactive_superuser = User.objects.create_superuser(
        username="inactive-root", email="inactive@example.test", password="pw"
    )
    inactive_superuser.is_active = False
    inactive_superuser.save(update_fields=["is_active"])
    inactive_client = Client()
    inactive_client.force_login(inactive_superuser)
    assert inactive_client.get(ADMIN_URL).status_code == 302

    superuser = User.objects.create_superuser(username="root", email="root@example.test", password="pw")
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(superuser)
    page = csrf_client.get(ADMIN_URL)
    assert page.status_code == 200
    csrf_token = csrf_client.cookies["csrftoken"].value
    data = {"action": "issue", "node_id": "node-a"}
    assert csrf_client.post(ADMIN_URL, data).status_code == 403

    response = csrf_client.post(ADMIN_URL, data, HTTP_X_CSRFTOKEN=csrf_token)
    assert response.status_code == 200
    assert "no-store" in response["Cache-Control"]
    rendered = response.content.decode()
    assert "Copy this node token now" in rendered
    credential = NodeIdentityCredential.objects.get(node_id="node-a")
    match = re.search(r"<code>([^<]+)</code>", rendered)
    assert match
    revealed_token = match.group(1)
    assert rendered.count(revealed_token) == 1
    assert hashlib.sha256(revealed_token.encode()).hexdigest() == credential.token_hash
    assert len(credential.token_hash) == 64
    assert csrf_client.get(ADMIN_URL).status_code == 200
    assert "Copy this node token now" not in csrf_client.get(ADMIN_URL).content.decode()
    assert csrf_client.post(
        ADMIN_URL,
        {"action": "revoke", "credential_id": credential.pk},
        HTTP_X_CSRFTOKEN=csrf_client.cookies["csrftoken"].value,
    ).status_code == 302
    credential.refresh_from_db()
    assert not credential.is_enabled

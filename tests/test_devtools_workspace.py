from pathlib import Path
import json
from uuid import UUID

import pytest
from django.http import Http404
from django.test import RequestFactory, override_settings

from ki_knowledge.django_site.views_devtools import chrome_devtools_workspace


@pytest.mark.parametrize("address", ["127.0.0.1", "::1"])
def test_local_devtools_workspace(address):
    request = RequestFactory().get(
        "/.well-known/appspecific/com.chrome.devtools.json", REMOTE_ADDR=address,
    )
    with override_settings(DEBUG=True, BASE_DIR=Path("/tmp/workspace")):
        response = chrome_devtools_workspace(request)
        repeated = chrome_devtools_workspace(request)

    payload = json.loads(response.content)
    assert response.status_code == 200
    assert payload["workspace"]["root"] == "/tmp/workspace"
    assert UUID(payload["workspace"]["uuid"]).version == 5
    assert response.content == repeated.content
    assert response["Cache-Control"] == "no-store"


@pytest.mark.parametrize("debug,address", [
    (False, "127.0.0.1"),
    (True, "192.168.1.50"),
    (True, ""),
    (True, "invalid"),
])
def test_devtools_workspace_not_exposed(debug, address):
    request = RequestFactory().get("/", REMOTE_ADDR=address)
    with override_settings(DEBUG=debug):
        with pytest.raises(Http404):
            chrome_devtools_workspace(request)

from ipaddress import ip_address
from uuid import NAMESPACE_URL, uuid5

from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.http import require_GET


@require_GET
def chrome_devtools_workspace(request):
    if not settings.DEBUG:
        raise Http404
    try:
        is_local = ip_address(request.META.get("REMOTE_ADDR", "")).is_loopback
    except ValueError:
        is_local = False
    if not is_local:
        raise Http404

    root = str(settings.BASE_DIR.resolve())
    response = JsonResponse({
        "workspace": {
            "root": root,
            "uuid": str(uuid5(NAMESPACE_URL, f"ki-knowledge-workspace:{root}")),
        },
    })
    response["Cache-Control"] = "no-store"
    return response

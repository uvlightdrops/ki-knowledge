from __future__ import annotations

import json

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from requests import RequestException

from .services import (
    available_data_domains,
    domain_knowledge_summary,
    knowledge_api_browser_context,
    knowledge_api_default_url,
    normalize_semantic_domain,
    run_dashboard_task,
)
from .views_common import (
    _active_semantic_domain,
    _format_task_message,
    _int_param,
    _int_post_param,
)

_JIRA_CHAT_SESSION_KEY = "jira_support_chat_history"
_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"
_KNOWLEDGE_API_URL_SESSION_KEY = "knowledge_api_url"
_SEMANTIC_DOMAIN_SESSION_KEY = "semantic_active_domain"
_DASHBOARD_BUILDER_SESSION_KEY = "dashboard_builder_widgets"

def knowledge_api_view(request: HttpRequest):
    if request.method == "GET":
        active_domain = _active_semantic_domain(request)
        api_url = request.session.get(_KNOWLEDGE_API_URL_SESSION_KEY, "").strip() or knowledge_api_default_url()
        source_type = request.GET.get("source_type", "").strip() or None
        source_id = request.GET.get("source_id", "").strip() or None
        query = request.GET.get("q", "").strip()
        limit = _int_param(request, "limit", default=20, minimum=1, maximum=50)
        notice = request.GET.get("notice", "").strip()
        try:
            browser = knowledge_api_browser_context(
                api_url=api_url,
                source_type=source_type,
                source_id=source_id,
                query=query,
                limit=limit,
            )
        except RequestException as exc:
            browser = {
                "health": None,
                "status": "error",
                "sources": [],
                "selected_source": None,
                "selected_source_id": "",
                "search_results": [],
                "records": [],
                "artifacts": [],
                "graph": {},
            }
            error_message = str(exc)
        else:
            error_message = ""

        domain_overview = []
        seen_domains: set[str] = set()
        for domain in available_data_domains():
            if domain and domain not in seen_domains:
                seen_domains.add(domain)
                knowledge = domain_knowledge_summary(domain)
                domain_overview.append(
                    {
                        "slug": domain,
                        "display_name": domain,
                        "is_active": domain == active_domain,
                        "source_count": int(knowledge.get("sources", 0) or 0),
                        "record_count": int(knowledge.get("records", 0) or 0),
                        "artifact_count": int(knowledge.get("artifacts", 0) or 0),
                    }
                )
        if active_domain and active_domain not in seen_domains:
            knowledge = domain_knowledge_summary(active_domain)
            domain_overview.append(
                {
                    "slug": active_domain,
                    "display_name": active_domain,
                    "is_active": True,
                    "source_count": int(knowledge.get("sources", 0) or 0),
                    "record_count": int(knowledge.get("records", 0) or 0),
                    "artifact_count": int(knowledge.get("artifacts", 0) or 0),
                }
            )
        domain_overview.sort(key=lambda item: (item["display_name"].lower() != active_domain.lower(), item["display_name"].lower()))

        return render(
            request,
            "kicli_django/knowledge_api.html",
            {
                "api_url": api_url,
                "default_api_url": knowledge_api_default_url(),
                "current_path": request.get_full_path(),
                "active_domain": active_domain,
                "status": browser["status"],
                "health": browser["health"],
                "health_json": json.dumps(browser["health"], ensure_ascii=False, indent=2) if browser["health"] is not None else "",
                "error_message": error_message,
                "notice": notice,
                "domain_overview": domain_overview,
                **browser,
            },
        )

    if request.method == "POST":
        action = request.POST.get("action", "").strip()
        if action == "clear":
            request.session.pop(_KNOWLEDGE_API_URL_SESSION_KEY, None)
            request.session.modified = True
            next_url = request.POST.get("next", "").strip() or reverse("knowledge-api")
            return HttpResponseRedirect(next_url if next_url.startswith("/") else reverse("knowledge-api"))
        if action == "set":
            api_url = request.POST.get("api_url", "").strip()
            if not api_url:
                return HttpResponseBadRequest("api_url missing")
            request.session[_KNOWLEDGE_API_URL_SESSION_KEY] = api_url
            request.session.modified = True
            next_url = request.POST.get("next", "").strip() or reverse("knowledge-api")
            return HttpResponseRedirect(next_url if next_url.startswith("/") else reverse("knowledge-api"))
        if action == "generate":
            api_url = request.session.get(_KNOWLEDGE_API_URL_SESSION_KEY, "").strip() or knowledge_api_default_url()
            source_id = request.POST.get("source_id", "").strip()
            artifact_type = request.POST.get("artifact_type", "").strip()
            max_items = _int_post_param(request, "max_items", default=6, minimum=1, maximum=20)
            if not source_id or not artifact_type:
                return HttpResponseBadRequest("source_id or artifact_type missing")
            from ki_knowledge.ui.knowledge_api_client import KnowledgeAPIClient

            client = KnowledgeAPIClient(api_url)
            artifact = client.generate_artifact(
                source_id=source_id,
                artifact_type=artifact_type,
                max_items=max_items,
            )
            next_url = request.POST.get("next", "").strip() or reverse("knowledge-api")
            if not next_url.startswith("/"):
                next_url = reverse("knowledge-api")
            separator = "&" if "?" in next_url else "?"
            return HttpResponseRedirect(f"{next_url}{separator}notice={artifact['artifact_id']}")
        if action in {"kb_reset_domain", "kb_clear_artifacts_domain", "kb_reset_all"}:
            active_domain = _active_semantic_domain(request)
            target_domain = request.POST.get("target_domain", "").strip() or None
            resolved_target = normalize_semantic_domain(target_domain or active_domain)
            if action == "kb_reset_all":
                result = run_dashboard_task(action, domain=active_domain)
            else:
                result = run_dashboard_task(action, domain=active_domain, target_domain=resolved_target)
            next_url = request.POST.get("next", "").strip() or reverse("knowledge-api")
            if not next_url.startswith("/"):
                next_url = reverse("knowledge-api")
            separator = "&" if "?" in next_url else "?"
            return HttpResponseRedirect(f"{next_url}{separator}notice={_format_task_message(result)}")
        return HttpResponseBadRequest("action missing")

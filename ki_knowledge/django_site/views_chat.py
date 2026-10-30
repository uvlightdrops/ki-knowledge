"""Domain chat, legacy conversation actions and prompt backlog HTTP views."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlencode
import logging
import sqlite3

from django.http import HttpRequest, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from ki_core.core.errors import AIError
from ki_knowledge.django_site.source_workflow import import_markdown_file
from ki_knowledge.django_site.ui_dispatcher import run_dashboard_task
from ki_knowledge.integrations.sql_backend import psycopg
from ki_knowledge.llm_provider import chat_settings
from requests.exceptions import RequestException

from .chat_service import (
    ollama_available_models,
    ollama_chat_answer,
    ollama_runtime_settings,
    save_ollama_chat_markdown,
)
from .data_display import display_data_path
from .domain_registry import data_dir
from .prompt_library import (
    load_prompt_library_context,
    parse_prompt_backlog,
    parse_prompt_templates,
    prompt_batch_outputs,
    run_prompt_backlog_batch,
    save_prompt_library_documents,
)
from .support_chat import support_chat_answer, support_chat_index_status
from .views_common import _active_semantic_domain, _int_post_param


_DOMAIN_CHAT_SESSION_KEY = "domain_chat_history"


_OLLAMA_CHAT_SESSION_KEY = "ollama_chat_history"


_CHAT_ERRORS = (AIError, RuntimeError, ValueError, OSError, RequestException, sqlite3.DatabaseError)
if psycopg is not None:
    _CHAT_ERRORS += (psycopg.Error,)


@require_http_methods(["GET", "POST"])

def jira_support_chat_view(request: HttpRequest):
    if request.method == "GET":
        return _domain_chat_redirect(request)
    return support_chat_view(request)


def _domain_chat_redirect(request: HttpRequest):
    params = {
        key: request.GET[key] for key in ("domain", "notice", "source_types")
        if request.GET.get(key)
    }
    query = f"?{urlencode(params)}" if params else ""
    return HttpResponseRedirect(f"{reverse('support-chat')}{query}")


@require_http_methods(["GET", "POST"])
def support_chat_view(request: HttpRequest):
    domain = _active_semantic_domain(
        request, domain=request.POST.get("domain"), heartbeat=False,
    )
    histories = request.session.get(_DOMAIN_CHAT_SESSION_KEY, {})
    history = histories.get(domain, [])
    source_types = request.POST.get("source_types", "") if request.method == "POST" else request.GET.get("source_types", "")
    error_message = ""
    status_code = 200
    question = ""
    limit = _int_post_param(request, "limit", default=8, minimum=1, maximum=20)
    canonical_url = f"{reverse('support-chat')}?{urlencode({'domain': domain})}"
    if request.method == "POST":
        if request.POST.get("action", "").strip() == "clear":
            request.session[_DOMAIN_CHAT_SESSION_KEY] = {**histories, domain: []}
            request.session.modified = True
            return HttpResponseRedirect(canonical_url)
        question = request.POST.get("question", "").strip()
        if not question:
            return HttpResponseBadRequest("question missing")
        conversation = []
        for item in reversed(history[:6]):
            conversation.extend([
                {"role": "user", "content": item["question"]},
                {"role": "assistant", "content": item["answer"]},
            ])
        try:
            result = support_chat_answer(
                question, limit=limit, domain=domain, source_types=source_types, history=conversation,
            )
        except _CHAT_ERRORS as exc:
            logging.getLogger(__name__).warning("Domain chat failed for %s: %s", domain, exc)
            error_message = f"Chat fehlgeschlagen: {exc}"
            status_code = 503
        else:
            entry = {"question": question, **result}
            history = [entry, *history][:20]
            request.session[_DOMAIN_CHAT_SESSION_KEY] = {**histories, domain: history}
            request.session.modified = True
            return HttpResponseRedirect(canonical_url)
    index_status = {}
    provider_settings = {}
    try:
        index_status = support_chat_index_status(domain, source_types)
        provider_settings = chat_settings()
    except _CHAT_ERRORS as exc:
        logging.getLogger(__name__).warning("Domain chat status failed for %s: %s", domain, exc)
        error_message = error_message or f"Chat-Status nicht verfügbar: {exc}"
        status_code = 503
    return render(
        request,
        "kicli_django/jira_support_chat.html",
        {
            "history": history,
            "active_domain": domain,
            "source_types": source_types,
            "index_status": index_status,
            "chat_settings": provider_settings,
            "error_message": error_message,
            "question": question,
            "context_limit": limit,
            "notice": request.GET.get("notice", ""),
        },
        status=status_code,
    )


@require_http_methods(["GET", "POST"])

def prompt_backlog_view(request: HttpRequest):
    domain = _active_semantic_domain(request)
    prompt_context = load_prompt_library_context(domain)
    ollama_settings = ollama_runtime_settings()
    default_model = ollama_settings["model"]
    notice = request.GET.get("notice", "").strip()
    error_message = ""
    status_code = 200
    try:
        available_models = ollama_available_models(ollama_settings["base_url"])
    except AIError as exc:
        logging.getLogger(__name__).warning("Chat model discovery failed (%s).", type(exc).__name__)
        available_models = []
        error_message = "Modellliste nicht verfügbar. Provider-Verbindung und Konfiguration prüfen."
        status_code = 503

    if request.method == "POST":
        action = request.POST.get("action", "save").strip() or "save"
        if "backlog_content" in request.POST:
            backlog_content = request.POST.get("backlog_content", "").strip()
        else:
            backlog_content = str(prompt_context["backlog_content"]).strip()
        if "templates_content" in request.POST:
            templates_content = request.POST.get("templates_content", "").strip()
        else:
            templates_content = str(prompt_context["templates_content"]).strip()
        model = request.POST.get("model", "").strip() or default_model
        system_prompt = request.POST.get("system_prompt", "").strip()
        try:
            saved_paths = save_prompt_library_documents(
                domain=domain,
                backlog_content=backlog_content,
                templates_content=templates_content,
            )
            notice = "Prompt-Dokumente gespeichert"
            if action in {"run", "run_import", "run_import_semantic"}:
                batch_result = run_prompt_backlog_batch(
                    domain=domain,
                    backlog_content=backlog_content,
                    templates_content=templates_content,
                    model=model,
                    base_url=ollama_settings["base_url"],
                    system_prompt=system_prompt,
                    import_outputs=action in {"run_import", "run_import_semantic"},
                )
                save_prompt_library_documents(
                    domain=domain,
                    backlog_content=batch_result["updated_backlog_content"],
                    templates_content=templates_content,
                )
                notice = f"Batch verarbeitet: {batch_result['processed']} Prompt(s)"
                if batch_result["saved_files"]:
                    notice += f" · gespeichert: {len(batch_result['saved_files'])}"
                if action in {"run_import", "run_import_semantic"}:
                    notice += f" · importiert: {batch_result['imported_records']} Records"
                if action == "run_import_semantic":
                    enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                    run = run_dashboard_task("semantic_records_run", domain=domain)
                    notice += (
                        f" · semantik: queued {enqueue.get('enqueued', 0)},"
                        f" done {run.get('done', 0)}, failed {run.get('failed', 0)}"
                    )
            query = urlencode({"notice": notice})
            return HttpResponseRedirect(f"{reverse('prompt-backlog')}?{query}")
        except (AIError, OSError, RuntimeError, ValueError) as exc:
            error_message = str(exc)
            backlog_items = parse_prompt_backlog(backlog_content)
            template_names = sorted(parse_prompt_templates(templates_content).keys())
            prompt_context = {
                **prompt_context,
                "backlog_content": backlog_content,
                "templates_content": templates_content,
                "backlog_items": backlog_items,
                "open_items": [item for item in backlog_items if not bool(item["checked"])],
                "done_items": [item for item in backlog_items if bool(item["checked"])],
                "open_count": sum(1 for item in backlog_items if not bool(item["checked"])),
                "done_count": sum(1 for item in backlog_items if bool(item["checked"])),
                "template_names": template_names,
                "recent_outputs": prompt_batch_outputs(domain, limit=12),
            }
            prompt_context["saved_paths"] = saved_paths if "saved_paths" in locals() else {}

    return render(
        request,
        "kicli_django/prompt_backlog.html",
        {
            **prompt_context,
            "active_domain": domain,
            "available_models": available_models,
            "default_model": default_model,
            "chat_provider": ollama_settings["provider"],
            "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
            "notice": notice,
            "error_message": error_message,
        },
        status=status_code,
    )


@require_http_methods(["GET", "POST"])

def ollama_chat_view(request: HttpRequest):
    if request.method == "GET":
        return _domain_chat_redirect(request)
    domain = _active_semantic_domain(request)
    history = request.session.get(_OLLAMA_CHAT_SESSION_KEY, [])
    display_history = [
        {**item, "entry_index": index, "saved_path": display_data_path(item.get("saved_path", "") or None)}
        for index, item in enumerate(history) if item.get("domain") == domain
    ]
    ollama_settings = ollama_runtime_settings()
    available_models = [ollama_settings["model"]] if ollama_settings["model"] else []
    default_model = ollama_settings["model"]
    error_message = ""
    status_code = 200
    notice = request.GET.get("notice", "").strip()
    saved_path = display_data_path(request.GET.get("saved_path", "").strip() or None)
    imported_notice = request.GET.get("imported", "").strip()

    if request.method == "POST":
        action = request.POST.get("action", "ask").strip()

        if action in {"save_entry", "import_entry", "semantic_entry"}:
            entry_index_raw = request.POST.get("entry_index", "").strip()
            try:
                entry_index = int(entry_index_raw)
            except ValueError:
                return HttpResponseBadRequest("entry index missing")
            if entry_index < 0 or entry_index >= len(history):
                return HttpResponseBadRequest("entry not found")

            entry = history[entry_index]
            if entry.get("domain") and entry["domain"] != domain:
                return HttpResponseBadRequest("entry belongs to another domain")
            saved_path_value = str(entry.get("saved_path", "")).strip()
            saved_file = Path(saved_path_value) if saved_path_value else None

            if action in {"save_entry", "import_entry", "semantic_entry"} and saved_file is None:
                saved_file = save_ollama_chat_markdown(
                    domain=domain,
                    title=str(entry.get("title", "")).strip() or str(entry.get("question", ""))[:80],
                    question=str(entry.get("question", "")).strip(),
                    answer=str(entry.get("answer", "")).strip(),
                    model=str(entry.get("model", default_model)).strip() or default_model,
                    base_url=str(entry.get("base_url", ollama_settings["base_url"])).strip() or ollama_settings["base_url"],
                    system_prompt=str(entry.get("system_prompt", "")).strip(),
                    messages=[],
                )
                entry["saved_path"] = str(saved_file)
                saved_path = display_data_path(saved_file)

            if action in {"import_entry", "semantic_entry"}:
                if saved_file is None:
                    return HttpResponseBadRequest("saved file missing")
                imported = import_markdown_file(
                    saved_file,
                    source_name=saved_file.relative_to(data_dir(domain)).as_posix()
                    if saved_file.is_relative_to(data_dir(domain))
                    else saved_file.name,
                )
                entry["imported"] = f"{imported['imported']} records"
                imported_notice = entry["imported"]

            if action == "semantic_entry":
                enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                run = run_dashboard_task("semantic_records_run", domain=domain)
                entry["semantic"] = f"queued {enqueue.get('enqueued', 0)}, done {run.get('done', 0)}, failed {run.get('failed', 0)}"

            history[entry_index] = entry
            request.session[_OLLAMA_CHAT_SESSION_KEY] = history
            request.session.modified = True
            notice = "Eintrag aktualisiert"
            if entry.get("saved_path"):
                notice += f" · gespeichert: {entry['saved_path']}"
            if entry.get("imported"):
                notice += f" · importiert: {entry['imported']}"
            if entry.get("semantic"):
                notice += f" · semantik: {entry['semantic']}"
            query = urlencode({"notice": notice, "saved_path": entry.get("saved_path", ""), "imported": entry.get("imported", "")})
            return HttpResponseRedirect(f"{reverse('ollama-chat')}?{query}")

        if action == "clear":
            request.session[_OLLAMA_CHAT_SESSION_KEY] = []
            request.session.modified = True
            return HttpResponseRedirect(reverse("ollama-chat"))

        question = request.POST.get("question", "").strip()
        if not question:
            return HttpResponseBadRequest("question missing")

        model = request.POST.get("model", "").strip() or default_model
        system_prompt = request.POST.get("system_prompt", "").strip()
        title = request.POST.get("title", "").strip() or question[:80]
        history_messages: list[dict[str, str]] = []
        for item in reversed([item for item in history if item.get("domain") == domain][:6]):
            user_question = str(item.get("question", "")).strip()
            user_answer = str(item.get("answer", "")).strip()
            if user_question:
                history_messages.append({"role": "user", "content": user_question})
            if user_answer:
                history_messages.append({"role": "assistant", "content": user_answer})
        try:
            result = ollama_chat_answer(
                question,
                history=history_messages,
                model=model,
                base_url=ollama_settings["base_url"],
                system_prompt=system_prompt,
            )
            entry = {
                "domain": domain,
                "title": title,
                "question": result["question"],
                "answer": result["answer"],
                "model": result["model"],
                "base_url": result["base_url"],
                "system_prompt": system_prompt,
                "saved_path": "",
                "imported": "",
                "semantic": "",
            }
            try:
                if action in {"save", "save_import", "save_import_semantic"}:
                    saved_file = save_ollama_chat_markdown(
                        domain=domain,
                        title=title,
                        question=result["question"],
                        answer=result["answer"],
                        model=result["model"],
                        base_url=result["base_url"],
                        system_prompt=system_prompt,
                        messages=result["messages"],
                    )
                    entry["saved_path"] = str(saved_file)
                    saved_path = display_data_path(saved_file)
                    if action in {"save_import", "save_import_semantic"}:
                        imported = import_markdown_file(
                            saved_file,
                            source_name=saved_file.relative_to(data_dir(domain)).as_posix()
                            if saved_file.is_relative_to(data_dir(domain))
                            else saved_file.name,
                        )
                        entry["imported"] = f"{imported['imported']} records"
                        imported_notice = entry["imported"]
                        if action == "save_import_semantic":
                            enqueue = run_dashboard_task("semantic_records_enqueue", domain=domain)
                            run = run_dashboard_task("semantic_records_run", domain=domain)
                            entry["semantic"] = f"queued {enqueue.get('enqueued', 0)}, done {run.get('done', 0)}, failed {run.get('failed', 0)}"
            except (OSError, ValueError) as exc:
                error_message = str(exc)
                history = [entry, *history][:20]
                display_history = [
                    {**item, "entry_index": index, "saved_path": display_data_path(item.get("saved_path", "") or None)}
                    for index, item in enumerate(history) if item.get("domain") == domain
                ]
                request.session[_OLLAMA_CHAT_SESSION_KEY] = history
                request.session.modified = True
                return render(
                    request,
                    "kicli_django/ollama_chat.html",
                    {
                        "history": display_history,
                        "active_domain": domain,
                        "available_models": available_models,
                        "default_model": default_model,
                        "chat_provider": ollama_settings["provider"],
                        "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
                        "notice": notice,
                        "saved_path": saved_path,
                        "imported_notice": imported_notice,
                        "error_message": error_message,
                    },
                )
            history = [entry, *history][:20]
            display_history = [
                {**item, "entry_index": index, "saved_path": display_data_path(item.get("saved_path", "") or None)}
                for index, item in enumerate(history) if item.get("domain") == domain
            ]
            request.session[_OLLAMA_CHAT_SESSION_KEY] = history
            request.session.modified = True
            notice = "Antwort erzeugt"
            if entry["saved_path"]:
                notice += f" · gespeichert: {display_data_path(entry['saved_path'])}"
            if entry["imported"]:
                notice += f" · importiert: {entry['imported']}"
            if entry["semantic"]:
                notice += f" · semantik: {entry['semantic']}"
            query = urlencode(
                {
                    "notice": notice,
                    "saved_path": entry["saved_path"],
                    "imported": entry["imported"],
                }
            )
            return HttpResponseRedirect(f"{reverse('ollama-chat')}?{query}")
        except _CHAT_ERRORS as exc:
            logging.getLogger(__name__).warning("Legacy chat failed (%s).", type(exc).__name__)
            error_message = "Chat fehlgeschlagen. Provider-Verbindung und Konfiguration prüfen."
            status_code = 503

    return render(
        request,
        "kicli_django/ollama_chat.html",
        {
    "history": display_history,
            "active_domain": domain,
            "available_models": available_models,
            "default_model": default_model,
            "chat_provider": ollama_settings["provider"],
            "default_system_prompt": f"Du bist ein hilfreicher Assistent fuer die Domain {domain}. Antworte klar und strukturiert.",
            "notice": notice,
            "saved_path": saved_path,
            "imported_notice": imported_notice,
            "error_message": error_message,
        },
        status=status_code,
    )

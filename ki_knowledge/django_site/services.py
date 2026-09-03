from __future__ import annotations

import csv
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import markdown
from django.conf import settings

import networkx as nx
from ki_core.adapters.ollama import OllamaClient
from ki_core.config import Config
from ki_core.core.models import ChatRequest, Message, Role
from ki_knowledge.api.app import _field_embedding_backend, _get_components, _semantic_model_id
from ki_knowledge.integrations.embeddings import OllamaEmbeddingProvider, TFIDFEmbeddingProvider
from ki_knowledge.integrations.jira_cache import DomainTerm, JiraIssueCache
from ki_knowledge.integrations.jira_csv import JiraCSVImporter
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph
from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.integrations.semantic_terms import SemanticEnrichmentService, SemanticTermStore
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator
from ki_knowledge.integrations.pdf_ingest import extract_text_from_pdf as pdf_extract_text
from ki_knowledge.integrations.pdf_paths import pdf_relative_source_path, pdf_source_id

from ki_knowledge.ui.knowledge_api_client import (
    KnowledgeAPIClient,
    default_knowledge_api_url,
    discover_markdown_files,
    default_markdown_directory,
)
from ki_knowledge.ui.knowledge_graph_viz import create_pyvis_network, graph_dict_to_networkx, graph_statistics
from ki_knowledge.ui.knowledge_workspace import build_markdown_tree
from ki_knowledge.config_runtime import (
    knowledge_data_root,
    knowledge_jira_root,
    knowledge_markdown_root,
    knowledge_ontology_root,
    knowledge_pdf_root,
)


@dataclass
class ImportResult:
    imported: int = 0
    source_ids: list[str] = None


def data_root() -> Path:
    return knowledge_data_root(Config.from_env())


def markdown_type_root() -> Path:
    return knowledge_markdown_root(Config.from_env())


def jira_type_root() -> Path:
    return knowledge_jira_root(Config.from_env())


def ontology_type_root() -> Path:
    return knowledge_ontology_root(Config.from_env())


def pdf_type_root() -> Path:
    return knowledge_pdf_root(Config.from_env())


def _resolve_existing_domain_dir(base: Path, normalized_domain: str) -> Path:
    if base.exists() and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and normalize_semantic_domain(child.name) == normalized_domain:
                return child
    return base / normalized_domain


def _detect_domain_label(base: Path, normalized_domain: str) -> str:
    if base.exists() and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and normalize_semantic_domain(child.name) == normalized_domain:
                return child.name
    return normalized_domain


def _resolve_domain_file(domain_dir: Path, preferred: str, legacy: str) -> Path:
    preferred_path = domain_dir / preferred
    legacy_path = domain_dir / legacy
    if legacy_path.exists() and not preferred_path.exists():
        preferred_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_path.rename(preferred_path)
    return preferred_path


def domain_markdown_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(markdown_type_root(), resolved)


def domain_jira_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(jira_type_root(), resolved)


def domain_ontology_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return _resolve_existing_domain_dir(ontology_type_root(), resolved)


def domain_pdf_dir(domain: str | None = None) -> Path:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    pdf_dir = _resolve_existing_domain_dir(pdf_type_root(), resolved)
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True, exist_ok=True)
    return pdf_dir


def discover_pdf_files(root: Path) -> list[Path]:
    if not root.exists():
        return []

    found: list[Path] = []
    seen: set[str] = set()

    def walk(current: Path) -> None:
        try:
            resolved_current = current.resolve(strict=False)
        except OSError:
            resolved_current = current
        key = str(resolved_current)
        if key in seen:
            return
        seen.add(key)

        if current.is_file():
            if current.suffix.lower() == ".pdf":
                found.append(current)
            return

        if not current.is_dir():
            return

        try:
            children = sorted(current.iterdir(), key=lambda item: item.name)
        except OSError:
            return

        for child in children:
            walk(child)

    walk(root)
    return sorted({path.resolve(strict=False) for path in found}, key=lambda item: str(item))


def data_dir(domain: str | None = None) -> Path:
    return domain_markdown_dir(domain)


def display_data_path(value: str | Path | None) -> str:
    if value is None:
        return "-"
    path = Path(value).expanduser()
    root = data_root().expanduser()
    home = Path.home().expanduser()
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError):
        resolved = path
    try:
        relative = resolved.relative_to(root.resolve())
        return "DATADIR" if not relative.parts else f"DATADIR/{relative.as_posix()}"
    except (OSError, RuntimeError, ValueError):
        pass
    try:
        relative = resolved.relative_to(home.resolve())
        return "~" if not relative.parts else f"~/{relative.as_posix()}"
    except (OSError, RuntimeError, ValueError):
        return str(path)


def display_source_ref(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return "-"
    if ":" not in text:
        return display_data_path(text)
    prefix, remainder = text.split(":", 1)
    remainder = remainder.strip()
    if not remainder:
        return f"{prefix}:"
    return f"{prefix}:{display_data_path(remainder)}"


def artifact_content_preview(artifact_type: str, content: str, *, limit: int = 240) -> str:
    text = (content or "").strip()
    if not text:
        return ""
    if artifact_type == "summary_note":
        try:
            payload = json.loads(text)
        except ValueError:
            payload = {}
        sections = payload.get("sections") if isinstance(payload, dict) else []
        if isinstance(sections, list) and sections:
            first = sections[0] if isinstance(sections[0], dict) else {}
            title = str(first.get("title", "")).strip()
            summary = str(first.get("summary", "")).strip()
            snippet = f"{title}: {summary}" if title else summary
            if snippet:
                return snippet[:limit]
        if isinstance(payload, dict):
            raw = payload.get("title") or payload.get("content") or ""
            if raw:
                return str(raw)[:limit]
    normalized = " ".join(text.split())
    return normalized[:limit]


def ollama_runtime_settings() -> dict[str, str]:
    config = Config.from_env()
    return {
        "base_url": (config.ollama_base_url or "http://localhost:11434").strip(),
        "model": (config.ollama_model or "llama3.2").strip(),
    }


def ollama_chat_dir(domain: str | None = None) -> Path:
    return data_dir(domain) / "ollama-chat"


def ollama_available_models(base_url: str | None = None) -> list[str]:
    config = Config.from_env()
    resolved_base_url = (base_url or config.ollama_base_url or "http://localhost:11434").strip()
    try:
        return OllamaClient.get_available_models(resolved_base_url)
    except Exception:
        return []


def ollama_chat_answer(
    question: str,
    *,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
    base_url: str | None = None,
    system_prompt: str | None = None,
) -> dict[str, Any]:
    prompt = (question or "").strip()
    if not prompt:
        raise ValueError("question missing")

    config = Config.from_env()
    provider = OllamaClient(
        base_url=(base_url or config.ollama_base_url or "http://localhost:11434").strip(),
        model=(model or config.ollama_model or "llama3.2").strip(),
    )
    messages: list[dict[str, str]] = []
    if system_prompt and system_prompt.strip():
        messages.append({"role": "system", "content": system_prompt.strip()})
    for entry in history or []:
        role = str(entry.get("role", "")).strip()
        content = str(entry.get("content", "")).strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": prompt})
    response = provider.chat(
        ChatRequest(
            messages=[Message(role=Role(entry["role"]), content=entry["content"]) for entry in messages]
        )
    )
    return {
        "question": prompt,
        "answer": response.message.content,
        "model": response.model,
        "base_url": provider.base_url,
        "messages": [*messages, {"role": "assistant", "content": response.message.content}],
    }


def save_ollama_chat_markdown(
    *,
    domain: str | None = None,
    title: str,
    question: str,
    answer: str,
    model: str,
    base_url: str,
    system_prompt: str = "",
    messages: list[dict[str, str]] | None = None,
) -> Path:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    target_dir = ollama_chat_dir(resolved_domain)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", title.strip().lower()).strip("-._") or "chat"
    path = target_dir / f"{timestamp}-{slug}.md"
    lines = [
        f"# {title.strip() or 'Chat'}",
        "",
        f"- domain: {resolved_domain}",
        f"- model: {model}",
        f"- base_url: {base_url}",
        f"- saved_at: {datetime.now(timezone.utc).isoformat()}",
        "",
    ]
    if system_prompt.strip():
        lines.extend(["## System prompt", "", system_prompt.strip(), ""])
    lines.extend(["## User", "", question.strip(), "", "## Assistant", "", answer.strip(), ""])
    if messages:
        lines.extend(["## Transcript", ""])
        for message in messages:
            role = str(message.get("role", "")).strip().title() or "Message"
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            lines.extend([f"### {role}", "", content, ""])
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def prompt_library_dir(domain: str | None = None) -> Path:
    return data_dir(domain) / "prompt-library"


def prompt_backlog_path(domain: str | None = None) -> Path:
    return prompt_library_dir(domain) / "prompt_backlog.md"


def prompt_templates_path(domain: str | None = None) -> Path:
    return prompt_library_dir(domain) / "prompt_templates.md"


def prompt_batch_dir(domain: str | None = None) -> Path:
    return prompt_library_dir(domain) / "runs"


def _default_prompt_backlog_markdown(domain: str) -> str:
    return "\n".join(
        [
            "# Prompt backlog",
            "",
            f"Domain: `{domain}`",
            "",
            "Offene Batch-Fragen als Markdown-Checkliste notieren.",
            "Syntax:",
            "- `- [ ] Frage ohne Vorlage`",
            "- `- [ ] template-name :: Frage mit Vorlage`",
            "",
            "## Queue",
            "",
            "- [ ] default :: Fasse die wichtigsten offenen Themen dieser Domain zusammen.",
            "- [ ] condensation :: Welche Begriffe sollten spaeter in Dokumentation kondensiert werden?",
            "",
            "## Notes",
            "",
            "- Alles, was auf `[ ]` steht, wird beim Batch-Lauf verarbeitet.",
            "- Verarbeitete Zeilen werden auf `[x]` gesetzt.",
            "",
        ]
    )


def _default_prompt_templates_markdown(domain: str) -> str:
    return "\n".join(
        [
            "# Prompt templates",
            "",
            f"Domain: `{domain}`",
            "",
            "Jede Vorlage beginnt mit `## template-name`.",
            "Verfuegbare Platzhalter: `{{domain}}`, `{{question}}`, `{{template}}`.",
            "",
            "## default",
            "",
            "Du bist ein hilfreicher Assistent fuer die Domain {{domain}}.",
            "Arbeite die folgende Frage klar, strukturiert und praxisnah aus.",
            "",
            "Frage:",
            "{{question}}",
            "",
            "## condensation",
            "",
            "Du hilfst dabei, spaetere Dokumentation fuer die Domain {{domain}} vorzubereiten.",
            "Beantworte die Frage so, dass Canonical Terms, Relationen, Risiken und offene Annahmen klar werden.",
            "",
            "Frage:",
            "{{question}}",
            "",
        ]
    )


def _read_or_initialize_markdown(path: Path, default_content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(default_content.strip() + "\n", encoding="utf-8")
    return path.read_text(encoding="utf-8")


def save_prompt_library_documents(*, domain: str | None = None, backlog_content: str, templates_content: str) -> dict[str, str]:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    backlog_file = prompt_backlog_path(resolved_domain)
    templates_file = prompt_templates_path(resolved_domain)
    backlog_file.parent.mkdir(parents=True, exist_ok=True)
    backlog_file.write_text(backlog_content.strip() + "\n", encoding="utf-8")
    templates_file.write_text(templates_content.strip() + "\n", encoding="utf-8")
    return {"backlog_path": str(backlog_file), "templates_path": str(templates_file)}


def _normalize_prompt_template_name(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", (value or "").strip().lower()).strip("-._")
    return normalized or "default"


def parse_prompt_templates(markdown_text: str) -> dict[str, str]:
    templates: dict[str, str] = {}
    current_name = ""
    current_lines: list[str] = []
    for raw_line in markdown_text.splitlines():
        heading = re.match(r"^\s*##\s+(.+?)\s*$", raw_line)
        if heading:
            if current_name:
                templates[current_name] = "\n".join(current_lines).strip()
            current_name = _normalize_prompt_template_name(heading.group(1))
            current_lines = []
            continue
        if current_name:
            current_lines.append(raw_line)
    if current_name:
        templates[current_name] = "\n".join(current_lines).strip()
    if "default" not in templates or not templates["default"].strip():
        templates["default"] = (
            "Du bist ein hilfreicher Assistent fuer die Domain {{domain}}.\n"
            "Arbeite die folgende Frage klar und strukturiert aus.\n\n"
            "Frage:\n{{question}}"
        )
    return templates


def parse_prompt_backlog(markdown_text: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, raw_line in enumerate(markdown_text.splitlines()):
        match = re.match(r"^\s*[-*]\s+\[( |x|X)\]\s+(.*\S)\s*$", raw_line)
        if not match:
            continue
        checked = match.group(1).lower() == "x"
        body = match.group(2).strip()
        template_name = "default"
        question = body
        if "::" in body:
            template_candidate, question_candidate = body.split("::", 1)
            normalized_template = _normalize_prompt_template_name(template_candidate)
            if normalized_template:
                template_name = normalized_template
                question = question_candidate.strip() or body
        items.append(
            {
                "line_index": index,
                "line_number": index + 1,
                "checked": checked,
                "template": template_name,
                "question": question.strip(),
                "raw": body,
            }
        )
    return items


def _render_prompt_template(template_text: str, *, domain: str, question: str, template_name: str) -> str:
    rendered = (template_text or "").strip()
    if not rendered:
        rendered = (
            "Du bist ein hilfreicher Assistent fuer die Domain {{domain}}.\n"
            "Arbeite die folgende Frage klar und strukturiert aus.\n\n"
            "Frage:\n{{question}}"
        )
    return (
        rendered.replace("{{domain}}", domain)
        .replace("{{question}}", question)
        .replace("{{template}}", template_name)
        .strip()
    )


def load_prompt_library_context(domain: str | None = None) -> dict[str, Any]:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    backlog_content = _read_or_initialize_markdown(
        prompt_backlog_path(resolved_domain),
        _default_prompt_backlog_markdown(resolved_domain),
    )
    templates_content = _read_or_initialize_markdown(
        prompt_templates_path(resolved_domain),
        _default_prompt_templates_markdown(resolved_domain),
    )
    backlog_items = parse_prompt_backlog(backlog_content)
    templates = parse_prompt_templates(templates_content)
    open_items = [item for item in backlog_items if not bool(item["checked"])]
    done_items = [item for item in backlog_items if bool(item["checked"])]
    recent_outputs = prompt_batch_outputs(resolved_domain, limit=12)
    return {
        "domain": resolved_domain,
        "backlog_path": display_data_path(prompt_backlog_path(resolved_domain)),
        "templates_path": display_data_path(prompt_templates_path(resolved_domain)),
        "runs_dir": display_data_path(prompt_batch_dir(resolved_domain)),
        "backlog_content": backlog_content,
        "templates_content": templates_content,
        "backlog_items": backlog_items,
        "template_names": sorted(templates.keys()),
        "open_items": open_items,
        "done_items": done_items,
        "open_count": len(open_items),
        "done_count": len(done_items),
        "recent_outputs": recent_outputs,
    }


def save_prompt_batch_markdown(
    *,
    domain: str | None = None,
    title: str,
    template_name: str,
    question: str,
    rendered_prompt: str,
    answer: str,
    model: str,
    base_url: str,
) -> Path:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    target_dir = prompt_batch_dir(resolved_domain)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", title.strip().lower()).strip("-._") or "prompt"
    path = target_dir / f"{timestamp}-{slug}.md"
    lines = [
        f"# {title.strip() or 'Prompt'}",
        "",
        f"- domain: {resolved_domain}",
        f"- template: {template_name}",
        f"- model: {model}",
        f"- base_url: {base_url}",
        f"- executed_at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Original question",
        "",
        question.strip(),
        "",
        "## Rendered prompt",
        "",
        rendered_prompt.strip(),
        "",
        "## Assistant",
        "",
        answer.strip(),
        "",
    ]
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return path


def prompt_batch_outputs(domain: str | None = None, *, limit: int = 12) -> list[dict[str, str]]:
    root = prompt_batch_dir(domain)
    if not root.exists() or not root.is_dir():
        return []
    files = sorted(
        discover_markdown_files(root),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    workspace_root = data_dir(domain)
    return [
        {"name": path.relative_to(workspace_root).as_posix(), "path": str(path)}
        for path in files[:limit]
    ]


def run_prompt_backlog_batch(
    *,
    domain: str | None = None,
    backlog_content: str,
    templates_content: str,
    model: str | None = None,
    base_url: str | None = None,
    system_prompt: str = "",
    import_outputs: bool = False,
) -> dict[str, Any]:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    templates = parse_prompt_templates(templates_content)
    items = parse_prompt_backlog(backlog_content)
    open_items = [item for item in items if not bool(item["checked"])]
    if not open_items:
        return {
            "processed": 0,
            "saved_files": [],
            "imported_records": 0,
            "updated_backlog_content": backlog_content.strip() + "\n",
            "results": [],
        }

    backlog_lines = backlog_content.splitlines()
    saved_files: list[str] = []
    imported_records = 0
    results: list[dict[str, Any]] = []
    for item in open_items:
        question = str(item["question"]).strip()
        if not question:
            continue
        template_name = _normalize_prompt_template_name(str(item["template"]))
        template_text = templates.get(template_name) or templates["default"]
        rendered_prompt = _render_prompt_template(
            template_text,
            domain=resolved_domain,
            question=question,
            template_name=template_name,
        )
        answer = ollama_chat_answer(
            rendered_prompt,
            history=None,
            model=model,
            base_url=base_url,
            system_prompt=system_prompt,
        )
        saved_file = save_prompt_batch_markdown(
            domain=resolved_domain,
            title=question[:80],
            template_name=template_name,
            question=question,
            rendered_prompt=rendered_prompt,
            answer=str(answer["answer"]),
            model=str(answer["model"]),
            base_url=str(answer["base_url"]),
        )
        saved_files.append(str(saved_file))
        imported = None
        if import_outputs:
            imported = import_markdown_file(
                saved_file,
                source_name=saved_file.relative_to(data_dir(resolved_domain)).as_posix()
                if saved_file.is_relative_to(data_dir(resolved_domain))
                else saved_file.name,
            )
            imported_records += int(imported.get("imported", 0) or 0)
        backlog_lines[item["line_index"]] = re.sub(r"\[( )\]", "[x]", backlog_lines[item["line_index"]], count=1)
        results.append(
            {
                "question": question,
                "template": template_name,
                "saved_path": str(saved_file),
                "imported": 0 if imported is None else int(imported.get("imported", 0) or 0),
            }
        )
    updated_backlog_content = "\n".join(backlog_lines).strip() + "\n"
    return {
        "processed": len(results),
        "saved_files": saved_files,
        "imported_records": imported_records,
        "updated_backlog_content": updated_backlog_content,
        "results": results,
    }


def knowledge_api_default_url() -> str:
    return default_knowledge_api_url()


def knowledge_api_health(api_url: str | None = None) -> dict[str, Any]:
    client = KnowledgeAPIClient((api_url or knowledge_api_default_url()).strip())
    return client.health()


def knowledge_api_browser_context(
    *,
    api_url: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    client = KnowledgeAPIClient((api_url or knowledge_api_default_url()).strip())
    health = client.health()
    normalized_source_type = None if not source_type or source_type == "(all)" else source_type
    sources = client.list_sources(source_type=normalized_source_type)
    selected_source = None
    selected_source_id = (source_id or "").strip()
    if not selected_source_id and sources:
        selected_source_id = sources[0]["source_id"]
    if selected_source_id:
        selected_source = next((source for source in sources if source["source_id"] == selected_source_id), None)
        if selected_source is None:
            selected_source = client.get_source(selected_source_id)

    search_results = client.search_blocks(query, limit=limit) if query.strip() else []
    records = client.list_records(source_id=selected_source_id or None, limit=limit) if selected_source_id else []
    artifacts = client.list_artifacts(source_id=selected_source_id or None) if selected_source_id else []
    graph = client.get_source_graph(selected_source_id, limit=min(max(limit, 1) * 10, 400)) if selected_source_id else {}
    return {
        "client": client,
        "health": health,
        "status": str(health.get("status", "ok")),
        "sources": sources,
        "selected_source": selected_source,
        "selected_source_id": selected_source_id,
        "search_results": search_results,
        "records": records,
        "artifacts": artifacts,
        "graph": graph,
        "source_type": normalized_source_type or "(all)",
        "query": query,
        "limit": limit,
    }


def available_data_domains() -> list[str]:
    domains: set[str] = set()
    for base in (markdown_type_root(), jira_type_root(), ontology_type_root(), pdf_type_root()):
        if not base.exists() or not base.is_dir():
            continue
        for child in base.iterdir():
            if child.is_dir():
                domains.add(normalize_semantic_domain(child.name))
    legacy_root = domain_storage_root()
    if legacy_root.exists() and legacy_root.is_dir():
        for child in legacy_root.iterdir():
            if child.is_dir():
                domains.add(normalize_semantic_domain(child.name))
    result = sorted(item for item in domains if item)
    _register_domains(result)
    return result


def _register_domains(slugs: list[str]) -> None:
    """Backfill the shared Domain registry with slugs found by directory scans.

    Imported lazily and guarded: this service layer is also used by the
    plain FastAPI app (tests/test_jira_api.py) without Django settings
    configured at all, so any failure to reach the Django app registry
    (ImproperlyConfigured/AppRegistryNotReady) is treated as "registry not
    available here" rather than a hard error - domains still get registered
    normally whenever this runs inside the Django app.
    """

    try:
        from django.apps import apps as django_apps

        if not django_apps.ready:
            return
        from ki_knowledge.django_site.infosite_models import ensure_domain_registered
    except Exception:
        return

    for slug in slugs:
        ensure_domain_registered(slug)


def default_semantic_domain() -> str:
    env_override = os.getenv("KNOWLEDGE_DEFAULT_DOMAIN", "").strip()
    if env_override:
        return normalize_semantic_domain(env_override)
    domains = available_data_domains()
    return domains[0] if domains else "default"


def normalize_semantic_domain(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "default"
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-_")
    return normalized or "default"


def domain_storage_root() -> Path:
    raw = os.getenv("KNOWLEDGE_JIRA_ROOT", "").strip()
    if raw:
        return Path(raw).expanduser()
    return jira_type_root()


def domain_db_paths(domain: str | None = None) -> dict[str, Path]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_dir = _resolve_existing_domain_dir(domain_storage_root(), resolved)
    return {
        "domain": domain_dir,
        "cache_db": _resolve_domain_file(domain_dir, "cache.sqlite", "jira_cache.sqlite"),
        "graph_db": _resolve_domain_file(domain_dir, "graph.sqlite", "jira_graph.sqlite"),
        "cypher_path": _resolve_domain_file(domain_dir, "graph.cypher", "jira_graph.cypher"),
    }


def semantic_domains() -> list[str]:
    domains = set(available_data_domains())
    domains.add(default_semantic_domain())
    root = domain_storage_root()
    if root.exists() and root.is_dir():
        for child in root.iterdir():
            if child.is_dir():
                domains.add(normalize_semantic_domain(child.name))
    return sorted(domains)


def create_semantic_domain(domain: str | None) -> dict[str, Any]:
    raw = (domain or "").strip()
    if not raw:
        raise ValueError("domain missing")
    resolved = normalize_semantic_domain(raw)
    if resolved == "default" and raw.lower() != "default":
        raise ValueError("invalid domain name")
    md_dir = domain_markdown_dir(resolved)
    jira_dir = domain_jira_dir(resolved)
    owl_dir = domain_ontology_dir(resolved)
    prompt_dir = prompt_library_dir(resolved)
    md_dir.mkdir(parents=True, exist_ok=True)
    jira_dir.mkdir(parents=True, exist_ok=True)
    owl_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    _register_domains([resolved])
    return {
        "domain": resolved,
        "markdown_dir": str(md_dir),
        "jira_dir": str(jira_dir),
        "ontology_dir": str(owl_dir),
        "prompt_dir": str(prompt_dir),
        "created": True,
    }


def semantic_domain_states() -> list[dict[str, Any]]:
    states: list[dict[str, Any]] = []
    for domain in semantic_domains():
        paths = domain_db_paths(domain)
        markdown_dir = domain_markdown_dir(domain)
        jira_dir = domain_jira_dir(domain)
        ontology_dir = domain_ontology_dir(domain)
        pdf_dir = domain_pdf_dir(domain)
        md_label = _detect_domain_label(markdown_type_root(), domain)
        jira_label = _detect_domain_label(jira_type_root(), domain)
        owl_label = _detect_domain_label(ontology_type_root(), domain)
        pdf_label = _detect_domain_label(pdf_type_root(), domain)
        cache_path = paths["cache_db"]
        graph_path = paths["graph_db"]
        csv_path = jira_csv_path(domain)
        markdown_files = len(discover_markdown_files(markdown_dir))
        jira_csv_files = len(sorted(path for path in jira_dir.glob("*.csv") if jira_dir.exists() and jira_dir.is_dir() and path.is_file()))
        ontology_files = len(discover_ontology_files(ontology_dir))
        pdf_files = len(discover_pdf_files(pdf_dir))
        pdf_job_stats = get_pdf_job_stats(domain)
        cache_exists = cache_path.exists()
        graph_exists = graph_path.exists()
        issue_count = 0
        totals = {"terms": 0, "facts": 0, "relations": 0, "candidates": 0, "record_term_links": 0}
        if cache_exists:
            try:
                issue_count = JiraIssueCache(str(cache_path)).issue_count()
            except sqlite3.Error:
                issue_count = 0
            try:
                totals = SemanticTermStore(str(cache_path)).monitoring_snapshot(recent_limit=1).get("totals", totals)
            except sqlite3.Error:
                totals = totals
        states.append(
            {
                "domain": domain,
                "domain_label": md_label if md_label != domain else (jira_label if jira_label != domain else (owl_label if owl_label != domain else pdf_label)),
                "cache_db": str(cache_path),
                "graph_db": str(graph_path),
                "markdown_dir": str(markdown_dir),
                "jira_dir": str(jira_dir),
                "ontology_dir": str(ontology_dir),
                "pdf_dir": str(pdf_dir),
                "csv_path": csv_path,
                "markdown_files": markdown_files,
                "jira_csv_files": jira_csv_files,
                "ontology_files": ontology_files,
                "pdf_files": pdf_files,
                "has_md_source": markdown_files > 0 or markdown_dir.exists(),
                "has_jira_source": bool(csv_path),
                "has_owl_source": ontology_files > 0,
                "has_pdf_source": pdf_files > 0,
                "pdf_jobs": pdf_job_stats,
                "pdf_jobs_active": pdf_job_stats.get("processing", 0) > 0,
                "cache_exists": cache_exists,
                "graph_exists": graph_exists,
                "issues": issue_count,
                "terms": int(totals.get("terms", 0) or 0),
                "facts": int(totals.get("facts", 0) or 0),
            }
        )
    return states


def delete_semantic_domain(domain: str | None) -> dict[str, Any]:
    resolved = normalize_semantic_domain(domain)
    paths = domain_db_paths(resolved)
    if not paths["cache_db"].exists() and not paths["graph_db"].exists():
        raise ValueError(f"domain has no db files: {resolved}")
    removed: list[str] = []
    for key in ("cache_db", "graph_db", "cypher_path"):
        path = paths.get(key)
        if isinstance(path, Path) and path.exists():
            path.unlink()
            removed.append(str(path))
    domain_dir = paths["domain"]
    if domain_dir.exists() and domain_dir.is_dir():
        try:
            domain_dir.rmdir()
        except OSError:
            pass
    return {"domain": resolved, "removed": removed}


def data_layout_snapshot(domain: str | None = None) -> dict[str, str]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return {
        "data_root": str(data_root()),
        "markdown_root": str(markdown_type_root()),
        "jira_root": str(jira_type_root()),
        "ontology_root": str(ontology_type_root()),
        "active_markdown_dir": str(domain_markdown_dir(resolved)),
        "active_jira_dir": str(domain_jira_dir(resolved)),
        "active_ontology_dir": str(domain_ontology_dir(resolved)),
    }


@contextmanager
def _domain_env(domain: str | None):
    paths = domain_db_paths(domain)
    cache_path = str(paths["cache_db"])
    graph_path = str(paths["graph_db"])
    cypher_path = str(paths["cypher_path"]) if paths.get("cypher_path") else ""
    previous = {
        k: os.environ.get(k) 
        for k in ("JIRA_CACHE_DB", "JIRA_GRAPH_DB", "JIRA_GRAPH_CYPHER_PATH")
    }
    os.environ["JIRA_CACHE_DB"] = cache_path
    os.environ["JIRA_GRAPH_DB"] = graph_path
    if cypher_path:
        os.environ["JIRA_GRAPH_CYPHER_PATH"] = cypher_path
    elif "JIRA_GRAPH_CYPHER_PATH" in os.environ:
        del os.environ["JIRA_GRAPH_CYPHER_PATH"]
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _is_under_dir(path: Path, root: Path) -> bool:
    try:
        path_resolved = path.expanduser().resolve()
    except OSError:
        path_resolved = path.expanduser()
    try:
        root_resolved = root.expanduser().resolve()
    except OSError:
        root_resolved = root.expanduser()
    if path_resolved == root_resolved:
        return True
    return str(path_resolved).startswith(f"{root_resolved}{os.sep}")


def source_in_domain(source: Any, domain: str | None = None) -> bool:
    location = Path(str(getattr(source, "location", ""))).expanduser()
    md_root = domain_markdown_dir(domain)
    jira_root = domain_jira_dir(domain)
    owl_root = domain_ontology_dir(domain)
    pdf_root = domain_pdf_dir(domain)
    return (
        _is_under_dir(location, md_root)
        or _is_under_dir(location, jira_root)
        or _is_under_dir(location, owl_root)
        or _is_under_dir(location, pdf_root)
    )


def _source_matches_domain_legacy(source: Any, domain: str | None = None) -> bool:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    location = str(getattr(source, "location", "") or "").lower().replace("\\", "/")
    marker = f"/{resolved}/"
    if marker in location:
        return True
    metadata = getattr(source, "metadata", {}) or {}
    meta_domain = normalize_semantic_domain(str(metadata.get("domain", "") or ""))
    if meta_domain and meta_domain == resolved:
        return True
    return False


def domain_knowledge_summary(domain: str | None = None) -> dict[str, Any]:
    store_obj = store()
    scoped_sources = [
        source
        for source in store_obj.list_sources()
        if source_in_domain(source, domain=domain) or _source_matches_domain_legacy(source, domain=domain)
    ]
    source_ids = [source.source_id for source in scoped_sources]
    source_count = len(source_ids)
    if not source_ids:
        return {"sources": 0, "records": 0, "artifacts": 0, "recent_sources": [], "recent_artifacts": []}
    scoped_artifacts = [
        artifact
        for artifact in store_obj.list_artifacts()
        if getattr(artifact, "source_id", "") in set(source_ids)
    ]
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        source_placeholders = ",".join("?" for _ in source_ids)
        record_count = conn.execute(
            f"""
            SELECT COUNT(*) FROM knowledge_blocks kb
            JOIN knowledge_sources ks ON kb.source_path = ks.location
            WHERE ks.source_id IN ({source_placeholders})
            """,
            source_ids,
        ).fetchone()
        artifact_count = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})",
            source_ids,
        ).fetchone()
    return {
        "sources": source_count,
        "records": int(record_count[0]) if record_count else 0,
        "artifacts": int(artifact_count[0]) if artifact_count else 0,
        "recent_sources": scoped_sources[:8],
        "recent_artifacts": scoped_artifacts[:8],
    }


def domain_source_ids(domain: str | None = None) -> set[str]:
    scoped_sources = [
        source
        for source in store().list_sources()
        if source_in_domain(source, domain=domain) or _source_matches_domain_legacy(source, domain=domain)
    ]
    return {str(source.source_id) for source in scoped_sources}


def domain_registry_overview(active_domain: str | None = None) -> list[dict[str, Any]]:
    """Combined overview of every registered Domain across both pipelines.

    Returns one dict per Domain row with knowledge-pipeline stats (Jira/OWL/
    Markdown-workspace, via domain_knowledge_summary) and InfoSite stats
    (project/source-document counts), so a single "domain tile" can show
    both without either pipeline's storage being touched or merged.
    """

    from ki_knowledge.django_site.infosite_models import Domain, InfoSiteProject, SourceDocument

    overview: list[dict[str, Any]] = []
    for domain in Domain.objects.all():
        knowledge = domain_knowledge_summary(domain.slug)
        projects = InfoSiteProject.objects.filter(domain=domain.slug)
        overview.append(
            {
                "slug": domain.slug,
                "display_name": domain.display_name or domain.slug,
                "is_active": domain.slug == active_domain,
                "knowledge_sources": knowledge["sources"],
                "knowledge_records": knowledge["records"],
                "infosite_project_count": projects.count(),
                "infosite_source_count": SourceDocument.objects.filter(project__domain=domain.slug).count(),
            }
        )
    return overview



def _domain_knowledge_scope(domain: str | None = None) -> tuple[list[str], list[str]]:
    scoped_sources = [
        source
        for source in store().list_sources()
        if source_in_domain(source, domain=domain) or _source_matches_domain_legacy(source, domain=domain)
    ]
    source_ids = [source.source_id for source in scoped_sources]
    source_locations = [str(source.location) for source in scoped_sources]
    return source_ids, source_locations


def knowledge_base_clear_domain_artifacts(domain: str | None = None) -> dict[str, Any]:
    source_ids, _ = _domain_knowledge_scope(domain)
    if not source_ids:
        return {"domain": normalize_semantic_domain(domain), "deleted_artifacts": 0}
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        placeholders = ",".join("?" for _ in source_ids)
        row = conn.execute(
            f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({placeholders})",
            source_ids,
        ).fetchone()
        deleted_artifacts = int(row[0]) if row else 0
        conn.execute(f"DELETE FROM knowledge_artifacts WHERE source_id IN ({placeholders})", source_ids)
    return {
        "domain": normalize_semantic_domain(domain),
        "sources": len(source_ids),
        "deleted_artifacts": deleted_artifacts,
    }


def knowledge_base_reset_domain(domain: str | None = None) -> dict[str, Any]:
    source_ids, source_locations = _domain_knowledge_scope(domain)
    normalized_domain = normalize_semantic_domain(domain)
    if not source_ids and not source_locations:
        return {
            "domain": normalized_domain,
            "sources": 0,
            "deleted_records": 0,
            "deleted_relations": 0,
            "deleted_embeddings": 0,
            "deleted_artifacts": 0,
            "deleted_sources": 0,
        }
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        block_ids: list[str] = []
        queries: list[tuple[str, list[str]]] = []
        if source_locations:
            placeholders = ",".join("?" for _ in source_locations)
            queries.append((f"SELECT id FROM knowledge_blocks WHERE source_path IN ({placeholders})", source_locations))
        if source_ids:
            placeholders = ",".join("?" for _ in source_ids)
            queries.append(
                (
                    f"SELECT id FROM knowledge_blocks WHERE json_extract(metadata_json, '$.source_id') IN ({placeholders})",
                    source_ids,
                )
            )
        for query, params in queries:
            rows = conn.execute(query, params).fetchall()
            block_ids.extend(str(row[0]) for row in rows)
        block_ids = sorted(set(block_ids))

        deleted_relations = 0
        deleted_embeddings = 0
        deleted_records = 0
        if block_ids:
            block_placeholders = ",".join("?" for _ in block_ids)
            relation_row = conn.execute(
                f"""
                SELECT COUNT(*) FROM knowledge_relations
                WHERE source_block_id IN ({block_placeholders})
                   OR target_block_id IN ({block_placeholders})
                """,
                [*block_ids, *block_ids],
            ).fetchone()
            deleted_relations = int(relation_row[0]) if relation_row else 0
            embedding_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_embeddings WHERE block_id IN ({block_placeholders})",
                block_ids,
            ).fetchone()
            deleted_embeddings = int(embedding_row[0]) if embedding_row else 0
            record_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_blocks WHERE id IN ({block_placeholders})",
                block_ids,
            ).fetchone()
            deleted_records = int(record_row[0]) if record_row else 0
            conn.execute(
                f"""
                DELETE FROM knowledge_relations
                WHERE source_block_id IN ({block_placeholders})
                   OR target_block_id IN ({block_placeholders})
                """,
                [*block_ids, *block_ids],
            )
            conn.execute(f"DELETE FROM knowledge_embeddings WHERE block_id IN ({block_placeholders})", block_ids)
            conn.execute(f"DELETE FROM knowledge_blocks WHERE id IN ({block_placeholders})", block_ids)

        deleted_artifacts = 0
        deleted_sources = 0
        if source_ids:
            source_placeholders = ",".join("?" for _ in source_ids)
            artifact_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})",
                source_ids,
            ).fetchone()
            deleted_artifacts = int(artifact_row[0]) if artifact_row else 0
            source_row = conn.execute(
                f"SELECT COUNT(*) FROM knowledge_sources WHERE source_id IN ({source_placeholders})",
                source_ids,
            ).fetchone()
            deleted_sources = int(source_row[0]) if source_row else 0
            conn.execute(f"DELETE FROM knowledge_artifacts WHERE source_id IN ({source_placeholders})", source_ids)
            conn.execute(f"DELETE FROM knowledge_sources WHERE source_id IN ({source_placeholders})", source_ids)

    return {
        "domain": normalized_domain,
        "sources": len(source_ids),
        "deleted_records": deleted_records,
        "deleted_relations": deleted_relations,
        "deleted_embeddings": deleted_embeddings,
        "deleted_artifacts": deleted_artifacts,
        "deleted_sources": deleted_sources,
    }


def knowledge_base_reset_all() -> dict[str, Any]:
    with sqlite3.connect(settings.KNOWLEDGE_DB_PATH) as conn:
        counts = {}
        for table in (
            "knowledge_relations",
            "knowledge_embeddings",
            "knowledge_artifacts",
            "knowledge_blocks",
            "knowledge_sources",
        ):
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = int(row[0]) if row else 0
        conn.execute("DELETE FROM knowledge_relations")
        conn.execute("DELETE FROM knowledge_embeddings")
        conn.execute("DELETE FROM knowledge_artifacts")
        conn.execute("DELETE FROM knowledge_blocks")
        conn.execute("DELETE FROM knowledge_sources")
    return {"deleted": counts}


def store() -> KnowledgeStore:
    return KnowledgeStore(settings.KNOWLEDGE_DB_PATH)


def root_markdown_tree(query: str = "", domain: str | None = None):
    return build_markdown_tree(data_dir(domain), query=query)


def workspace_markdown_files(query: str = "", domain: str | None = None) -> list[dict[str, str]]:
    root = data_dir(domain)
    files = discover_markdown_files(root)
    normalized_query = query.strip().lower()
    if normalized_query:
        files = [
            path
            for path in files
            if normalized_query in path.name.lower() or normalized_query in path.as_posix().lower()
        ]
    return [
        {"name": path.relative_to(root).as_posix(), "path": str(path)}
        for path in files
    ]


def discover_ontology_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
    return sorted(path for path in root.glob("**/*") if path.is_file() and path.suffix.lower() in suffixes)


def workspace_ontology_files(query: str = "", domain: str | None = None) -> list[dict[str, str]]:
    root = domain_ontology_dir(domain)
    files = discover_ontology_files(root)
    normalized_query = query.strip().lower()
    if normalized_query:
        files = [
            path
            for path in files
            if normalized_query in path.name.lower() or normalized_query in path.as_posix().lower()
        ]
    return [
        {"name": path.relative_to(root).as_posix(), "path": str(path)}
        for path in files
    ]


def render_markdown_html(content: str) -> str:
    return markdown.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "toc"],
        output_format="html5",
    )


def tree_lines(node, prefix: str = "") -> list[str]:
    lines: list[str] = []
    for child in node.iter_children():
        lines.append(f"{prefix}{child.name}/")
        lines.extend(tree_lines(child, prefix=prefix + "  "))
    for file_path in node.files:
        lines.append(f"{prefix}{file_path.name}")
    return lines


def import_markdown_file(path: Path, *, source_name: str | None = None, block_types: list[str] | None = None) -> dict[str, Any]:
    store_obj = store()
    # For ontology files, import directly as OWL source instead of markdown
    if "/ontology/" in str(path) and path.suffix == ".md":
        return {"imported": 0, "source_id": "owl:deprecated-markdown", "note": "Ontology markdown import is deprecated; use OWL format directly"}
    
    # Automatically filter ontology imports to reduce metadata bloat
    if block_types is None and "/ontology/" in str(path):
        block_types = ["heading", "paragraph"]
    blocks = store_obj.import_markdown_file(path, source_name=source_name, allowed_block_types=block_types)
    return {"imported": len(blocks), "source_id": f"markdown:{path.resolve()}"}


def import_ontology_file(path: Path) -> dict[str, Any]:
    """Import OWL/RDF file directly as ontology source."""
    text = path.read_text(encoding="utf-8")
    try:
        record_count, source_id = import_ontology_to_store(
            text,
            source_url=str(path),
            title=path.stem.replace("_", " ").title(),
        )
        return {"imported": record_count, "source_id": source_id, "type": "ontology"}
    except Exception as exc:
        return {"imported": 0, "error": str(exc), "type": "ontology"}


def import_ontology_directory(directory: Path) -> dict[str, Any]:
    """Import all ontology files (OWL/RDF/TTL/etc.) from directory and subdirectories."""
    if not directory.exists() or not directory.is_dir():
        return {"imported": 0, "error": f"Directory not found: {directory}", "files": 0}
    
    # Recursively find all ontology files in subdirectories
    ontology_suffixes = {".owl", ".rdf", ".ttl", ".n3", ".jsonld"}
    ontology_files = sorted(
        path for path in directory.glob("**/*")
        if path.is_file() and path.suffix.lower() in ontology_suffixes
    )
    
    if not ontology_files:
        return {"imported": 0, "files": 0}
    
    imported = 0
    source_ids: list[str] = []
    
    for ontology_path in ontology_files:
        result = import_ontology_file(ontology_path)
        imported += int(result.get("imported", 0))
        if "source_id" in result:
            source_ids.append(result["source_id"])
    
    return {"imported": imported, "source_ids": source_ids, "files": len(ontology_files)}


def import_ontology_url(url: str, *, top_n: int = 50) -> dict[str, Any]:
    """Fetch and import ontology from a remote URL."""
    text, content_type = fetch_ontology_url(url)
    record_count, source_id = import_ontology_to_store(
        text,
        source_url=url,
        content_type=content_type,
        title=Path(url).stem.replace("_", " ").title() or "Ontology",
        top_n=top_n,
    )
    return {"imported": record_count, "source_id": source_id, "type": "ontology"}


def import_markdown_directory(directory: Path, *, block_types: list[str] | None = None) -> dict[str, Any]:
    store_obj = store()
    files = discover_markdown_files(directory)
    imported = 0
    source_ids: list[str] = []
    for file_path in files:
        result = import_markdown_file(
            file_path,
            source_name=file_path.relative_to(directory).as_posix(),
            block_types=block_types,
        )
        imported += int(result["imported"])
        source_ids.append(result["source_id"])
    return {"imported": imported, "source_ids": source_ids, "files": len(files)}


def import_pdf_file(path: Path, *, source_name: str | None = None, domain: str | None = None) -> dict[str, Any]:
    """Import a PDF file as markdown blocks into the knowledge store."""
    store_obj = store()
    if not path.exists():
        return {"imported": 0, "error": f"PDF not found: {path}"}
    
    try:
        markdown_text = pdf_extract_text(path)
    except Exception as exc:
        return {"imported": 0, "error": str(exc), "file": str(path)}
    
    if not markdown_text.strip():
        return {"imported": 0, "error": "PDF contains no extractable text", "file": str(path)}
    
    blocks = store_obj.import_markdown_text(
        markdown_text,
        source_path=str(path.resolve()),
        source_name=source_name or pdf_relative_source_path(path, domain=domain),
        source_id=pdf_source_id(path, domain=domain),
        source_type="pdf",
    )
    return {"imported": len(blocks), "source_id": pdf_source_id(path, domain=domain), "file": str(path)}


def import_pdf_directory(directory: Path, *, domain: str | None = None) -> dict[str, Any]:
    """Import all PDF files from a directory and subdirectories into the knowledge store."""
    if not directory.exists() or not directory.is_dir():
        return {"imported": 0, "error": f"Directory not found: {directory}"}
    
    # Recursively find all PDF files in subdirectories, including symlinked folders
    pdf_files = discover_pdf_files(directory)
    imported = 0
    source_ids: list[str] = []

    for pdf_path in pdf_files:
        try:
            relative_name = pdf_path.relative_to(directory).as_posix()
        except ValueError:
            relative_name = pdf_path.name
        result = import_pdf_file(
            pdf_path,
            source_name=relative_name,
            domain=domain,
        )
        imported += int(result.get("imported", 0))
        if "source_id" in result:
            source_ids.append(result["source_id"])

    return {"imported": imported, "source_ids": source_ids, "files": len(pdf_files)}


def generate_all_artifacts(source_id: str, max_items: int = 8) -> list[dict[str, Any]]:
    generator = KnowledgeArtifactGenerator(store())
    return [
        generator.generate_quiz_module(source_id, max_questions=max_items),
        generator.generate_flashcards(source_id, max_cards=max_items),
        generator.generate_summary_note(source_id, max_sections=max_items),
        generator.generate_glossary(source_id, max_terms=max_items),
        generator.generate_study_guide(source_id, max_items=max_items),
    ]


def graph_payload(source_id: str, limit: int = 400) -> dict[str, Any]:
    graph = KnowledgeGraph(settings.KNOWLEDGE_DB_PATH)
    return graph.source_graph_payload(store(), source_id=source_id, limit=limit)


def graph_context(source_id: str, limit: int = 400) -> dict[str, Any]:
    payload = graph_payload(source_id, limit=limit)
    network = create_pyvis_network(graph_dict_to_networkx(payload), physics_enabled=True)
    stats = graph_statistics(graph_dict_to_networkx(payload))
    return {
        "payload": payload,
        "graph_html": network.generate_html(),
        "stats": stats,
    }


def graph_3d_context(source_id: str, limit: int = 400) -> dict[str, Any]:
    payload = graph_payload(source_id, limit=limit)
    graph = graph_dict_to_networkx(payload)
    stats = graph_statistics(graph)
    if graph.number_of_nodes() == 0:
        return {"graph_3d": {"nodes": [], "edges": []}, "stats": stats}

    positions = nx.spring_layout(graph, dim=3, seed=42)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for node_id, data in graph.nodes(data=True):
        pos = positions.get(node_id, [0.0, 0.0, 0.0])
        degree = graph.degree(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": data.get("label", node_id),
                "node_type": data.get("node_type", "unknown"),
                "path": data.get("path", ""),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": float(pos[2]),
                "size": max(4, min(22, 6 + degree)),
            }
        )

    for src, dst, edge_data in graph.edges(data=True):
        src_pos = positions.get(src, [0.0, 0.0, 0.0])
        dst_pos = positions.get(dst, [0.0, 0.0, 0.0])
        edges.append(
            {
                "source": src,
                "target": dst,
                "predicate": edge_data.get("predicate", ""),
                "weight": float(edge_data.get("weight", 1.0)),
                "x0": float(src_pos[0]),
                "y0": float(src_pos[1]),
                "z0": float(src_pos[2]),
                "x1": float(dst_pos[0]),
                "y1": float(dst_pos[1]),
                "z1": float(dst_pos[2]),
            }
        )

    return {
        "graph_3d": {"nodes": nodes, "edges": edges},
        "graph_3d_json": json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False),
        "stats": stats,
    }


def jira_cache_db_path(domain: str | None = None) -> str:
    return str(domain_db_paths(domain)["cache_db"])


def jira_issue_count(domain: str | None = None) -> int:
    cache_path = Path(jira_cache_db_path(domain)).expanduser()
    if not cache_path.exists():
        return 0
    return JiraIssueCache(str(cache_path)).issue_count()


def jira_csv_path(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_key = f"JIRA_CSV_PATH_{resolved.upper().replace('-', '_')}"
    explicit = os.getenv(domain_key, "").strip() or os.getenv("JIRA_CSV_PATH", "").strip()
    if explicit:
        return str(Path(explicit).expanduser())
    jira_dir = domain_jira_dir(resolved)
    if not jira_dir.exists() or not jira_dir.is_dir():
        return ""
    candidates = sorted(path for path in jira_dir.glob("*.csv") if path.is_file())
    if not candidates:
        return ""
    for preferred in ("jira.csv", "issues.csv", f"{resolved}.csv"):
        exact = next((path for path in candidates if path.name.lower() == preferred), None)
        if exact is not None:
            return str(exact)
    return str(candidates[0])


def jira_domain_terms(
    limit: int = 200,
    min_count: int = 2,
    *,
    sort: str = "relevance",
    order: str = "desc",
    domain: str | None = None,
) -> list[DomainTerm]:
    cache_path = Path(jira_cache_db_path(domain)).expanduser()
    if not cache_path.exists():
        return []
    cache = JiraIssueCache(str(cache_path))
    store_obj = semantic_store(domain)
    ingest_limit = max(limit * 5, 300)
    extracted = cache.extract_domain_terms(limit=ingest_limit, min_count=min_count)
    store_obj.store_domain_candidates(extracted)
    store_obj.promote_candidates(limit=ingest_limit)
    return store_obj.list_domain_terms(limit=limit, min_count=min_count, sort=sort, order=order)


def jira_reset_data(domain: str | None = None) -> dict[str, Any]:
    paths = domain_db_paths(domain)
    cache_db = Path(paths["cache_db"]).expanduser()
    graph_db = Path(paths["graph_db"]).expanduser()
    cypher_path = paths.get("cypher_path")

    removed = []
    for path in (cache_db, graph_db, cypher_path):
        if path is not None and path.exists():
            path.unlink()
            removed.append(str(path))

    return {
        "removed": removed,
        "cache_db": str(cache_db),
        "graph_db": str(graph_db),
        "cypher_path": str(cypher_path) if cypher_path else "",
    }


def jira_reimport_data(domain: str | None = None) -> dict[str, Any]:
    config = Config.from_env()
    csv_path = jira_csv_path(domain)
    if not csv_path:
        raise ValueError("JIRA_CSV_PATH missing")

    csv_encoding = os.getenv("JIRA_CSV_ENCODING", "utf-8-sig").strip() or "utf-8-sig"
    csv_delimiter = os.getenv("JIRA_CSV_DELIMITER", "").strip() or None
    cache_db = jira_cache_db_path(domain)
    graph_db = jira_graph_db_path(domain)
    cypher_path = str(domain_db_paths(domain).get("cypher_path") or "")
    embed_model = (
        os.getenv("KNOWLEDGE_EMBED_MODEL")
        or os.getenv("JIRA_EMBED_MODEL")
        or config.knowledge_embed_model
        or "nomic-embed-text"
    )
    embed_model = embed_model.strip()
    use_hybrid = os.getenv("KI_USE_HYBRID_SEARCH") or os.getenv("JIRA_USE_HYBRID_SEARCH", "true")
    use_hybrid = use_hybrid.lower() in {"1", "true", "yes"}

    issues = JiraCSVImporter.from_csv(csv_path, encoding=csv_encoding, delimiter=csv_delimiter)
    cache = JiraIssueCache(cache_db)
    ingested = cache.ingest_issues(issues)

    embedded_issues = 0
    embedded_fields = 0
    embedding_backend = "none"
    if use_hybrid:
        try:
            backend = OllamaEmbeddingProvider(
                base_url=config.ollama_base_url or "http://localhost:11434",
                model=embed_model,
            )
            backend.embed("probe")
            embedded_issues = cache.build_embeddings(backend, embedding_model=embed_model)
            embedded_fields = cache.build_field_embeddings(backend, embedding_model=embed_model)
            embedding_backend = f"ollama:{embed_model}"
        except Exception:
            tfidf = TFIDFEmbeddingProvider()
            tfidf.fit(i.full_text for i in cache.list_issues(limit=5000))
            embedded_issues = cache.build_embeddings(tfidf, embedding_model="tfidf")
            embedded_fields = cache.build_field_embeddings(tfidf, embedding_model="tfidf-fields")
            embedding_backend = "tfidf"

    graph = JiraKnowledgeGraph(graph_db)
    graph_stats = graph.rebuild_from_cache(cache)
    semantic_store_obj = SemanticTermStore(cache_db)
    candidates = cache.extract_domain_terms(limit=300, min_count=2)
    created_candidates = semantic_store_obj.store_domain_candidates(candidates)
    promoted_terms = semantic_store_obj.promote_candidates(limit=300)

    if cypher_path:
        Path(cypher_path).write_text(graph.export_cypher(), encoding="utf-8")

    return {
        "csv_path": csv_path,
        "cache_db": cache_db,
        "graph_db": graph_db,
        "ingested": ingested,
        "issues": cache.issue_count(),
        "graph_nodes": graph_stats["nodes"],
        "graph_edges": graph_stats["edges"],
        "embedded_issues": embedded_issues,
        "embedded_fields": embedded_fields,
        "embedding_backend": embedding_backend,
        "term_candidates": created_candidates,
        "promoted_terms": promoted_terms,
        "cypher_path": cypher_path,
    }


def _normalize_retrieval_sources(source_types: str | list[str] | None) -> set[str]:
    all_types = {"markdown", "pdf", "jira", "owl"}
    if source_types is None:
        return all_types
    if isinstance(source_types, str):
        candidates = [part.strip() for part in source_types.split(",") if part.strip()]
    else:
        candidates = [str(part).strip() for part in source_types if str(part).strip()]
    normalized: set[str] = set()
    aliases = {
        "markdown": "markdown",
        "md": "markdown",
        "pdf": "pdf",
        "jira": "jira",
        "jira_issue": "jira",
        "jira_csv": "jira",
        "csv": "jira",
        "owl": "owl",
        "ontology": "owl",
        "rdf": "owl",
        "ttl": "owl",
    }
    for candidate in candidates:
        key = candidate.lower()
        if key in {"all", "*", "all_sources", "all-sources"}:
            return all_types
        mapped = aliases.get(key, key)
        if mapped in all_types:
            normalized.add(mapped)
    return normalized or all_types


def _split_retrieval_chunks(text: str) -> list[str]:
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    blocks = re.split(r"\n\s*\n+", cleaned)
    chunks: list[str] = []
    for block in blocks:
        compact = re.sub(r"\s+", " ", block).strip()
        if len(compact) >= 40:
            chunks.append(compact)
    if not chunks:
        compact = re.sub(r"\s+", " ", cleaned).strip()
        if compact:
            chunks.append(compact[:2000])
    return chunks


def _score_retrieval_text(question: str, title: str, snippet: str) -> float:
    normalized_question = (question or "").lower()
    if not normalized_question:
        return 0.0
    query_terms = set(re.findall(r"[a-zA-Z0-9äöüÄÖÜ_-]{3,}", normalized_question))
    if not query_terms:
        return 0.0
    haystack = f"{title} {snippet}".lower()
    hits = sum(1 for term in query_terms if term in haystack)
    return float(hits + 0.2 * len(query_terms & set(re.findall(r"[a-zA-Z0-9äöüÄÖÜ_-]{3,}", haystack))))


def support_search(
    query: str,
    *,
    domain: str | None = None,
    source_types: str | list[str] | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    """Search all active source types for a domain and rank context snippets."""
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    normalized_query = (query or "").strip()
    if not normalized_query:
        return []
    selected_types = _normalize_retrieval_sources(source_types)
    hits: list[dict[str, Any]] = []
    markdown_dir = domain_markdown_dir(resolved_domain)
    pdf_dir = domain_pdf_dir(resolved_domain)
    jira_dir = domain_jira_dir(resolved_domain)
    ontology_dir = domain_ontology_dir(resolved_domain)

    if "markdown" in selected_types:
        for path in discover_markdown_files(markdown_dir):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            title = path.stem or path.name
            for snippet in _split_retrieval_chunks(content):
                score = _score_retrieval_text(normalized_query, title, snippet)
                if score <= 0:
                    continue
                hits.append(
                    {
                        "source_type": "markdown",
                        "source_id": f"markdown:{path.resolve()}",
                        "title": title,
                        "path": str(path),
                        "score": round(score, 3),
                        "snippet": snippet[:800],
                    }
                )

    if "pdf" in selected_types and pdf_dir.exists():
        for path in discover_pdf_files(pdf_dir):
            try:
                content = pdf_extract_text(path)
            except Exception:
                continue
            title = path.stem or path.name
            for snippet in _split_retrieval_chunks(content):
                score = _score_retrieval_text(normalized_query, title, snippet)
                if score <= 0:
                    continue
                hits.append(
                    {
                        "source_type": "pdf",
                        "source_id": pdf_source_id(path, domain=resolved_domain),
                        "title": title,
                        "path": str(path),
                        "score": round(score, 3),
                        "snippet": snippet[:800],
                    }
                )

    if "jira" in selected_types:
        for csv_path in sorted(jira_dir.glob("*.csv"), key=lambda item: item.name.lower()):
            if not csv_path.is_file():
                continue
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
                    reader = csv.DictReader(handle)
                    rows = list(reader)
            except (OSError, csv.Error):
                continue
            if not rows:
                continue
            for row in rows[:12]:
                row_text = " ".join(f"{key}: {value}" for key, value in row.items() if value and str(value).strip())
                snippet = row_text[:500]
                if not snippet:
                    continue
                score = _score_retrieval_text(normalized_query, csv_path.stem, snippet)
                if score <= 0:
                    continue
                hits.append(
                    {
                        "source_type": "jira",
                        "source_id": f"jira:{csv_path.resolve()}",
                        "title": csv_path.stem,
                        "path": str(csv_path),
                        "score": round(score, 3),
                        "snippet": snippet,
                    }
                )

    if "owl" in selected_types:
        for path in discover_ontology_files(ontology_dir):
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            title = path.stem or path.name
            for snippet in _split_retrieval_chunks(content):
                score = _score_retrieval_text(normalized_query, title, snippet)
                if score <= 0:
                    continue
                hits.append(
                    {
                        "source_type": "owl",
                        "source_id": f"owl:{path.resolve()}",
                        "title": title,
                        "path": str(path),
                        "score": round(score, 3),
                        "snippet": snippet[:800],
                    }
                )

    ranked = sorted(hits, key=lambda item: (float(item["score"]), len(str(item["snippet"]))), reverse=True)[:limit]
    return ranked


def support_chat_answer(
    question: str,
    *,
    domain: str | None = None,
    source_types: str | list[str] | None = None,
    limit: int = 8,
    model: str | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    prompt = (question or "").strip()
    if not prompt:
        raise ValueError("question missing")
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    selected_types = _normalize_retrieval_sources(source_types)
    hits = support_search(prompt, domain=resolved_domain, source_types=sorted(selected_types), limit=max(1, limit))
    if not hits:
        answer = (
            "Ich habe in der aktuellen Domain keine passenden Quellen gefunden. "
            "Bitte prüfe die Domain oder aktive Quellen."
        )
        return {
            "answer": answer,
            "sources": [],
            "graph_expanded": [],
            "prompt": f"Frage: {prompt}\n\nKein passender Kontext gefunden.",
            "hits": [],
            "selected_source_types": sorted(selected_types),
            "domain": resolved_domain,
        }

    context_lines = []
    for index, hit in enumerate(hits, start=1):
        snippet = str(hit.get("snippet", "")).strip()
        context_lines.append(
            f"[{index}] {hit.get('source_type', 'source')} | {hit.get('title', 'Eintrag')} | {hit.get('path', '')}\n{snippet}"
        )
    context_block = "\n\n".join(context_lines)
    user_prompt = (
        "Du bist ein hilfreicher, sachlich und präzise antwortender Assistent. "
        "Antworte nur auf Basis des folgenden Kontexts; wenn etwas fehlt, sag das explizit.\n\n"
        f"Frage: {prompt}\n\n"
        "Kontext:\n"
        f"{context_block}\n\n"
        "Antworte kurz, konkret und nenne die relevanten Quellen/Dateien mit Typ und Titel."
    )
    config = Config.from_env()
    provider = OllamaClient(
        base_url=(base_url or config.ollama_base_url or "http://localhost:11434").strip(),
        model=(model or config.ollama_model or "llama3.2").strip(),
    )
    answer = provider.chat(
        ChatRequest(messages=[Message(role=Role.USER, content=user_prompt)])
    ).message.content.strip()
    source_details = [
        {
            "source_type": hit.get("source_type", "source"),
            "title": hit.get("title", "Eintrag"),
            "path": hit.get("path", ""),
            "score": hit.get("score", 0),
            "source_id": hit.get("source_id", ""),
            "snippet": hit.get("snippet", "")[:400],
        }
        for hit in hits
    ]
    return {
        "answer": answer,
        "sources": [f"{hit['source_type']}:{hit['title']}" for hit in hits],
        "graph_expanded": [],
        "prompt": user_prompt,
        "hits": hits,
        "source_details": source_details,
        "selected_source_types": sorted(selected_types),
        "domain": resolved_domain,
    }


def jira_support_chat_answer(
    question: str,
    limit: int = 8,
    domain: str | None = None,
    source_types: str | list[str] | None = None,
) -> dict[str, Any]:
    prompt = (question or "").strip()
    if not prompt:
        raise ValueError("question missing")
    result = support_chat_answer(
        prompt,
        domain=domain,
        source_types=source_types or ["markdown", "pdf", "jira", "owl"],
        limit=limit,
    )
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "graph_expanded": result["graph_expanded"],
        "prompt": result["prompt"],
        "issue_count": jira_issue_count(domain),
        "cache_db": jira_cache_db_path(domain),
        "hits": result["hits"],
        "source_details": result.get("source_details", []),
        "selected_source_types": result["selected_source_types"],
    }


def jira_graph_db_path(domain: str | None = None) -> str:
    return str(domain_db_paths(domain)["graph_db"])


def jira_hybrid_search(query: str, limit: int = 8, domain: str | None = None) -> dict[str, Any]:
    normalized = (query or "").strip()
    if not normalized:
        raise ValueError("query missing")
    with _domain_env(domain):
        cache, _, assistant = _get_components()
    backend = assistant.embedding_backend
    embedding_model = assistant.embedding_model
    if backend is None or not embedding_model:
        backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
    cache.build_embeddings(backend, embedding_model=embedding_model)
    hits = cache.hybrid_search(normalized, backend=backend, embedding_model=embedding_model, limit=limit)
    return {
        "hits": hits,
        "query": normalized,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
        "embedding_model": embedding_model,
    }


def jira_daily_timeline(days: int = 14, domain: str | None = None) -> dict[str, Any]:
    with _domain_env(domain):
        cache, _, _ = _get_components()
    items = cache.daily_timeline(limit_days=days)
    return {
        "timeline": items,
        "days": days,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
    }


def jira_graph_explorer(
    *,
    issue_key: str | None = None,
    limit: int = 20,
    rebuild: bool = False,
    domain: str | None = None,
) -> dict[str, Any]:
    with _domain_env(domain):
        cache, _, _ = _get_components()
    graph = JiraKnowledgeGraph(jira_graph_db_path(domain))
    stats = None
    if rebuild:
        stats = graph.rebuild_from_cache(cache)
    selected_key = (issue_key or "").strip()
    if not selected_key:
        issues = cache.list_issues(limit=1)
        selected_key = issues[0].key if issues else ""
    neighbors = graph.issue_neighbors(selected_key, limit=limit) if selected_key else []
    if stats is None:
        with sqlite3.connect(jira_graph_db_path(domain)) as conn:
            node_row = conn.execute("SELECT COUNT(*) FROM graph_nodes").fetchone()
            edge_row = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()
            stats = {
                "nodes": int(node_row[0]) if node_row else 0,
                "edges": int(edge_row[0]) if edge_row else 0,
            }
    return {
        "issue_key": selected_key,
        "neighbors": neighbors,
        "stats": stats,
        "graph_db": jira_graph_db_path(domain),
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
    }


def jira_domain_analysis(
    *,
    limit_terms: int = 20,
    min_count: int = 2,
    query: str = "",
    limit_hits: int = 8,
    domain: str | None = None,
) -> dict[str, Any]:
    with _domain_env(domain):
        cache, _, assistant = _get_components()
    terms = cache.extract_domain_terms(limit=limit_terms, min_count=min_count)
    backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
    embedded_fields = cache.build_field_embeddings(backend, embedding_model=embedding_model)
    normalized_query = (query or "").strip()
    hits = []
    if normalized_query:
        hits = cache.semantic_field_search(
            query=normalized_query,
            backend=backend,
            embedding_model=embedding_model,
            limit=limit_hits,
        )
    return {
        "terms": terms,
        "hits": hits,
        "query": normalized_query,
        "limit_terms": limit_terms,
        "min_count": min_count,
        "limit_hits": limit_hits,
        "embedding_model": embedding_model,
        "embedded_fields": embedded_fields,
        "cache_db": jira_cache_db_path(domain),
        "issue_count": cache.issue_count(),
    }


def jira_excluded_terms(kind: str | None = None, domain: str | None = None) -> list[dict[str, str]]:
    return JiraIssueCache(jira_cache_db_path(domain)).list_excluded_terms(kind=kind)


def jira_exclusion_add(term: str, kind: str = "exception", domain: str | None = None) -> bool:
    return JiraIssueCache(jira_cache_db_path(domain)).add_excluded_term(term, kind=kind)


def jira_exclusion_remove(term: str, domain: str | None = None) -> bool:
    return JiraIssueCache(jira_cache_db_path(domain)).remove_excluded_term(term)


def jira_forget_jira_term(term: str, kind: str = "exception", domain: str | None = None) -> dict[str, bool]:
    cache = JiraIssueCache(jira_cache_db_path(domain))
    added = cache.add_excluded_term(term, kind=kind)
    forgotten = semantic_store(domain).forget_term(term)
    return {"excluded": added, "forgotten": forgotten}


def semantic_store(domain: str | None = None) -> SemanticTermStore:
    return SemanticTermStore(jira_cache_db_path(domain))


def semantic_terms(status: str | None = None, limit: int = 300, domain: str | None = None):
    return semantic_store(domain).list_terms(status=status, limit=limit)


def semantic_term_detail(term_id: str, domain: str | None = None) -> dict[str, Any] | None:
    store_obj = semantic_store(domain)
    term = store_obj.get_term(term_id)
    if term is None:
        return None
    return {
        "term": term,
        "facts": store_obj.current_facts(term_id),
        "relations": store_obj.term_relations(term_id),
    }


def semantic_monitoring_snapshot(domain: str | None = None) -> dict[str, Any]:
    return semantic_store(domain).monitoring_snapshot(recent_limit=10)


def semantic_jobs(status: str | None = None, job_type: str | None = None, limit: int = 200, domain: str | None = None):
    return semantic_store(domain).list_jobs(status=status, job_type=job_type, limit=limit)


def semantic_job_detail(job_id: str, domain: str | None = None) -> dict[str, Any] | None:
    store_obj = semantic_store(domain)
    job = store_obj.get_job(job_id)
    if job is None:
        return None
    term = store_obj.get_term(job.term_id)
    related = []
    if term is not None:
        related = store_obj.current_facts(job.term_id)[:8]
    elif job.term_id:
        related = store_obj.list_record_term_links(record_id=job.term_id, limit=20)
    with _domain_env(domain):
        _, _, assistant = _get_components()
    enrichment_service = SemanticEnrichmentService(
        store=store_obj,
        backend=assistant.backend,
        model_id=_semantic_model_id(assistant),
        knowledge_db_path=str(settings.KNOWLEDGE_DB_PATH),
    )
    return {
        "job": job,
        "term": term,
        "facts": related,
        "prompt": enrichment_service.build_prompt_for_job(job),
    }


def _candidate_record_ids_for_semantic_linking(limit: int = 1200, min_len: int = 40) -> list[str]:
    records = store().list_records(limit=limit)
    allowed_types = {"paragraph", "list_item", "code_block", "quote", "heading"}
    ids: list[str] = []
    for item in records:
        if item.block_type not in allowed_types:
            continue
        content = (item.content or "").strip()
        if len(content) < min_len:
            continue
        ids.append(item.block_id)
    return ids


def run_dashboard_task(task_name: str, *, domain: str | None = None, target_domain: str | None = None) -> dict[str, Any]:
    resolved_domain = normalize_semantic_domain(domain or default_semantic_domain())
    if task_name == "domain_switch":
        return {"task": task_name, "domain": resolved_domain}

    if task_name == "domain_create":
        result = create_semantic_domain(target_domain or resolved_domain)
        return {"task": task_name, **result}

    if task_name == "domain_delete":
        deleted = delete_semantic_domain(target_domain)
        return {"task": task_name, **deleted}

    if task_name == "kb_reset_domain":
        result = knowledge_base_reset_domain(resolved_domain)
        return {"task": task_name, **result}

    if task_name == "kb_clear_artifacts_domain":
        result = knowledge_base_clear_domain_artifacts(resolved_domain)
        return {"task": task_name, **result}

    if task_name == "kb_reset_all":
        result = knowledge_base_reset_all()
        return {"task": task_name, **result}

    if task_name == "jira_reset":
        result = jira_reset_data(resolved_domain)
        return {"task": task_name, "domain": resolved_domain, **result}

    if task_name == "jira_reimport":
        result = jira_reimport_data(resolved_domain)
        return {"task": task_name, "domain": resolved_domain, **result}

    store_obj = semantic_store(resolved_domain)
    if task_name == "semantic_extract_promote":
        terms = jira_domain_terms(limit=300, min_count=2, domain=resolved_domain)
        candidates = store_obj.store_domain_candidates(terms)
        promoted = store_obj.promote_candidates(limit=300)
        return {"task": task_name, "domain": resolved_domain, "candidates": candidates, "promoted": promoted}

    if task_name == "semantic_enqueue":
        enqueued = store_obj.enqueue_jobs(job_type="definition", only_status="new", limit=200)
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued}

    if task_name == "semantic_run":
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
        )
        result = service.run_batch(batch_size=20)
        return {"task": task_name, "domain": resolved_domain, **result}

    if task_name == "semantic_refine_enqueue":
        enqueued = store_obj.enqueue_refinement_jobs(
            limit=100,
            min_facts=2,
            min_relations=1,
            min_confidence=0.65,
            job_type="refine",
        )
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued}

    if task_name == "semantic_refine_run":
        enqueued = store_obj.enqueue_refinement_jobs(
            limit=100,
            min_facts=2,
            min_relations=1,
            min_confidence=0.65,
            job_type="refine",
        )
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
        )
        result = service.run_batch(batch_size=20)
        return {"task": task_name, "domain": resolved_domain, "enqueued": enqueued, **result}

    if task_name == "semantic_fields_rebuild":
        with _domain_env(resolved_domain):
            cache, _, assistant = _get_components()
        backend, embedding_model = _field_embedding_backend(cache=cache, assistant=assistant)
        embedded = cache.build_field_embeddings(backend=backend, embedding_model=embedding_model)
        return {
            "task": task_name,
            "domain": resolved_domain,
            "embedded_fields": embedded,
            "embedding_model": embedding_model,
        }

    if task_name == "semantic_records_enqueue":
        record_ids = _candidate_record_ids_for_semantic_linking()
        enqueued = store_obj.enqueue_record_link_jobs(record_ids, job_type="record_terms")
        return {"task": task_name, "domain": resolved_domain, "records": len(record_ids), "enqueued": enqueued}

    if task_name == "semantic_records_run":
        with _domain_env(resolved_domain):
            _, _, assistant = _get_components()
        service = SemanticEnrichmentService(
            store=store_obj,
            backend=assistant.backend,
            model_id=_semantic_model_id(assistant),
            knowledge_db_path=str(settings.KNOWLEDGE_DB_PATH),
        )
        result = service.run_batch(batch_size=30, job_types=("record_terms",))
        return {"task": task_name, "domain": resolved_domain, **result}

    raise ValueError(f"unsupported dashboard task: {task_name}")


def pdf_batch_db_path(domain: str | None = None) -> str:
    """Get the PDF batch database path for a domain."""
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    data_dir = data_root()
    domain_dir = _resolve_existing_domain_dir(data_dir / "pdf", resolved)
    return str(domain_dir.parent.parent / ".pdf_import_jobs.sqlite")


def get_pdf_batch_processor():
    """Get or create PDF batch processor."""
    from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor
    db_path = pdf_batch_db_path()
    return PDFBatchProcessor(db_path)


def pdf_import_jobs(domain: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
    """Get PDF import jobs for a domain."""
    processor = get_pdf_batch_processor()
    jobs = processor.list_jobs(domain=domain or default_semantic_domain(), status=status)
    jobs = jobs[:limit]
    
    return [
        {
            "job_id": j.job_id,
            "pdf_path": j.pdf_path,
            "display_pdf_path": display_data_path(j.pdf_path),
            "domain": j.domain,
            "status": j.status,
            "pages_total": j.pages_total,
            "pages_processed": j.pages_processed,
            "progress_percent": (j.pages_processed / j.pages_total * 100) if j.pages_total > 0 else 0,
            "error_message": j.error_message,
            "created_at": j.created_at,
            "started_at": j.started_at,
            "completed_at": j.completed_at,
            "source_id": j.source_id,
            "artifact_id": j.artifact_id,
            "content_preview": _compact_job_preview(j.content_preview),
            "display_content_preview": _compact_job_preview(j.content_preview, limit=80),
        }
        for j in jobs
    ]


def _compact_job_preview(value: str | None, *, limit: int = 200) -> str:
    text = (value or "").replace("\r", " ").replace("\n", " ").strip()
    if not text:
        return ""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _parse_iso_datetime(value: str | None) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _minutes_since(value: str | None) -> int | None:
    parsed = _parse_iso_datetime(value)
    if parsed is None:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)
    return max(0, int(delta.total_seconds() // 60))


def pdf_import_report(domain: str | None = None, *, limit: int = 12) -> dict[str, Any]:
    """Build a report snapshot for the PDF import queue."""
    resolved_domain = domain or default_semantic_domain()
    jobs = pdf_import_jobs(domain=resolved_domain, limit=2000)
    counts = {
        "total": len(jobs),
        "pending": sum(1 for job in jobs if job["status"] == "pending"),
        "processing": sum(1 for job in jobs if job["status"] == "processing"),
        "done": sum(1 for job in jobs if job["status"] == "done"),
        "failed": sum(1 for job in jobs if job["status"] == "failed"),
    }
    processing_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("started_at") or job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "processing"
    ]
    pending_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "pending"
    ]
    failed_jobs = [
        {
            **job,
            "display_pdf_path": display_data_path(job["pdf_path"]),
            "age_minutes": _minutes_since(job.get("completed_at") or job.get("created_at")),
        }
        for job in jobs
        if job["status"] == "failed"
    ]
    return {
        "domain": resolved_domain,
        "counts": counts,
        "processing_jobs": processing_jobs,
        "pending_jobs": pending_jobs[:limit],
        "failed_jobs": failed_jobs[:limit],
        "recent_done": [
            {**job, "display_pdf_path": display_data_path(job["pdf_path"])}
            for job in jobs
            if job["status"] == "done"
        ][:limit],
        "stale_processing": [
            job
            for job in processing_jobs
            if job.get("age_minutes") is not None and job["age_minutes"] >= 30
        ],
    }


def get_pdf_job_stats(domain: str | None = None) -> dict[str, int]:
    """Get PDF import job statistics for a domain."""
    jobs = pdf_import_jobs(domain=domain, limit=1000)
    return {
        "total": len(jobs),
        "pending": sum(1 for j in jobs if j["status"] == "pending"),
        "processing": sum(1 for j in jobs if j["status"] == "processing"),
        "done": sum(1 for j in jobs if j["status"] == "done"),
        "failed": sum(1 for j in jobs if j["status"] == "failed"),
    }


def create_pdf_import_job(pdf_path: str, domain: str | None = None) -> str:
    """Create a new PDF import job."""
    processor = get_pdf_batch_processor()
    return processor.create_job(pdf_path, domain=domain or default_semantic_domain())


def delete_pdf_import_jobs(job_ids: list[str], domain: str | None = None) -> dict[str, int]:
    """Delete old PDF import jobs for a domain."""
    processor = get_pdf_batch_processor()
    return processor.delete_jobs(job_ids, domain=domain or default_semantic_domain())


def process_pdf_import_job(job_id: str) -> dict:
    """Process a PDF import job immediately."""
    processor = get_pdf_batch_processor()
    return processor.process_job(job_id)

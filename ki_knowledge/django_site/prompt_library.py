"""Domain prompt templates, backlog execution and saved batch results."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

from ki_knowledge.django_site.source_workflow import import_markdown_file
from ki_knowledge.ui.knowledge_api_client import discover_markdown_files

from .chat_service import ollama_chat_answer
from .data_display import display_data_path
from .domain_registry import data_dir, default_semantic_domain, normalize_semantic_domain


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

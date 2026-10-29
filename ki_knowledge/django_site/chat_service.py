"""Configured chat-provider calls and conversation Markdown output."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import re

from django.conf import settings
from ki_core.core.models import ChatRequest, Message, Role
from ki_knowledge.llm_provider import chat_client, chat_models, chat_settings

from .domain_registry import data_dir, default_semantic_domain, normalize_semantic_domain


def ollama_runtime_settings() -> dict[str, str]:
    """Chat provider settings (``provider``, ``base_url``, ``model``) from ``llm.provider``."""
    return chat_settings()


def ollama_chat_dir(domain: str | None = None) -> Path:
    return data_dir(domain) / "ollama-chat"


def ollama_available_models(base_url: str | None = None) -> list[str]:
    settings = chat_settings()
    if base_url:
        settings = {**settings, "base_url": base_url}
    return chat_models(settings)


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

    provider = chat_client(model=model, base_url=base_url)
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
        "base_url": getattr(provider, "base_url", ""),
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

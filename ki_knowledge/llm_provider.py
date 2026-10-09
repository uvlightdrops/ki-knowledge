"""Chat client for the configured LLM provider (ki-core ``llm.default_provider``).

Same convention as kicli-code-assist: ``llm.default_provider`` selects one of
``llm.providers.{ki,openai,ollama}``; ``ki`` is the company-internal,
OpenAI-compatible server (key in ``creds.yaml``).  ``http.verify_ssl`` and
``http.request_timeout`` apply to the remote providers.  Embeddings are not
affected – they always use Ollama (``llm.providers.ollama.base_url``,
``knowledge.embed_model``) so vectors stay comparable across hosts.
"""

from __future__ import annotations

from typing import Any

from ki_core import AIClient
from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient

from ki_knowledge.app_config import AppConfig

CHAT_PROVIDERS = ("ki", "openai", "ollama", "mock")


def chat_settings(config: AppConfig | None = None) -> dict[str, str]:
    """``provider``, ``base_url`` and ``model`` of the configured chat provider."""
    config = config or AppConfig.from_env()
    provider = config.llm_default_provider
    if provider == "ki":
        return {"provider": "ki", "base_url": config.ki_base_url.strip(), "model": config.ki_model.strip()}
    if provider == "openai":
        return {"provider": "openai", "base_url": config.openai_base_url.strip(), "model": config.openai_model.strip()}
    if provider == "ollama":
        return {"provider": "ollama", "base_url": config.ollama_base_url.strip(), "model": config.ollama_model.strip()}
    if provider == "mock":
        return {"provider": "mock", "base_url": "", "model": "mock-1"}
    raise ValueError(f"llm.default_provider '{provider}' unbekannt (erlaubt: {', '.join(CHAT_PROVIDERS)})")


def chat_client(*, model: str | None = None, base_url: str | None = None, config: AppConfig | None = None) -> AIClient:
    """ki-core client for the configured provider; ``model`` overrides the config.

    ``base_url`` is only honoured for Ollama (e.g. a stored chat session); for
    remote providers the configured endpoint is always used.
    """
    config = config or AppConfig.from_env()
    settings = chat_settings(config)
    provider = settings["provider"]
    resolved_model = (model or settings["model"]).strip() or None
    resolved_url = ((base_url if provider == "ollama" else None) or settings["base_url"]).strip()
    if provider == "mock":
        return MockAIClient(model=resolved_model or "mock-1")
    if provider == "ollama":
        return OllamaClient(base_url=resolved_url, model=resolved_model, verify=config.http_verify_ssl)
    if not resolved_url:
        raise ValueError(f"llm.providers.{provider}.base_url fehlt in ki.yaml")
    api_key = config.ki_api_key if provider == "ki" else config.openai_api_key
    return OpenAICompatibleClient(
        base_url=resolved_url,
        api_key=api_key,
        model=resolved_model,
        timeout=config.request_timeout,
        verify=config.http_verify_ssl,
    )


def chat_models(settings: dict[str, Any] | None = None) -> list[str]:
    """Selectable models: installed Ollama models, otherwise just the configured one."""
    settings = settings or chat_settings()
    if settings["provider"] == "ollama":
        try:
            return OllamaClient.get_available_models(settings["base_url"])
        except Exception:
            return []
    return [settings["model"]] if settings["model"] else []

"""Chat client for the configured LLM provider (ki-core ``llm.provider``).

Same convention as kicli-code-assist: ``llm.provider`` selects one of
``llm.providers.{ki,openai,ollama}``; ``ki`` is the company-internal,
OpenAI-compatible server (key in ``creds.yaml``).  ``http.verify_ssl`` and
``http.request_timeout`` apply to the remote providers.  Embeddings are not
affected – they always use Ollama (``llm.providers.ollama.base_url``,
``knowledge.embed_model``) so vectors stay comparable across hosts.
"""

from __future__ import annotations

from typing import Any

from ki_core import AIClient
from ki_core.chat import create_chat_client, get_chat_models, get_chat_settings
from ki_core.core.errors import ValidationError

from ki_knowledge.app_config import AppConfig

CHAT_PROVIDERS = ("ki", "openai", "ollama", "mock")


def _chat_config(config: AppConfig) -> dict[str, Any]:
    """Adapt resolved app attributes, including explicit per-call overrides."""
    return {
        "llm": {
            "provider": config.llm_default_provider,
            "providers": {
                "ki": {
                    "base_url": config.ki_base_url,
                    "api_key": config.ki_api_key,
                    "model": config.ki_model,
                },
                "openai": {
                    "base_url": config.openai_base_url,
                    "api_key": config.openai_api_key,
                    "model": config.openai_model,
                },
                "ollama": {
                    "base_url": config.ollama_base_url,
                    "model": config.ollama_model,
                },
            },
        },
        "http": {"request_timeout": config.request_timeout, "verify_ssl": config.http_verify_ssl},
    }


def chat_settings(config: AppConfig | None = None) -> dict[str, str]:
    """``provider``, ``base_url`` and ``model`` of the configured chat provider."""
    try:
        return get_chat_settings(_chat_config(config or AppConfig.from_env()))
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def chat_client(*, model: str | None = None, base_url: str | None = None, config: AppConfig | None = None) -> AIClient:
    """ki-core client for the configured provider; ``model`` overrides the config.

    ``base_url`` is only honoured for Ollama (e.g. a stored chat session); for
    remote providers the configured endpoint is always used.
    """
    try:
        return create_chat_client(
            _chat_config(config or AppConfig.from_env()),
            model=model,
            ollama_base_url=base_url,
        )
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc


def chat_models(settings: dict[str, Any] | None = None) -> list[str]:
    """Selectable models: installed Ollama models, otherwise just the configured one."""
    return get_chat_models(settings or chat_settings())

import pytest
from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient

from ki_knowledge.app_config import AppConfig
from ki_knowledge.llm_provider import chat_client, chat_models, chat_settings


def test_mock_is_default():
    assert isinstance(chat_client(config=AppConfig()), MockAIClient)


def test_ki_provider_uses_internal_endpoint_with_ssl_and_timeout():
    cfg = AppConfig(
        llm_default_provider="ki", ki_base_url="https://ki.intern/v1", ki_api_key="k",
        ki_model="m", request_timeout=120, http_verify_ssl=False,
    )
    client = chat_client(base_url="http://localhost:11434", config=cfg)
    assert isinstance(client, OpenAICompatibleClient)
    assert client.base_url.startswith("https://ki.intern")
    assert chat_models(chat_settings(cfg)) == ["m"]


def test_ollama_honours_base_url_override():
    cfg = AppConfig(llm_default_provider="ollama")
    client = chat_client(base_url="http://other:11434", model="x", config=cfg)
    assert isinstance(client, OllamaClient) and client.base_url.startswith("http://other")


def test_unknown_provider_fails_clearly():
    with pytest.raises(ValueError):
        chat_settings(AppConfig(llm_default_provider="foo"))

import os

import pytest
import requests

from ki_core.adapters.mock import MockAIClient
from ki_core.adapters.ollama import OllamaClient
from ki_core.adapters.openai_compat import OpenAICompatibleClient
from ki_core.core.errors import ProviderError, TimeoutError as ProviderTimeoutError
from ki_core.core.models import ChatRequest, Message, Role, StreamEventType

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


@pytest.mark.parametrize("provider", ["ki", "openai", "ollama", "mock"])
def test_all_provider_settings_and_per_call_options(provider):
    cfg = AppConfig(
        llm_default_provider=provider,
        ki_base_url="https://ki.invalid/v1", ki_api_key="test-key", ki_model="ki-model",
        openai_base_url="https://openai.invalid/v1", openai_api_key="test-key", openai_model="openai-model",
        ollama_model="ollama-model", request_timeout=73, http_verify_ssl=False,
    )
    client = chat_client(config=cfg)
    if provider != "mock":
        assert client.timeout == 73
        assert client.verify is False
        assert client.default_model == f"{provider}-model"
    assert chat_settings(cfg)["provider"] == provider
    override = chat_client(model="override-model", base_url="http://override:11434", config=cfg)
    if provider == "mock":
        response = override.chat(ChatRequest(messages=[Message(Role.USER, "Synthetic test")]))
        assert response.model == "override-model"
    else:
        assert override.default_model == "override-model"
    if provider in {"ki", "openai"}:
        assert override.base_url == f"https://{provider}.invalid/v1"
    if provider == "ollama":
        assert override.base_url == "http://override:11434"


@pytest.mark.parametrize("provider", ["ki", "openai"])
@pytest.mark.parametrize("credential", ["", "${MISSING_KEY}"])
def test_credentials_missing_or_unresolved_fail_before_network(provider, credential, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Invalid configuration must not contact a provider")

    monkeypatch.setattr(requests, "post", forbidden)
    config = AppConfig(
        llm_default_provider=provider, ki_base_url="https://ki.invalid/v1",
        ki_api_key=credential, openai_api_key=credential,
    )
    with pytest.raises(ValueError, match="api_key"):
        chat_client(config=config)


def test_model_discovery_failure_is_not_an_empty_success(monkeypatch):
    def fail(url):
        raise ProviderError("Provider unavailable")

    monkeypatch.setattr(OllamaClient, "get_available_models", fail)
    with pytest.raises(ProviderError, match="unavailable"):
        chat_models({"provider": "ollama", "base_url": "http://offline:11434", "model": "m"})


@pytest.mark.parametrize("provider", ["ki", "openai", "ollama"])
@pytest.mark.parametrize("stream", [False, True])
def test_provider_protocol_through_app_adapter(provider, stream, monkeypatch):
    import json

    calls = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            if provider == "ollama":
                return {"message": {"content": "OK"}, "model": "server-model"}
            return {"choices": [{"message": {"content": "OK"}}], "model": "server-model"}

        def iter_lines(self):
            if provider == "ollama":
                yield json.dumps({"message": {"content": "OK"}}).encode()
                yield b'{"done": true}'
            else:
                yield b'data: {"choices":[{"delta":{"content":"OK"}}]}'
                yield b"data: [DONE]"

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(requests, "post", post)
    cfg = AppConfig(
        llm_default_provider=provider,
        ki_base_url="https://ki.invalid/v1", ki_api_key="ki-key", ki_model="ki-model",
        openai_api_key="openai-key", request_timeout=17, http_verify_ssl=False,
    )
    client = chat_client(config=cfg)
    request = ChatRequest(messages=[Message(Role.USER, "Synthetic connectivity test")], temperature=0)
    if stream:
        events = list(client.chat_stream(request))
        assert "".join(event.text for event in events) == "OK"
        assert events[-1].type == StreamEventType.DONE
    else:
        assert client.chat(request).message.content == "OK"
    assert len(calls) == 1
    url, options = calls[0]
    assert url.endswith("/api/chat" if provider == "ollama" else "/chat/completions")
    assert options["timeout"] == 17 and options["verify"] is False
    assert options["json"]["stream"] == stream
    assert options["json"]["messages"] == [{"role": "user", "content": "Synthetic connectivity test"}]
    if provider != "ollama":
        assert options["headers"]["Authorization"] == f"Bearer {provider}-key"


def test_live_runtime_provider_change_affects_next_client(tmp_path, monkeypatch):
    from ki_core.runtime_settings import RuntimeSettings
    from ki_knowledge.app_config import clear_config_cache

    monkeypatch.chdir(tmp_path)
    for key in list(os.environ):
        if key.startswith("KI_CFG_") or key in {"KI_STAGE", "KI_PROFILE"}:
            monkeypatch.delenv(key)
    (tmp_path / "ki.yaml").write_text(
        "llm:\n  provider: mock\n  providers:\n    ollama:\n      base_url: http://localhost:11434\n      model: initial-model\n",
        encoding="utf-8",
    )
    clear_config_cache()
    assert isinstance(chat_client(), MockAIClient)
    editor = RuntimeSettings(tmp_path)
    snapshot = editor.snapshot()
    editor.save(snapshot["revision"], {
        "llm.provider": "ollama", "llm.providers.ollama.model": "next-model", "http.request_timeout": 51,
    })
    client = chat_client()
    assert isinstance(client, OllamaClient)
    assert client.default_model == "next-model" and client.timeout == 51


@pytest.mark.parametrize("provider", ["ki", "openai", "ollama"])
@pytest.mark.parametrize("stream", [False, True])
def test_provider_timeout_is_explicit_without_failover(provider, stream, monkeypatch):
    calls = []

    def timeout(url, **kwargs):
        calls.append(url)
        raise requests.exceptions.Timeout("Synthetic timeout")

    monkeypatch.setattr(requests, "post", timeout)
    cfg = AppConfig(
        llm_default_provider=provider, ki_base_url="https://ki.invalid/v1",
        ki_api_key="test-key", openai_api_key="test-key",
    )
    client = chat_client(config=cfg)
    request = ChatRequest(messages=[Message(Role.USER, "Synthetic test")])
    with pytest.raises(ProviderTimeoutError):
        list(client.chat_stream(request)) if stream else client.chat(request)
    assert len(calls) == 1

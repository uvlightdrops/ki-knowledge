from __future__ import annotations

from ki_core.adapters.openai_compat import OpenAICompatibleClient as _OpenAICompatibleClient
from ki_core.core.models import ChatRequest, Message, Role


class KIClient:
    """Compatibility wrapper around the ki-core OpenAI-compatible client."""

    def __init__(self, config) -> None:
        self._client = _OpenAICompatibleClient(
            base_url=config.ki_base_url,
            api_key=config.ki_api_key,
            model=getattr(config, "ki_model", None),
            timeout=getattr(config, "request_timeout", 30),
        )
        self.model = getattr(config, "ki_model", None)

    def chat(self, messages: list[dict], **options) -> str:
        request = ChatRequest(
            messages=[
                Message(role=Role(str(message["role"])), content=str(message["content"]))
                for message in messages
            ],
            model=options.get("model") or self.model,
            temperature=options.get("temperature"),
        )
        return self._client.chat(request).message.content

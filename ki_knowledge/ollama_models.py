"""Pull the Ollama models this node needs (``python -m ki_knowledge.ollama_models``).

``knowledge.embed_model`` always, the chat model only if
``llm.default_provider`` is ``ollama``. Waits for Ollama first, so it also
works as a Kubernetes job started next to the Ollama pod.
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request

from ki_knowledge.app_config import AppConfig


def required_models(config: AppConfig) -> list[str]:
    models = [config.knowledge_embed_model]
    if config.llm_default_provider == "ollama":
        models.append(config.ollama_model)
    return list(dict.fromkeys(m.strip() for m in models if m and m.strip()))


def installed_models(base_url: str, wait_seconds: float = 0) -> set[str]:
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            with urllib.request.urlopen(f"{base_url}/api/tags", timeout=5) as response:
                return {m["name"] for m in json.load(response).get("models", [])}
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(3)


def pull(base_url: str, model: str) -> str:
    request = urllib.request.Request(
        f"{base_url}/api/pull",
        data=json.dumps({"model": model, "stream": False}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=3600) as response:
        return json.load(response).get("status", "")


def main() -> int:
    config = AppConfig.from_env()
    base_url = config.ollama_base_url.rstrip("/")
    try:
        installed = installed_models(base_url, wait_seconds=300)
    except OSError as exc:
        print(f"  ollama: {base_url} nicht erreichbar ({exc})")
        return 1
    ok = True
    for model in required_models(config):
        if model in installed or f"{model}:latest" in installed:
            continue
        print(f"  ollama: lade Modell {model} (einmalig, kann dauern) …", flush=True)
        try:
            status = pull(base_url, model)
        except OSError as exc:
            status = str(exc)
        if status != "success":
            print(f"  ollama: {model} nicht geladen ({status})")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

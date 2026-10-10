from pathlib import Path

import yaml


def test_minikube_keeps_ollama_and_uses_cluster_dns():
    root = Path(__file__).resolve().parents[1]
    spec = yaml.safe_load((root / "config/defaults/stack.yaml").read_text())["stack"]
    target = spec["targets"]["minikube"]
    ollama = spec["services"]["ollama"]

    assert target["services"].get("ollama", {}).get("k8s", ollama["k8s"]) is not None
    env = {**spec["k8s"]["env"], **target["k8s"]["env"]}
    assert env["KI_CFG_LLM__PROVIDERS__OLLAMA__BASE_URL"] == (
        "http://{services[ollama].probe_host}:{services[ollama].port}"
    )
    assert env["KI_STAGE"] == "dev-mk"
    assert ollama["k8s"]["volumes"]["models"]["mount"] == "/root/.ollama"
    assert ollama["post_start"] == ["{python}", "-m", "ki_knowledge.ollama_models"]

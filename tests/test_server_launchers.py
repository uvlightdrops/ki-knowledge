import os
from pathlib import Path
import runpy
import shutil
import signal
import socket
import subprocess
import sys
import time
import json
from urllib.error import URLError
from urllib.request import urlopen

import pytest
import yaml

from stackctl.spec import build_stack, deep_merge


ROOT = Path(__file__).resolve().parents[1]


def _wrapper_project(tmp_path, monkeypatch):
    root = tmp_path / "project with spaces"
    root.mkdir()
    wrapper = root / "kistack"
    shutil.copy2(ROOT / "kistack", wrapper)
    home = tmp_path / "home"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for utility in ("dirname", "readlink"):
        (bin_dir / utility).symlink_to(shutil.which(utility))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("PATH", str(bin_dir))
    return root, home, bin_dir


def _fake_stackctl(path, label, exit_code=0):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'#!/bin/sh\nprintf "%s\\n" "{label}" "$PWD" "$@"\nexit {exit_code}\n'
    )
    path.chmod(0o755)


def test_wrapper_prefers_central_tool_preserves_root_arguments_and_exit_code(tmp_path, monkeypatch):
    root, home, bin_dir = _wrapper_project(tmp_path, monkeypatch)
    _fake_stackctl(home / ".local/bin/stackctl", "central", exit_code=23)
    _fake_stackctl(bin_dir / "stackctl", "path")
    link = tmp_path / "knowledge-alias"
    link.symlink_to(root / "kistack")
    result = subprocess.run(
        [str(link), "--json", "logs", "service with spaces"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 23
    assert result.stdout.splitlines() == [
        "central", str(root), "--json", "logs", "service with spaces",
    ]
    assert not (root / ".venv").exists()


def test_wrapper_uses_path_when_no_central_tool_exists(tmp_path, monkeypatch):
    root, _, bin_dir = _wrapper_project(tmp_path, monkeypatch)
    _fake_stackctl(bin_dir / "stackctl", "path")
    result = subprocess.run(
        [str(root / "kistack"), "install"], cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["path", str(root), "install"]
    assert not (root / ".venv").exists()


def test_wrapper_missing_tool_fails_without_installing_anything(tmp_path, monkeypatch):
    root, _, _ = _wrapper_project(tmp_path, monkeypatch)
    result = subprocess.run(
        [str(root / "kistack"), "install"], capture_output=True, text=True,
    )
    assert result.returncode == 127
    assert "Zentrales stackctl fehlt" in result.stderr
    assert not (root / ".venv").exists()


@pytest.mark.parametrize("service", ["api", "django"])
def test_legacy_launcher_delegates_to_local_foreground(service, monkeypatch, tmp_path):
    calls = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "execv", lambda executable, args: calls.append((executable, args)))
    runpy.run_path(str(ROOT / "examples" / f"run_knowledge_{service}.py"), run_name="__main__")
    assert calls == [(str(ROOT / "kistack"), [str(ROOT / "kistack"), "-t", "local", "run", service])]


def test_api_legacy_environment_maps_to_config_without_overriding_explicit_values(monkeypatch):
    monkeypatch.setenv("KI_API_PORT", "9123")
    monkeypatch.setenv("KI_API_HOST", "0.0.0.0")
    monkeypatch.setenv("KI_API_RELOAD", "false")
    monkeypatch.setenv("KI_CFG_STACK__SERVICES__API__PORT", "9234")
    monkeypatch.delenv("KI_CFG_STACK__SERVICES__API__HOST", raising=False)
    monkeypatch.delenv("KI_CFG_STACK__SERVICES__API__ENV__UVICORN_RELOAD", raising=False)
    monkeypatch.setattr(os, "execv", lambda *args: None)
    runpy.run_path(str(ROOT / "examples" / "run_knowledge_api.py"), run_name="__main__")
    assert os.environ["KI_CFG_STACK__SERVICES__API__PORT"] == "9234"
    assert os.environ["KI_CFG_STACK__SERVICES__API__HOST"] == "0.0.0.0"
    assert os.environ["KI_CFG_STACK__SERVICES__API__ENV__UVICORN_RELOAD"] == "false"


def test_stack_defines_commands_without_example_scripts_and_reload_per_target():
    raw = yaml.safe_load((ROOT / "config/defaults/stack.yaml").read_text())["stack"]
    local = build_stack(raw, ROOT)
    api = local.service("api")
    assert api.command[1:] == [
        "-m", "uvicorn", "ki_knowledge.api.knowledge_app:app",
        "--host", "127.0.0.1", "--port", "8090",
    ]
    assert api.env["UVICORN_RELOAD"] == "true"
    assert local.service("django").prepare[1:] == ["manage.py", "migrate", "--no-input"]
    for service in local.services.values():
        assert not any("examples/run_knowledge" in item for item in service.command)
    prod = yaml.safe_load((ROOT / "config/stages/prod.yaml").read_text())["stack"]
    assert build_stack(deep_merge(raw, prod), ROOT).service("api").env["UVICORN_RELOAD"] == "false"
    for target in ("minikube", "k8s"):
        cluster = build_stack(raw, ROOT, target)
        assert cluster.service("api").k8s["env"]["UVICORN_RELOAD"] == "false"
        assert "--noreload" in cluster.service("django").k8s["command"]


def test_stages_use_current_core_provider_key():
    for path in (ROOT / "config/stages").glob("*.yaml"):
        llm = yaml.safe_load(path.read_text()).get("llm", {})
        assert "default_provider" not in llm
        assert llm["provider"] in {"ki", "ollama"}


def test_actual_api_runs_through_canonical_command_in_isolated_project(tmp_path):
    central = Path.home() / ".local/bin/stackctl"
    executable = str(central) if os.access(central, os.X_OK) else shutil.which("stackctl")
    if not executable:
        pytest.skip("Central stackctl user tool is not installed")
    (tmp_path / ".venv").symlink_to(sys.prefix, target_is_directory=True)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    api = yaml.safe_load((ROOT / "config/defaults/stack.yaml").read_text())["stack"]["services"]["api"]
    api.update(port=port, env={"UVICORN_RELOAD": "false"})
    (tmp_path / "pyproject.toml").write_text('[tool.stackctl]\nspec_file = "stack.yaml"\n')
    (tmp_path / "stack.yaml").write_text(yaml.safe_dump({"stack": {"services": {"api": api}}}))
    (tmp_path / "ki.yaml").write_text(yaml.safe_dump({
        "llm": {"provider": "mock"}, "knowledge": {"data_root": str(tmp_path / "data")},
    }))
    (tmp_path / "creds.yaml").write_text("{}\n")
    env = {
        key: value for key, value in os.environ.items()
        if key not in {"KI_STAGE", "KI_PROFILE"} and not key.startswith("KI_CFG_")
    }
    env["XDG_STATE_HOME"] = str(tmp_path / "state")
    env["KI_KNOWLEDGE_STORE_BACKEND"] = "sqlite"
    process = subprocess.Popen(
        [executable, "run", "api"], cwd=tmp_path, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and process.poll() is None:
            try:
                with urlopen(f"http://127.0.0.1:{port}/", timeout=1) as response:
                    assert json.load(response)["service"] == "ki-knowledge-api"
                    break
            except URLError:
                time.sleep(0.1)
        else:
            process.terminate()
            output, _ = process.communicate(timeout=10)
            pytest.fail(f"Actual API failed to become ready: {output}")
        process.send_signal(signal.SIGINT)
        output, _ = process.communicate(timeout=15)
        assert process.returncode == 130, output
        assert not (tmp_path / "var/run/api.pid").exists()
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)

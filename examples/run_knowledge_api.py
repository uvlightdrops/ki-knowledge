"""Legacy alias for the central ``stackctl -t local run api`` command."""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    for old, new in {
        "KI_API_HOST": "KI_CFG_STACK__SERVICES__API__HOST",
        "KI_API_PORT": "KI_CFG_STACK__SERVICES__API__PORT",
        "KI_API_RELOAD": "KI_CFG_STACK__SERVICES__API__ENV__UVICORN_RELOAD",
    }.items():
        if old in os.environ:
            os.environ.setdefault(new, os.environ[old])
    os.execv(str(PROJECT_ROOT / "kistack"), [str(PROJECT_ROOT / "kistack"), "-t", "local", "run", "api"])

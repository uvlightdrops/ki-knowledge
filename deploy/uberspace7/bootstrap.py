#!/usr/bin/env python3
"""Install the project and its declared siblings without changing host services."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stackctl-source", type=Path, required=True,
                        help="Existing, trusted stackctl checkout with supervisord support")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 12):
        parser.error("Use python3.12 or newer explicitly.")
    source = args.stackctl_source.expanduser().resolve()
    if not (source / "pyproject.toml").is_file() or not (source / ".git").exists():
        parser.error("--stackctl-source must be a trusted stackctl Git checkout.")
    if tomllib.loads((source / "pyproject.toml").read_text()).get("project", {}).get("name") != "stackctl":
        parser.error("--stackctl-source is not the stackctl project.")
    python = ROOT / ".venv/bin/python"
    try:
        if not python.exists():
            if (ROOT / ".venv").exists():
                parser.error("Existing .venv is incomplete; repair it explicitly instead of overwriting it.")
            subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True)
        else:
            subprocess.run([str(python), "-c",
                            "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"],
                           check=True)
        subprocess.run([str(python), "-m", "pip", "install", "-e", str(source)],
                       cwd=ROOT, check=True)
        env = dict(os.environ, STACKCTL_EXTRAS="uberspace7", KI_STAGE="prod-uberspace7")
        subprocess.run([str(python), "-m", "stackctl", "install"], cwd=ROOT, env=env, check=True)
        subprocess.run([str(python), "-m", "pip", "check"], cwd=ROOT, check=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        print(f"bootstrap: installation failed ({type(exc).__name__}); no services configured.",
              file=sys.stderr)
        return 1
    print("Installed. Configure runtime.yaml / private creds.yaml, then run deploy.py check.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

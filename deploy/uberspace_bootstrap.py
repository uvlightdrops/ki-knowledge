"""Standard-library-only bootstrap shared by the U7 and U8 entry points."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import tomllib


class UberspaceBootstrap:
    def __init__(self, root: Path, version: int):
        if version not in (7, 8):
            raise ValueError("Supported Uberspace versions: 7, 8.")
        self.ROOT = root.resolve()
        self.name = f"uberspace{version}"

    def main(self, argv: list[str] | None = None) -> int:
        parser = argparse.ArgumentParser(description="Install dependencies without changing host services.")
        parser.add_argument("--stackctl-source", type=Path, required=True,
                            help="Existing, trusted stackctl checkout with the required platform adapter")
        args = parser.parse_args(argv)
        if sys.version_info < (3, 12):
            parser.error("Use python3.12 or newer explicitly.")
        source = args.stackctl_source.expanduser().resolve()
        if not (source / "pyproject.toml").is_file() or not (source / ".git").exists():
            parser.error("--stackctl-source must be a trusted stackctl Git checkout.")
        if tomllib.loads((source / "pyproject.toml").read_text()).get("project", {}).get("name") != "stackctl":
            parser.error("--stackctl-source is not the stackctl project.")
        python = self.ROOT / ".venv/bin/python"
        try:
            if not python.exists():
                if (self.ROOT / ".venv").exists():
                    parser.error("Existing .venv is incomplete; repair it explicitly instead of overwriting it.")
                subprocess.run([sys.executable, "-m", "venv", str(self.ROOT / ".venv")], check=True)
            else:
                subprocess.run([str(python), "-c",
                                "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)"],
                               check=True)
            subprocess.run([str(python), "-m", "pip", "install", "-e", str(source)],
                           cwd=self.ROOT, check=True)
            env = dict(os.environ, STACKCTL_EXTRAS=self.name, KI_STAGE=f"prod-{self.name}")
            subprocess.run([str(python), "-m", "stackctl", "install"], cwd=self.ROOT, env=env, check=True)
            subprocess.run([str(python), "-m", "pip", "check"], cwd=self.ROOT, check=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"bootstrap: installation failed ({type(exc).__name__}); no services configured.",
                  file=sys.stderr)
            return 1
        print("Installed. Configure runtime.yaml / private creds.yaml, then run deploy.py check.")
        return 0

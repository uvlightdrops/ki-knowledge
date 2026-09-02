from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, "manage.py", "migrate"],
            cwd=str(PROJECT_ROOT),
        )
        or subprocess.call(
            [sys.executable, "manage.py", "runserver"],
            cwd=str(PROJECT_ROOT),
        )
    )

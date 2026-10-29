"""Legacy alias for the central ``stackctl -t local run django`` command."""

from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    os.execv(str(PROJECT_ROOT / "kistack"), [str(PROJECT_ROOT / "kistack"), "-t", "local", "run", "django"])

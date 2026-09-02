"""Launch the Phase-D Streamlit knowledge UI."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_ROOT / "examples" / "knowledge_streamlit_app.py"


if __name__ == "__main__":
    raise SystemExit(
        subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(APP_PATH)],
            cwd=str(PROJECT_ROOT),
        )
    )

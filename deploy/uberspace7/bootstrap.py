#!/usr/bin/env python3
"""Bootstrap the Uberspace 7 project environment without changing host services."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "deploy"))

from uberspace_bootstrap import UberspaceBootstrap

bootstrap = UberspaceBootstrap(ROOT, 7)

if __name__ == "__main__":
    raise SystemExit(bootstrap.main())

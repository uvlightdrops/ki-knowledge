#!/usr/bin/env python3
"""Uberspace 7 deployment; lifecycle operations always delegate to stackctl."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from ki_knowledge.deployment.uberspace import UberspaceDeployment

deployment = UberspaceDeployment(ROOT, 7)

if __name__ == "__main__":
    raise SystemExit(deployment.main())

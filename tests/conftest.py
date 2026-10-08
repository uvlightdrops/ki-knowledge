from __future__ import annotations

import os


def pytest_configure(config):
    os.environ.setdefault("KI_KNOWLEDGE_STORE_BACKEND", "sqlite")

"""Helpers for PDF path and source-id normalization."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.config_runtime import knowledge_pdf_root


def _pdf_type_root() -> Path:
    override = os.getenv("KNOWLEDGE_PDF_ROOT", "").strip()
    if override:
        return Path(override).expanduser()
    legacy = os.getenv("KICLI_PDF_ROOT", "").strip()
    if legacy:
        return Path(legacy).expanduser()
    return knowledge_pdf_root(Config.from_env())


def _normalize_domain(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "default"
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-_")
    return normalized or "default"


def _pdf_domain_root(domain: str | None = None) -> Path:
    resolved = _normalize_domain(domain)
    base = _pdf_type_root()
    if base.exists() and base.is_dir():
        for child in base.iterdir():
            if child.is_dir() and _normalize_domain(child.name) == resolved:
                return child
    return base / resolved


def pdf_relative_source_path(pdf_path: str | Path, domain: str | None = None) -> str:
    path = Path(pdf_path).expanduser()
    root = _pdf_domain_root(domain)

    for candidate in (path, path.resolve(strict=False)):
        try:
            relative = candidate.relative_to(root)
        except ValueError:
            try:
                relative = candidate.relative_to(root.resolve(strict=False))
            except ValueError:
                continue
        if relative.parts and str(relative) != ".":
            return relative.as_posix()

    return path.name


def pdf_source_id(pdf_path: str | Path, domain: str | None = None) -> str:
    return f"pdf:{pdf_relative_source_path(pdf_path, domain=domain)}"

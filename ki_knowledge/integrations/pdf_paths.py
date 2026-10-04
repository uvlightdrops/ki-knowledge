"""Helpers for PDF path and source-id normalization."""

from __future__ import annotations

import re
from pathlib import Path

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.data_layout import MIX, PDF, DataLayout


def _normalize_domain(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if not normalized:
        return "default"
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized).strip("-_")
    return normalized or "default"


def _domain_dir(layout: DataLayout, source_type: str, resolved: str) -> Path:
    for name in layout.source_domain_names(source_type):
        if _normalize_domain(name) == resolved:
            return layout.source_dir(source_type, name)
    return layout.source_dir(source_type, resolved)


def _pdf_domain_roots(domain: str | None = None) -> list[tuple[Path, str]]:
    """PDF-capable source folders of a domain with the prefix used in source ids."""
    resolved = _normalize_domain(domain)
    layout = DataLayout.from_config(Config.from_env())
    return [(_domain_dir(layout, PDF, resolved), ""), (_domain_dir(layout, MIX, resolved), "mix/")]


def _pdf_domain_root(domain: str | None = None) -> Path:
    return _pdf_domain_roots(domain)[0][0]


def pdf_relative_source_path(pdf_path: str | Path, domain: str | None = None) -> str:
    """Path relative to the domain's ``pdf`` folder; PDFs from ``mix`` get a ``mix/`` prefix."""
    path = Path(pdf_path).expanduser()
    for root, prefix in _pdf_domain_roots(domain):
        for candidate in (path, path.resolve(strict=False)):
            for base in (root, root.resolve(strict=False)):
                try:
                    relative = candidate.relative_to(base)
                except ValueError:
                    continue
                if relative.parts and str(relative) != ".":
                    return prefix + relative.as_posix()
    return path.name


def pdf_source_id(pdf_path: str | Path, domain: str | None = None) -> str:
    return f"pdf:{pdf_relative_source_path(pdf_path, domain=domain)}"

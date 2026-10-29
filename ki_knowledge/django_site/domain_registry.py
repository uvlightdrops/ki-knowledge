"""Domain registry lifecycle, defaults, source scope and domain inventory."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any
import logging
import os
import shutil
import sqlite3

from ki_knowledge.django_site.domain_paths import invalidate_domain_summary_cache
from ki_knowledge.django_site.jira_workflow import jira_cache_db_path, jira_csv_path
from ki_knowledge.django_site.source_workflow import discover_ontology_files, mixed_files_summary
from ki_knowledge.integrations.jira_cache import JiraIssueCache
from ki_knowledge.integrations.semantic_terms import SemanticTermStore
from ki_knowledge.integrations.sql_backend import connect
from ki_knowledge.services.domain_paths import (
    data_layout,
    data_root,
    domain_jira_dir,
    domain_label,
    domain_markdown_dir,
    domain_ontology_dir,
    domain_pdf_dir,
    domain_source_roots,
    domain_state_paths,
    infer_domain_from_path,
    normalize_registry_domain,
)
from ki_knowledge.ui.knowledge_api_client import discover_markdown_files

from .knowledge_summary import _domain_scoped_sources
from .source_workflow import discover_pdf_files


def _infer_domain_from_path(path: Path | str | None) -> str | None:
    return infer_domain_from_path(path)


def data_dir(domain: str | None = None) -> Path:
    return domain_markdown_dir(domain)


def available_data_domains() -> list[str]:
    domains = {normalize_semantic_domain(name) for name in data_layout().domain_names()}
    result = sorted(item for item in domains if item)
    _register_domains(result)
    return result


def _register_domains(slugs: list[str]) -> None:
    """Backfill the shared Domain registry with slugs found by directory scans.

    Imported lazily and guarded: this service layer is also used by the
    plain FastAPI app (tests/test_jira_api.py) without Django settings
    configured at all, so any failure to reach the Django app registry
    (ImproperlyConfigured/AppRegistryNotReady) is treated as "registry not
    available here" rather than a hard error - domains still get registered
    normally whenever this runs inside the Django app.
    """

    try:
        from django.apps import apps as django_apps

        if not django_apps.ready:
            return
        from ki_knowledge.django_site.infosite_models import ensure_domain_registered
    except Exception:
        return

    for slug in slugs:
        ensure_domain_registered(slug)


def default_semantic_domain() -> str:
    env_override = os.getenv("KNOWLEDGE_DEFAULT_DOMAIN", "").strip()
    if env_override:
        return normalize_semantic_domain(env_override)
    domains = available_data_domains()
    return domains[0] if domains else "default"


def normalize_semantic_domain(value: str | None) -> str:
    return normalize_registry_domain(value)


def domain_db_paths(domain: str | None = None) -> dict[str, Path]:
    return domain_state_paths(normalize_semantic_domain(domain or default_semantic_domain()))


def semantic_domains() -> list[str]:
    domains = set(available_data_domains())
    domains.add(default_semantic_domain())
    return sorted(domains)


def create_semantic_domain(domain: str | None) -> dict[str, Any]:
    from .prompt_library import prompt_library_dir

    raw = (domain or "").strip()
    if not raw:
        raise ValueError("domain missing")
    resolved = normalize_semantic_domain(raw)
    if resolved == "default" and raw.lower() != "default":
        raise ValueError("invalid domain name")
    md_dir = domain_markdown_dir(resolved)
    jira_dir = domain_jira_dir(resolved)
    owl_dir = domain_ontology_dir(resolved)
    prompt_dir = prompt_library_dir(resolved)
    md_dir.mkdir(parents=True, exist_ok=True)
    jira_dir.mkdir(parents=True, exist_ok=True)
    owl_dir.mkdir(parents=True, exist_ok=True)
    prompt_dir.mkdir(parents=True, exist_ok=True)
    _register_domains([resolved])
    return {
        "domain": resolved,
        "markdown_dir": str(md_dir),
        "jira_dir": str(jira_dir),
        "ontology_dir": str(owl_dir),
        "prompt_dir": str(prompt_dir),
        "created": True,
    }


def semantic_domain_states() -> list[dict[str, Any]]:
    from .pdf_jobs import get_pdf_job_stats

    states: list[dict[str, Any]] = []
    for domain in semantic_domains():
        paths = domain_db_paths(domain)
        markdown_dir = domain_markdown_dir(domain)
        jira_dir = domain_jira_dir(domain)
        ontology_dir = domain_ontology_dir(domain)
        pdf_dir = domain_pdf_dir(domain)
        cache_path = paths["cache_db"]
        graph_path = paths["graph_db"]
        csv_path = jira_csv_path(domain)
        markdown_files = len(discover_markdown_files(markdown_dir))
        jira_csv_files = len(sorted(path for path in jira_dir.glob("*.csv") if jira_dir.exists() and jira_dir.is_dir() and path.is_file()))
        ontology_files = len(discover_ontology_files(ontology_dir))
        pdf_files = len(discover_pdf_files(pdf_dir))
        mix = mixed_files_summary(domain)
        pdf_job_stats = get_pdf_job_stats(domain)
        cache_exists = cache_path.exists()
        graph_exists = graph_path.exists()
        issue_count = 0
        totals = {"terms": 0, "facts": 0, "relations": 0, "candidates": 0, "record_term_links": 0}
        if cache_exists:
            try:
                issue_count = JiraIssueCache(str(cache_path)).issue_count()
            except sqlite3.Error:
                issue_count = 0
        try:
            totals = SemanticTermStore(semantic_target(domain)).monitoring_snapshot(recent_limit=1).get("totals", totals)
        except Exception:
            totals = totals
        states.append(
            {
                "domain": domain,
                "domain_label": domain_label(domain),
                "cache_db": str(cache_path),
                "graph_db": str(graph_path),
                "markdown_dir": str(markdown_dir),
                "jira_dir": str(jira_dir),
                "ontology_dir": str(ontology_dir),
                "pdf_dir": str(pdf_dir),
                "mix_dir": str(mix["dir"]),
                "mix_files": mix["total"],
                "mix_counts": mix["counts"],
                "csv_path": csv_path,
                "markdown_files": markdown_files,
                "jira_csv_files": jira_csv_files,
                "ontology_files": ontology_files,
                "pdf_files": pdf_files,
                "has_md_source": markdown_files > 0 or markdown_dir.exists(),
                "has_jira_source": bool(csv_path),
                "has_owl_source": ontology_files > 0,
                "has_pdf_source": pdf_files > 0,
                "has_mix_source": mix["total"] > 0,
                "pdf_jobs": pdf_job_stats,
                "pdf_jobs_active": pdf_job_stats.get("processing", 0) > 0,
                "cache_exists": cache_exists,
                "graph_exists": graph_exists,
                "issues": issue_count,
                "terms": int(totals.get("terms", 0) or 0),
                "facts": int(totals.get("facts", 0) or 0),
            }
        )
    return states


def _domain_blockers(resolved: str, domain_root: Path) -> list[str]:
    """Reasons that protect a domain from removal: real source files, imported sources, projects."""
    blockers: list[str] = []
    if domain_root.is_dir():
        state_dir = data_layout().domain_state_dir(resolved)
        entries = [path for path in domain_root.rglob("*") if state_dir not in path.parents]
        files = [path for path in entries if path.is_file() and not path.is_symlink()]
        links = [path for path in entries if path.is_symlink()]
        if files:
            blockers.append(f"{len(files)} Quelldatei(en) im Domain-Verzeichnis")
        if links:
            blockers.append(f"{len(links)} verlinkte Quelle(n)")
    from ki_knowledge.django_site.knowledge_summary import _domain_scoped_sources

    sources = len(list(_domain_scoped_sources(resolved)))
    if sources:
        blockers.append(f"{sources} importierte Quelle(n)")
    try:
        from ki_knowledge.django_site.infosite_models import InfoSiteProject

        projects = InfoSiteProject.objects.filter(domain=resolved).count()
    except Exception:  # Registry not reachable outside Django (FastAPI tests).
        projects = 0
    if projects:
        blockers.append(f"{projects} InfoSite-Projekt(e)")
    return blockers


def delete_semantic_domain(domain: str | None) -> dict[str, Any]:
    """Remove an empty domain: derived DBs, PostgreSQL semantic schema, stage rows, registry and directory.

    Domains that still hold source files, imported sources or InfoSite projects
    are refused; their content has to be removed first.
    """
    raw = (domain or "").strip()
    if not raw:
        raise ValueError("domain missing")
    resolved = normalize_semantic_domain(raw)
    if resolved == "default":
        raise ValueError("Die Domain 'default' kann nicht entfernt werden.")
    known = resolved in set(available_data_domains())
    domain_root = data_layout().domain_root(resolved)
    try:
        from ki_knowledge.django_site.infosite_models import Domain

        registry = Domain.objects.filter(slug=resolved)
        registered = registry.exists()
    except Exception:  # Registry not reachable outside Django (FastAPI tests).
        registry, registered = None, False
    if not known and not registered:
        raise ValueError(f"Domain nicht gefunden: {resolved}")
    blockers = _domain_blockers(resolved, domain_root)
    if blockers:
        raise ValueError(f"Domain '{resolved}' enthält noch Daten: {', '.join(blockers)}")

    removed: list[str] = []
    paths = domain_db_paths(resolved)
    for key in ("cache_db", "graph_db", "cypher_path"):
        path = paths.get(key)
        if isinstance(path, Path) and path.exists():
            path.unlink()
            removed.append(str(path))
    target = semantic_target(resolved)
    if target.is_postgres and target.postgres_schema:
        with connect(target) as conn:
            exists = conn.execute(
                "SELECT 1 FROM information_schema.schemata WHERE schema_name = ?", (target.postgres_schema,)
            ).fetchone()
            if exists:
                conn.execute(f'DROP SCHEMA "{target.postgres_schema}" CASCADE')
                removed.append(f"postgres:{target.postgres_schema}")
    try:
        from ki_knowledge.django_site.book_pipeline import stage_store

        stage_store().delete_missing(resolved, [])
    except Exception:  # The stage table is optional for domains that never ran the pipeline.
        logging.getLogger(__name__).debug("no pipeline stages removed for %s", resolved, exc_info=True)
    if registry is not None and registered:
        registry.delete()
        removed.append(f"registry:{resolved}")
    if domain_root.is_dir():
        shutil.rmtree(domain_root)
        removed.append(str(domain_root))
    invalidate_domain_summary_cache(resolved)
    return {"domain": resolved, "removed": removed}


def data_layout_snapshot(domain: str | None = None) -> dict[str, str]:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return {
        "data_root": str(data_root()),
        "layout_version": str(data_layout().version),
        "active_markdown_dir": str(domain_markdown_dir(resolved)),
        "active_jira_dir": str(domain_jira_dir(resolved)),
        "active_ontology_dir": str(domain_ontology_dir(resolved)),
    }


@contextmanager
def _domain_env(domain: str | None):
    paths = domain_db_paths(domain)
    cache_path = str(paths["cache_db"])
    graph_path = str(paths["graph_db"])
    cypher_path = str(paths["cypher_path"]) if paths.get("cypher_path") else ""
    previous = {
        k: os.environ.get(k) 
        for k in ("JIRA_CACHE_DB", "JIRA_GRAPH_DB", "JIRA_GRAPH_CYPHER_PATH")
    }
    os.environ["JIRA_CACHE_DB"] = cache_path
    os.environ["JIRA_GRAPH_DB"] = graph_path
    if cypher_path:
        os.environ["JIRA_GRAPH_CYPHER_PATH"] = cypher_path
    elif "JIRA_GRAPH_CYPHER_PATH" in os.environ:
        del os.environ["JIRA_GRAPH_CYPHER_PATH"]
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _is_under_dir(path: Path, root: Path) -> bool:
    try:
        path_resolved = path.expanduser().resolve()
    except OSError:
        path_resolved = path.expanduser()
    try:
        root_resolved = root.expanduser().resolve()
    except OSError:
        root_resolved = root.expanduser()
    if path_resolved == root_resolved:
        return True
    return str(path_resolved).startswith(f"{root_resolved}{os.sep}")


def source_in_domain(source: Any, domain: str | None = None) -> bool:
    location = Path(str(getattr(source, "location", ""))).expanduser()
    return any(_is_under_dir(location, root) for root in domain_source_roots(domain))


def _source_matches_domain_legacy(source: Any, domain: str | None = None) -> bool:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    location = str(getattr(source, "location", "") or "").lower().replace("\\", "/")
    marker = f"/{resolved}/"
    if marker in location:
        return True
    metadata = getattr(source, "metadata", {}) or {}
    meta_domain = normalize_semantic_domain(str(metadata.get("domain", "") or ""))
    if meta_domain and meta_domain == resolved:
        return True
    return False


def semantic_target(domain: str | None = None):
    """Semantic store target for a domain, resolved like the domain's cache path."""
    from ki_knowledge.config_runtime import semantic_store_target

    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    return semantic_store_target(resolved, sqlite_path=jira_cache_db_path(domain))


def jira_graph_db_path(domain: str | None = None) -> str:
    resolved = normalize_semantic_domain(domain or default_semantic_domain())
    domain_key = f"JIRA_GRAPH_DB_{resolved.upper().replace('-', '_')}"
    explicit = os.getenv(domain_key, "").strip() or os.getenv("JIRA_GRAPH_DB", "").strip()
    if explicit:
        return str(Path(explicit).expanduser())
    return str(domain_db_paths(domain)["graph_db"])

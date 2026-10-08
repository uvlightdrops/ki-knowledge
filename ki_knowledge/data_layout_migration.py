"""Plan and execute data-root layout migrations.

Migrations are fully planned before execution. Relative links that would stop
resolving after a move and any occupied destination block the whole plan.
SQLite path references are counted read-only during planning and rewritten
only after database files have reached their destination.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from urllib.parse import quote

from ki_knowledge.data_layout import (
    _GLOBAL_FILES,
    _HOME_STATE_FILES,
    _V1_OUTPUT_DIR,
    DOMAIN_STATE_FILES,
    JIRA,
    LAYOUT_VERSION,
    MARKDOWN,
    MIX,
    ONTOLOGY,
    PDF,
    DataLayout,
    read_layout_version,
    source_type_dir_name,
)

MIGRATION_LOG_NAME = "layout-migration.jsonl"
_SQLITE_SIDECARS = ("-journal", "-wal", "-shm")
_DERIVED_FILE_NAMES = frozenset(name for pair in DOMAIN_STATE_FILES.values() for name in pair)
_RESERVED_DOMAIN_NAMES = frozenset({
    "domains", "system", "archive", "data_out", "sources", "derived", "output",
    "md", "pdf", "jira", "owl", "mix", "rdf",
})

# (database key, table, column); JSON columns are recursively inspected so
# provenance paths are covered along with the direct source-path columns.
_PATH_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("pdf_jobs_db", "pdf_import_jobs", "pdf_path"),
    ("pdf_jobs_db", "pdf_import_jobs", "result_json"),
    ("django_db", "django_site_sourcedocument", "file_path"),
    ("django_db", "django_site_generateddocument", "file_path"),
    ("django_db", "django_site_infositemappingrule", "source_path"),
    ("django_db", "django_site_infositeproject", "source_directory"),
    ("django_db", "django_site_infositeproject", "output_dir"),
    ("django_db", "django_site_infositeproject", "site_structure"),
    ("django_db", "django_site_syncrun", "summary_json"),
    ("knowledge_db", "knowledge_sources", "location"),
    ("knowledge_db", "knowledge_sources", "metadata_json"),
    ("knowledge_db", "knowledge_blocks", "source_path"),
    ("knowledge_db", "knowledge_blocks", "metadata_json"),
    ("knowledge_db", "knowledge_relations", "metadata_json"),
    ("knowledge_db", "knowledge_artifacts", "metadata_json"),
    ("knowledge_db", "knowledge_artifacts", "content"),
    ("block_store_db", "knowledge_sources", "location"),
    ("block_store_db", "knowledge_sources", "metadata_json"),
    ("block_store_db", "knowledge_blocks", "source_path"),
    ("block_store_db", "knowledge_blocks", "metadata_json"),
    ("block_store_db", "knowledge_relations", "metadata_json"),
    ("block_store_db", "knowledge_artifacts", "metadata_json"),
    ("block_store_db", "knowledge_artifacts", "content"),
    ("pipeline_jobs_db", "distributed_sync_jobs", "payload_json"),
    ("pipeline_jobs_db", "distributed_sync_jobs", "result_json"),
    ("pipeline_jobs_db", "knowledge_extraction_jobs", "result_json"),
)


@dataclass
class Operation:
    """One filesystem step. ``kind`` is ``move``, ``relink``, ``rmdir`` or ``write_version``."""

    kind: str
    src: Path | None = None
    dst: Path | None = None
    note: str = ""
    link_target: Path | None = None

    def describe(self) -> str:
        if self.kind in ("move", "relink"):
            text = f"{self.kind:<7} {self.src} -> {self.dst}"
        elif self.kind == "rmdir":
            text = f"rmdir   {self.src}"
        else:
            text = f"write   {self.dst}"
        return f"{text}  ({self.note})" if self.note else text


@dataclass
class MigrationPlan:
    root: Path
    home_state_dir: Path
    source_version: int = 1
    target_version: int = LAYOUT_VERSION
    operations: list[Operation] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    path_prefixes: list[tuple[Path, Path]] = field(default_factory=list)
    db_rows_to_rewrite: dict[str, int] = field(default_factory=dict)
    database_paths: dict[str, tuple[Path, Path]] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.conflicts

    @property
    def moves(self) -> list[Operation]:
        return [op for op in self.operations if op.kind in ("move", "relink")]


def _domain_key(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", name.strip().lower()).strip("-._")
    return normalized or name


def _is_empty_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink() and not any(path.iterdir())


def _escaping_relative_links(tree: Path) -> list[Path]:
    """Relative symlinks inside ``tree`` whose target lies outside of it."""
    found = []
    tree_abs = Path(os.path.abspath(tree))
    for dirpath, dirnames, filenames in os.walk(tree, followlinks=False):
        for name in (*dirnames, *filenames):
            entry = Path(dirpath) / name
            if not entry.is_symlink():
                continue
            target = os.readlink(entry)
            if os.path.isabs(target):
                continue
            resolved = Path(os.path.normpath(entry.parent / target))
            if not resolved.is_relative_to(tree_abs):
                found.append(entry)
    return found


def _internal_absolute_links(tree: Path, root: Path) -> list[Path]:
    """Absolute links into the migrating root that would keep their old path."""
    found = []
    root_abs = Path(os.path.abspath(root))
    for dirpath, dirnames, filenames in os.walk(tree, followlinks=False):
        for name in (*dirnames, *filenames):
            entry = Path(dirpath) / name
            if not entry.is_symlink():
                continue
            target = os.readlink(entry)
            if not os.path.isabs(target):
                continue
            resolved = Path(os.path.abspath(target))
            if resolved.is_relative_to(root_abs):
                found.append(entry)
    return found


def _db_accessors(layout: DataLayout, home_state_dir: Path | None = None) -> dict[str, Path]:
    paths = {
        "knowledge_db": layout.knowledge_db_path(),
        "django_db": layout.django_db_path(),
        "pdf_jobs_db": layout.pdf_jobs_db_path(),
        "jira_cache_db": layout.global_jira_cache_db_path(),
        "jira_graph_db": layout.global_jira_graph_db_path(),
    }
    if layout.is_domain_first:
        paths["pipeline_jobs_db"] = layout.pipeline_jobs_db_path()
        paths["block_store_db"] = layout.block_store_db_path()
    else:
        home = home_state_dir or layout.home_state_dir()
        paths["pipeline_jobs_db"] = home / _HOME_STATE_FILES["pipeline_jobs_db"][0]
        paths["block_store_db"] = home / _HOME_STATE_FILES["block_store_db"][0]
    return paths


class _Planner:
    def __init__(self, root: Path, home_state_dir: Path, target_version: int) -> None:
        self.root = root
        self.home_state_dir = home_state_dir
        self.target_version = target_version
        self.plan = MigrationPlan(
            root=root,
            home_state_dir=home_state_dir,
            target_version=target_version,
        )
        self._domain_names: dict[str, str] = {}
        self._targets: set[Path] = set()

    @property
    def new(self) -> DataLayout:
        return DataLayout(self.root, version=self.target_version)

    def domain(self, dir_name: str) -> str:
        """Merge differently-cased source domain names into one direct domain."""
        name = self._domain_names.setdefault(_domain_key(dir_name), _domain_key(dir_name))
        if name.casefold() in _RESERVED_DOMAIN_NAMES:
            self.plan.conflicts.append(
                f"domain name {dir_name!r} is reserved by the direct-domain layout"
            )
        return name

    def move(
        self,
        src: Path,
        dst: Path,
        note: str = "",
        *,
        rewrite_paths: bool = True,
        path_src: Path | None = None,
    ) -> None:
        kind = "move"
        inspect = path_src or src
        link_target = None
        if inspect.is_symlink():
            target = os.readlink(inspect)
            if not os.path.isabs(target):
                resolved_target = Path(os.path.abspath(inspect.parent / target))
                if not resolved_target.exists():
                    self.plan.conflicts.append(f"relative symlink has no resolvable target: {inspect} -> {target}")
                kind = "relink"
                link_target = resolved_target
                note = note or "relative symlink recreated against its resolved target"
            elif Path(os.path.abspath(target)).is_relative_to(Path(os.path.abspath(self.root))):
                self.plan.conflicts.append(
                    f"absolute symlink points inside the migrating root and may break after moving: {inspect}"
                )
        elif inspect.is_dir():
            for link in _escaping_relative_links(inspect):
                self.plan.conflicts.append(
                    f"relative symlink escapes moved tree and cannot be preserved safely: {link}"
                )
            for link in _internal_absolute_links(inspect, self.root):
                self.plan.conflicts.append(
                    f"absolute symlink points inside the migrating root and may break after moving: {link}"
                )
        if os.path.lexists(dst):
            self.plan.conflicts.append(f"target already exists: {dst}")
        if dst in self._targets:
            self.plan.conflicts.append(f"two sources map to the same target: {dst}")
        self._targets.add(dst)
        self.plan.operations.append(Operation(kind, src, dst, note, link_target))
        if rewrite_paths:
            self.plan.path_prefixes.append((path_src or src, dst))

    def rmdir(self, path: Path, note: str = "") -> None:
        self.plan.operations.append(Operation("rmdir", src=path, note=note))

    def archive(self, path: Path, category: str) -> None:
        self.plan.warnings.append(f"unexpected data moved to archive: {path}")
        self.move(path, self.new.archive_dir() / "v1" / category / path.name, "unexpected file")

    def type_dir(self, name: str) -> Path | None:
        base = self.root / name
        if base.is_symlink():
            self.plan.conflicts.append(f"{base} is a symlink; move its content manually first")
            return None
        return base if base.is_dir() else None

    def plan_v1_sources(self, source_type: str) -> None:
        type_dir_name = source_type_dir_name(source_type)
        base = self.type_dir(type_dir_name)
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink() or child.is_dir():
                name = self.domain(child.name)
                note = f"symlink -> {os.readlink(child)}" if child.is_symlink() else ("empty" if _is_empty_dir(child) else "")
                self.move(child, self.new.source_dir(source_type, name), note)
            else:
                self.archive(child, type_dir_name)
        self.rmdir(base, "type dir")

    def plan_v1_jira(self) -> None:
        base = self.type_dir(source_type_dir_name(JIRA))
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink():
                name = self.domain(child.name)
                self.move(child, self.new.source_dir(JIRA, name), f"symlink -> {os.readlink(child)}")
            elif child.is_dir():
                name = self.domain(child.name)
                entries = sorted(child.iterdir())
                self.plan.path_prefixes.append(
                    (child, self.new.source_dir(JIRA, name))
                )
                if not entries:
                    self.move(child, self.new.source_dir(JIRA, name), "empty")
                    continue
                for entry in entries:
                    if entry.name in _DERIVED_FILE_NAMES and entry.is_file():
                        self.move(entry, self.new.domain_state_dir(name) / entry.name, "derived")
                    else:
                        self.move(entry, self.new.source_dir(JIRA, name, entry.name))
                self.rmdir(child)
            else:
                self.archive(child, "jira")
        self.rmdir(base, "type dir")

    def plan_v1_output(self) -> None:
        base = self.type_dir(_V1_OUTPUT_DIR)
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink() or child.is_dir():
                self.move(child, self.new.output_dir(self.domain(child.name)))
            else:
                self.archive(child, _V1_OUTPUT_DIR)
        self.rmdir(base, "type dir")

    def plan_v2_domains(self) -> None:
        old_domains = self.root / "domains"
        if old_domains.is_symlink():
            self.plan.conflicts.append(f"{old_domains} is a symlink; migrate its contents manually first")
            return
        if not old_domains.is_dir():
            return
        domains = sorted(child for child in old_domains.iterdir() if child.is_dir() or child.is_symlink())
        for entry in sorted(old_domains.iterdir()):
            if not entry.is_dir() and not entry.is_symlink():
                self.plan.warnings.append(f"unexpected file moved to archive: {entry}")
                self.move(entry, self.new.archive_dir() / "v2" / "domains" / entry.name, "unexpected file")
        for domain_path in domains:
            if domain_path.is_symlink():
                self.plan.conflicts.append(f"domain directory is a symlink; move its contents manually first: {domain_path}")
                continue
            name = self.domain(domain_path.name)
            target_root = self.new.domain_root(name)
            original_root = domain_path
            self.move(domain_path, target_root, path_src=original_root)
            original_sources = original_root / "sources"
            moved_sources = target_root / "sources"
            if original_sources.is_symlink():
                self.plan.conflicts.append(f"unexpected symlinked sources directory: {original_sources}")
                continue
            if original_sources.is_dir():
                for source_path in sorted(original_sources.iterdir()):
                    fmt = source_path.name
                    if fmt not in {source_type_dir_name(t) for t in (MARKDOWN, PDF, JIRA, ONTOLOGY, MIX)}:
                        self.plan.conflicts.append(f"unknown source format directory cannot be placed at v3 root: {source_path}")
                        continue
                    if source_path.is_symlink() and not os.path.isabs(os.readlink(source_path)):
                        self.plan.conflicts.append(
                            f"relative source-directory symlink would change meaning while flattening: {source_path}"
                        )
                    destination = target_root / fmt
                    original_source = original_root / "sources" / fmt
                    self.move(moved_sources / fmt, destination, path_src=original_source)
                self.rmdir(moved_sources)
        self.rmdir(old_domains)

    def plan_global_files(self) -> None:
        if self.plan.source_version >= 2:
            return
        system_dir = self.new.system_dir()
        old_v1 = DataLayout(self.root, version=1)
        old_db_paths = _db_accessors(old_v1, self.home_state_dir)
        new_db_paths = _db_accessors(self.new, self.home_state_dir)
        self.plan.database_paths = {
            key: (old_db_paths[key], new_db_paths[key])
            for key in new_db_paths
        }

        def move_db(src: Path, dst: Path, note: str) -> None:
            if src.is_symlink():
                self.plan.conflicts.append(f"database path is a symlink; refusing to inspect or rewrite it: {src}")
                return
            if src.exists():
                self.move(src, dst, note, rewrite_paths=False)
                for suffix in _SQLITE_SIDECARS:
                    sidecar = Path(f"{src}{suffix}")
                    if sidecar.exists():
                        self.move(sidecar, Path(f"{dst}{suffix}"), "sqlite sidecar", rewrite_paths=False)

        for v1_name, v3_name in _GLOBAL_FILES.values():
            move_db(self.root / v1_name, system_dir / v3_name, "global state")
        for v1_name, v3_name in _HOME_STATE_FILES.values():
            move_db(self.home_state_dir / v1_name, system_dir / v3_name, "from home dir")
        self.rmdir(self.home_state_dir, "only if empty")

    def _configure_database_paths(self) -> None:
        if self.plan.database_paths:
            return
        old_layout = DataLayout(self.root, version=self.plan.source_version)
        new_layout = self.new
        old_paths = _db_accessors(old_layout, self.home_state_dir)
        new_paths = _db_accessors(new_layout, self.home_state_dir)
        self.plan.database_paths = {key: (old_paths[key], new_paths[key]) for key in new_paths}

    def build(self) -> MigrationPlan:
        try:
            version = read_layout_version(self.root)
        except (OSError, RuntimeError) as exc:
            self.plan.conflicts.append(str(exc))
            return self.plan
        self.plan.source_version = version
        if version == self.target_version:
            self.plan.conflicts.append(f"{self.root} already uses layout v{version}")
            return self.plan
        if version > self.target_version:
            self.plan.conflicts.append(f"cannot migrate layout v{version} backwards to v{self.target_version}")
            return self.plan
        if version not in (1, 2):
            self.plan.conflicts.append(f"unsupported migration source version: {version}")
            return self.plan
        if not self.root.is_dir():
            self.plan.conflicts.append(f"data root does not exist: {self.root}")
            return self.plan

        managed_v1_entries = {
            ".layout-version", "md", "pdf", "jira", "owl", "mix", _V1_OUTPUT_DIR,
            "archive", "system",
        }
        managed_v1_entries.update(v1_name for v1_name, _ in _GLOBAL_FILES.values())
        if version == 1:
            for entry in sorted(self.root.iterdir()):
                if entry.name not in managed_v1_entries:
                    if entry.name.casefold() in {"domains", "sources", "derived", "output"}:
                        self.plan.conflicts.append(f"unexpected reserved layout path at v1 root: {entry}")
                    else:
                        self.archive(entry, "root")

        if version == 1:
            for source_type in (MARKDOWN, PDF, ONTOLOGY, MIX):
                self.plan_v1_sources(source_type)
            self.plan_v1_jira()
            self.plan_v1_output()
            if self.target_version >= 2:
                self.plan_global_files()
            else:
                self._configure_database_paths()
        else:
            self._configure_database_paths()
            self.plan_v2_domains()
        self.plan.operations.append(
            Operation("write_version", dst=self.new.version_file(), note=str(self.target_version))
        )
        self.plan.path_prefixes.sort(key=lambda pair: len(str(pair[0])), reverse=True)
        self.plan.db_rows_to_rewrite = _rewrite_db_paths(self.plan, dry_run=True)
        return self.plan


def plan_v1_to_v2(root: str | Path, home_state_dir: str | Path | None = None) -> MigrationPlan:
    """Compatibility planner for the historical v1 -> v2 migration."""
    home = Path(home_state_dir).expanduser() if home_state_dir else DataLayout.home_state_dir()
    return _Planner(Path(root).expanduser(), home, 2).build()


def plan_migration(
    root: str | Path,
    target_version: int = LAYOUT_VERSION,
    home_state_dir: str | Path | None = None,
) -> MigrationPlan:
    """Plan migration to the requested layout version (v3 by default)."""
    if target_version not in (2, 3):
        raise ValueError(f"unsupported migration target version: {target_version}")
    home = Path(home_state_dir).expanduser() if home_state_dir else DataLayout.home_state_dir()
    return _Planner(Path(root).expanduser(), home, target_version).build()


def _rewrite_value(value: str, prefixes: list[tuple[Path, Path]]) -> str | None:
    for old, new in prefixes:
        old_text = str(old)
        if value == old_text or value.startswith(old_text + os.sep):
            return str(new) + value[len(old_text):]
    return None


def _rewrite_json_value(
    value: object,
    prefixes: list[tuple[Path, Path]],
    path_needle: str,
) -> tuple[object, bool]:
    if isinstance(value, str):
        if path_needle not in value:
            return value, False
        replacement = _rewrite_value(value, prefixes)
        if replacement is not None:
            return replacement, True
        try:
            nested = json.loads(value)
        except json.JSONDecodeError:
            return _rewrite_embedded_paths(value, prefixes, path_needle)
        rewritten, changed = _rewrite_json_value(nested, prefixes, path_needle)
        if changed:
            return json.dumps(rewritten, ensure_ascii=False), True
        return _rewrite_embedded_paths(value, prefixes, path_needle)
    if isinstance(value, list):
        result = [_rewrite_json_value(item, prefixes, path_needle) for item in value]
        return [item for item, _ in result], any(changed for _, changed in result)
    if isinstance(value, dict):
        result = {key: _rewrite_json_value(item, prefixes, path_needle) for key, item in value.items()}
        return {key: item for key, (item, _) in result.items()}, any(changed for _, changed in result.values())
    return value, False


def _rewrite_embedded_paths(
    value: str,
    prefixes: list[tuple[Path, Path]],
    path_needle: str,
) -> tuple[str, bool]:
    if path_needle not in value:
        return value, False
    rewritten = value
    for old, new in prefixes:
        old_text = re.escape(str(old))
        rewritten = re.sub(
            old_text + r"(?=$|[/\s\"'():,;<>])",
            lambda _match: str(new),
            rewritten,
        )
    return rewritten, rewritten != value


def _rewrite_db_paths(plan: MigrationPlan, *, dry_run: bool) -> dict[str, int]:
    """Count or rewrite absolute path references in known SQLite path columns."""
    counts: dict[str, int] = {}
    if not plan.path_prefixes:
        return counts
    path_needle = os.path.commonpath([str(old) for old, _ in plan.path_prefixes])
    tables_by_db: dict[str, set[tuple[str, str]]] = {}
    for db_key, table, column in _PATH_COLUMNS:
        tables_by_db.setdefault(db_key, set()).add((table, column))
    for db_key, table_columns in tables_by_db.items():
        old_path, new_path = plan.database_paths[db_key]
        db_path = old_path if dry_run else new_path
        if not db_path.exists():
            continue
        if db_path.is_symlink():
            plan.conflicts.append(f"database path is a symlink; refusing to inspect or rewrite it: {db_path}")
            continue
        uri = f"file:{quote(str(db_path), safe='/')}?mode=ro" if dry_run else str(db_path)
        with closing(sqlite3.connect(uri, uri=dry_run)) as conn:
            for table, column in sorted(table_columns):
                exists = conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                if not exists:
                    continue
                columns = {row[1] for row in conn.execute(f'PRAGMA table_info("{table}")')}
                if column not in columns:
                    plan.warnings.append(f"stored-path schema lacks {table}.{column} in {db_path}")
                    continue
                updates = []
                for rowid, value in conn.execute(f'SELECT rowid, "{column}" FROM "{table}"'):
                    rewritten, changed = _rewrite_json_value(value, plan.path_prefixes, path_needle)
                    if changed and isinstance(rewritten, str):
                        updates.append((rewritten, rowid))
                if updates and not dry_run:
                    with conn:
                        conn.executemany(
                            f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?', updates
                        )
                if updates:
                    counts[f"{table}.{column}"] = counts.get(f"{table}.{column}", 0) + len(updates)
    return counts


@dataclass
class MigrationResult:
    done: list[Operation] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    db_rows_rewritten: dict[str, int] = field(default_factory=dict)
    log_path: Path | None = None


def apply_plan(plan: MigrationPlan, log: Callable[[str], None] = lambda _msg: None) -> MigrationResult:
    """Execute a migration plan. Refuses plans with conflicts."""
    if not plan.ok:
        raise RuntimeError("migration plan has conflicts:\n" + "\n".join(plan.conflicts))
    new = DataLayout(plan.root, version=plan.target_version)
    result = MigrationResult(log_path=new.system_dir() / MIGRATION_LOG_NAME)
    result.log_path.parent.mkdir(parents=True, exist_ok=True)

    def journal(op: Operation) -> None:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": op.kind,
            "src": str(op.src) if op.src else None,
            "dst": str(op.dst) if op.dst else None,
            "link_target": str(op.link_target) if op.link_target else None,
        }
        with result.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
        result.done.append(op)
        log(op.describe())

    for op in plan.operations:
        if op.kind == "rmdir":
            try:
                op.src.rmdir()
            except FileNotFoundError:
                continue
            except OSError:
                if op.note != "only if empty":
                    result.skipped.append(f"not empty, kept: {op.src}")
                continue
            journal(op)
        elif op.kind in ("move", "relink"):
            op.dst.parent.mkdir(parents=True, exist_ok=True)
            if op.kind == "move":
                shutil.move(str(op.src), str(op.dst))
            else:
                target = op.link_target or Path(os.path.abspath(op.src.parent / os.readlink(op.src)))
                os.symlink(target, op.dst, target_is_directory=op.src.is_dir())
                op.src.unlink()
            journal(op)
        elif op.kind == "write_version":
            result.db_rows_rewritten = _rewrite_db_paths(plan, dry_run=False)
            op.dst.write_text(f"{plan.target_version}\n", encoding="utf-8")
            journal(op)
    return result


__all__ = [
    "MIGRATION_LOG_NAME",
    "MigrationPlan",
    "MigrationResult",
    "Operation",
    "apply_plan",
    "plan_migration",
    "plan_v1_to_v2",
]

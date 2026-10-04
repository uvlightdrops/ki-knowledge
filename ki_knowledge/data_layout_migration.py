"""Migrate a data root from layout v1 (source type first) to v2 (domain first).

The migration is planned completely before anything is touched: if any target
already exists, nothing is moved. Symlinked domain folders (e.g. ``md/anthro``
pointing into cloud storage) are moved as links; their targets stay untouched.
Every executed step is appended to ``system/layout-migration.jsonl`` so an
interrupted run can be inspected and reverted by hand.
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

from ki_knowledge.data_layout import (
    _GLOBAL_FILES,
    _HOME_STATE_FILES,
    _V1_OUTPUT_DIR,
    DOMAIN_STATE_FILES,
    JIRA,
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

# Columns that store absolute data paths: (global file key, table, column).
_PATH_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("pdf_jobs_db", "pdf_import_jobs", "pdf_path"),
    ("django_db", "django_site_sourcedocument", "file_path"),
    ("django_db", "django_site_generateddocument", "file_path"),
    ("django_db", "django_site_infositemappingrule", "source_path"),
    ("django_db", "django_site_infositeproject", "source_directory"),
    ("django_db", "django_site_infositeproject", "output_dir"),
)


@dataclass
class Operation:
    """One filesystem step. ``kind`` is ``move``, ``relink``, ``rmdir`` or ``write_version``."""

    kind: str
    src: Path | None = None
    dst: Path | None = None
    note: str = ""

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
    operations: list[Operation] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    path_prefixes: list[tuple[Path, Path]] = field(default_factory=list)
    db_rows_to_rewrite: dict[str, int] = field(default_factory=dict)

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


class _Planner:
    def __init__(self, root: Path, home_state_dir: Path) -> None:
        self.old = DataLayout(root, version=1)
        self.new = DataLayout(root, version=2)
        self.plan = MigrationPlan(root=root, home_state_dir=home_state_dir)
        self._domain_names: dict[str, str] = {}
        self._targets: set[Path] = set()

    def domain(self, dir_name: str) -> str:
        """Merge ``md/Anthro`` and ``pdf/anthro`` into one domain folder."""
        return self._domain_names.setdefault(_domain_key(dir_name), dir_name)

    def move(self, src: Path, dst: Path, note: str = "", *, rewrite_paths: bool = True) -> None:
        kind = "move"
        if src.is_symlink():
            if not os.path.isabs(os.readlink(src)):
                kind = "relink"
                note = note or "relative symlink recreated with absolute target"
        elif src.is_dir():
            for link in _escaping_relative_links(src):
                self.plan.warnings.append(f"relative symlink will break after moving: {link}")
        if os.path.lexists(dst):
            self.plan.conflicts.append(f"target already exists: {dst}")
        if dst in self._targets:
            self.plan.conflicts.append(f"two sources map to the same target: {dst}")
        self._targets.add(dst)
        self.plan.operations.append(Operation(kind, src, dst, note))
        if rewrite_paths:
            self.plan.path_prefixes.append((src, dst))

    def rmdir(self, path: Path, note: str = "") -> None:
        self.plan.operations.append(Operation("rmdir", src=path, note=note))

    def archive(self, path: Path, category: str) -> None:
        self.plan.warnings.append(f"unexpected file moved to archive: {path}")
        self.move(path, self.new.archive_dir() / "v1" / category / path.name, "unexpected file")

    def type_dir(self, name: str) -> Path | None:
        base = self.old.root / name
        if base.is_symlink():
            self.plan.conflicts.append(f"{base} is a symlink; move its content manually first")
            return None
        return base if base.is_dir() else None

    def plan_sources(self, source_type: str) -> None:
        type_dir_name = source_type_dir_name(source_type)
        base = self.type_dir(type_dir_name)
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink() or child.is_dir():
                note = f"symlink -> {os.readlink(child)}" if child.is_symlink() else ("empty" if _is_empty_dir(child) else "")
                self.move(child, self.new.source_dir(source_type, self.domain(child.name)), note)
            else:
                self.archive(child, type_dir_name)
        self.rmdir(base, "type dir")

    def plan_jira(self) -> None:
        base = self.type_dir(source_type_dir_name(JIRA))
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink():
                self.move(child, self.new.source_dir(JIRA, self.domain(child.name)), f"symlink -> {os.readlink(child)}")
            elif child.is_dir():
                domain = self.domain(child.name)
                entries = sorted(child.iterdir())
                if not entries:
                    self.move(child, self.new.source_dir(JIRA, domain), "empty")
                    continue
                for entry in entries:
                    if entry.name in _DERIVED_FILE_NAMES and entry.is_file():
                        self.move(entry, self.new.domain_state_dir(domain) / entry.name, "derived")
                    else:
                        self.move(entry, self.new.source_dir(JIRA, domain, entry.name))
                self.rmdir(child)
            else:
                self.archive(child, "jira")
        self.rmdir(base, "type dir")

    def plan_output(self) -> None:
        base = self.type_dir(_V1_OUTPUT_DIR)
        if base is None:
            return
        for child in sorted(base.iterdir()):
            if child.is_symlink() or child.is_dir():
                self.move(child, self.new.output_dir(self.domain(child.name)))
            else:
                self.archive(child, _V1_OUTPUT_DIR)
        self.rmdir(base, "type dir")

    def _move_db(self, src: Path, dst: Path, note: str) -> None:
        self.move(src, dst, note, rewrite_paths=False)
        for suffix in _SQLITE_SIDECARS:
            sidecar = Path(f"{src}{suffix}")
            if sidecar.exists():
                self.move(sidecar, Path(f"{dst}{suffix}"), "sqlite sidecar", rewrite_paths=False)

    def plan_global_files(self) -> None:
        system_dir = self.new.system_dir()
        for v1_name, v2_name in _GLOBAL_FILES.values():
            src = self.old.root / v1_name
            if src.exists():
                self._move_db(src, system_dir / v2_name, "global state")
        home = self.plan.home_state_dir
        for v1_name, v2_name in _HOME_STATE_FILES.values():
            src = home / v1_name
            if src.exists():
                self._move_db(src, system_dir / v2_name, "from home dir")
        if home.is_dir():
            self.rmdir(home, "only if empty")

    def build(self) -> MigrationPlan:
        version = read_layout_version(self.old.root)
        if version != 1:
            self.plan.conflicts.append(f"{self.old.root} already uses layout v{version}")
            return self.plan
        if not self.old.root.is_dir():
            self.plan.conflicts.append(f"data root does not exist: {self.old.root}")
            return self.plan
        for source_type in (MARKDOWN, PDF, ONTOLOGY, MIX):
            self.plan_sources(source_type)
        self.plan_jira()
        self.plan_output()
        self.plan_global_files()
        self.plan.operations.append(Operation("write_version", dst=self.new.version_file(), note="2"))
        self.plan.path_prefixes.sort(key=lambda pair: len(str(pair[0])), reverse=True)
        self.plan.db_rows_to_rewrite = _rewrite_db_paths(self.plan, self.old, dry_run=True)
        return self.plan


def plan_v1_to_v2(root: str | Path, home_state_dir: str | Path | None = None) -> MigrationPlan:
    """Describe every step needed to convert ``root`` to layout v2 without touching it."""
    home = Path(home_state_dir).expanduser() if home_state_dir else DataLayout.home_state_dir()
    return _Planner(Path(root).expanduser(), home).build()


def _rewrite_value(value: str, prefixes: list[tuple[Path, Path]]) -> str | None:
    for old, new in prefixes:
        old_text = str(old)
        if value == old_text or value.startswith(old_text + os.sep):
            return str(new) + value[len(old_text):]
    return None


def _rewrite_db_paths(plan: MigrationPlan, layout: DataLayout, *, dry_run: bool) -> dict[str, int]:
    """Rewrite stored absolute paths that point into moved folders."""
    counts: dict[str, int] = {}
    getters = {"pdf_jobs_db": layout.pdf_jobs_db_path, "django_db": layout.django_db_path}
    for key, table, column in _PATH_COLUMNS:
        db_path = getters[key]()
        if not db_path.exists():
            continue
        uri = f"file:{db_path}?mode=ro" if dry_run else str(db_path)
        with closing(sqlite3.connect(uri, uri=dry_run)) as conn, conn:
            exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
            if not exists:
                continue
            updates = []
            for rowid, value in conn.execute(f'SELECT rowid, "{column}" FROM "{table}"'):
                new_value = _rewrite_value(value, plan.path_prefixes) if isinstance(value, str) else None
                if new_value is not None:
                    updates.append((new_value, rowid))
            if updates and not dry_run:
                conn.executemany(f'UPDATE "{table}" SET "{column}" = ? WHERE rowid = ?', updates)
            if updates:
                counts[f"{table}.{column}"] = len(updates)
    return counts


@dataclass
class MigrationResult:
    done: list[Operation] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    db_rows_rewritten: dict[str, int] = field(default_factory=dict)
    log_path: Path | None = None


def apply_plan(plan: MigrationPlan, log: Callable[[str], None] = lambda _msg: None) -> MigrationResult:
    """Execute a plan built by :func:`plan_v1_to_v2`. Refuses plans with conflicts."""
    if not plan.ok:
        raise RuntimeError("migration plan has conflicts:\n" + "\n".join(plan.conflicts))
    new = DataLayout(plan.root, version=2)
    result = MigrationResult(log_path=new.system_dir() / MIGRATION_LOG_NAME)
    result.log_path.parent.mkdir(parents=True, exist_ok=True)

    def journal(op: Operation) -> None:
        entry = {
            "at": datetime.now(timezone.utc).isoformat(),
            "kind": op.kind,
            "src": str(op.src) if op.src else None,
            "dst": str(op.dst) if op.dst else None,
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
        elif op.kind == "move":
            op.dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(op.src), str(op.dst))
            journal(op)
        elif op.kind == "relink":
            op.dst.parent.mkdir(parents=True, exist_ok=True)
            target = os.path.normpath(op.src.parent / os.readlink(op.src))
            os.symlink(target, op.dst, target_is_directory=op.src.is_dir())
            op.src.unlink()
            journal(op)
        elif op.kind == "write_version":
            result.db_rows_rewritten = _rewrite_db_paths(plan, new, dry_run=False)
            op.dst.write_text("2\n", encoding="utf-8")
            journal(op)
    return result


__all__ = [
    "MIGRATION_LOG_NAME",
    "MigrationPlan",
    "MigrationResult",
    "Operation",
    "apply_plan",
    "plan_v1_to_v2",
]

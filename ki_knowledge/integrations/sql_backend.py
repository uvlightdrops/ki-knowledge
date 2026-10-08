"""Small DB-API facade for SQLite and PostgreSQL-backed knowledge stores."""

from __future__ import annotations

import os
import re
import sqlite3
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import psycopg
except ImportError:  # pragma: no cover - optional until PostgreSQL is configured
    psycopg = None  # type: ignore[assignment]


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


@dataclass(frozen=True)
class StoreTarget:
    kind: str
    sqlite_path: Path | None = None
    postgres_dsn: str | None = None
    postgres_schema: str | None = None

    @classmethod
    def sqlite(cls, path: str | Path) -> "StoreTarget":
        return cls(kind="sqlite", sqlite_path=Path(path).expanduser())

    @classmethod
    def postgres(cls, dsn: str, schema: str = "public") -> "StoreTarget":
        return cls(kind="postgres", postgres_dsn=dsn, postgres_schema=schema or "public")

    @classmethod
    def parse(cls, value: str | Path | "StoreTarget", schema: str | None = None) -> "StoreTarget":
        if isinstance(value, StoreTarget):
            if schema and value.kind == "postgres" and schema != value.postgres_schema:
                return cls.postgres(value.postgres_dsn or "", schema=schema)
            return value
        text = str(value)
        if text.startswith(("postgresql://", "postgres://")):
            return cls.postgres(text, schema=schema or "public")
        return cls.sqlite(Path(text))

    @property
    def is_sqlite(self) -> bool:
        return self.kind == "sqlite"

    @property
    def is_postgres(self) -> bool:
        return self.kind == "postgres"

    def safe_label(self) -> str:
        if self.is_sqlite:
            return str(self.sqlite_path)
        parsed = urlparse(self.postgres_dsn or "")
        return f"postgresql://{parsed.hostname or ''}/{(parsed.path or '').lstrip('/')} schema={self.postgres_schema}"


class Row(Mapping[str, Any], Sequence[Any]):
    def __init__(self, keys: Sequence[str], values: Sequence[Any]):
        self._keys = tuple(keys)
        self._values = tuple(values)
        self._index = {key: i for i, key in enumerate(self._keys)}

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._values[key]
        return self._values[self._index[key]]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._values)

    def keys(self):  # type: ignore[override]
        return self._keys


class CursorWrapper:
    def __init__(self, cursor: Any, target: StoreTarget):
        self._cursor = cursor
        self.target = target
        self.rowcount = getattr(cursor, "rowcount", -1)
        self.lastrowid = getattr(cursor, "lastrowid", None)

    def execute(self, sql: str, params: Any = ()) -> "CursorWrapper":
        self._cursor.execute(translate_sql(sql, self.target.kind), params)
        self.rowcount = getattr(self._cursor, "rowcount", -1)
        self.lastrowid = getattr(self._cursor, "lastrowid", None)
        return self

    def executemany(self, sql: str, seq_of_params: Sequence[Any]) -> "CursorWrapper":
        self._cursor.executemany(translate_sql(sql, self.target.kind), seq_of_params)
        self.rowcount = getattr(self._cursor, "rowcount", -1)
        self.lastrowid = getattr(self._cursor, "lastrowid", None)
        return self

    def fetchone(self) -> Any:
        row = self._cursor.fetchone()
        return self._adapt_row(row)

    def fetchall(self) -> list[Any]:
        return [self._adapt_row(row) for row in self._cursor.fetchall()]

    def __iter__(self):
        for row in self._cursor:
            yield self._adapt_row(row)

    def _adapt_row(self, row: Any) -> Any:
        if row is None or self.target.is_sqlite:
            return row
        keys = [col.name if hasattr(col, "name") else col[0] for col in self._cursor.description or []]
        return Row(keys, row)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


class ConnectionWrapper:
    def __init__(self, raw: Any, target: StoreTarget):
        self.raw = raw
        self.target = target
        self.dialect = target.kind

    def cursor(self) -> CursorWrapper:
        return CursorWrapper(self.raw.cursor(), self.target)

    def execute(self, sql: str, params: Any = ()) -> CursorWrapper:
        cur = self.cursor()
        return cur.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: Sequence[Any]) -> CursorWrapper:
        cur = self.cursor()
        return cur.executemany(sql, seq_of_params)

    def commit(self) -> None:
        self.raw.commit()

    def rollback(self) -> None:
        self.raw.rollback()

    def close(self) -> None:
        self.raw.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw, name)


@contextmanager
def connect(target: StoreTarget | str | Path):
    resolved = StoreTarget.parse(target)
    if resolved.is_sqlite:
        assert resolved.sqlite_path is not None
        resolved.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        raw = sqlite3.connect(str(resolved.sqlite_path))
        raw.row_factory = sqlite3.Row
        wrapper = ConnectionWrapper(raw, resolved)
    else:
        if psycopg is None:  # pragma: no cover
            raise RuntimeError("psycopg is required for PostgreSQL knowledge stores")
        schema = resolved.postgres_schema or "public"
        raw = psycopg.connect(resolved.postgres_dsn, autocommit=False)  # type: ignore[union-attr]
        wrapper = ConnectionWrapper(raw, resolved)
        with raw.cursor() as cur:
            cur.execute(f"CREATE SCHEMA IF NOT EXISTS {quote_ident(schema)}")
            cur.execute(f"SET search_path TO {quote_ident(schema)}, public")
    try:
        yield wrapper
        wrapper.commit()
    except Exception:
        wrapper.rollback()
        raise
    finally:
        wrapper.close()


def translate_sql(sql: str, kind: str) -> str:
    if kind == "sqlite":
        return sql
    out: list[str] = []
    i = 0
    quote: str | None = None
    while i < len(sql):
        ch = sql[i]
        if quote:
            if ch == "%":
                out.append("%%")
            else:
                out.append(ch)
            if ch == quote:
                if i + 1 < len(sql) and sql[i + 1] == quote:
                    out.append(sql[i + 1])
                    i += 1
                else:
                    quote = None
            i += 1
            continue
        if ch in {"'", '"'}:
            quote = ch
            out.append(ch)
            i += 1
        elif ch == "?":
            out.append("%s")
            i += 1
        elif (
            ch == ":"
            and i + 1 < len(sql)
            and (sql[i + 1].isalpha() or sql[i + 1] == "_")
            and not (i > 0 and sql[i - 1] == ":")
        ):
            j = i + 2
            while j < len(sql) and (sql[j].isalnum() or sql[j] == "_"):
                j += 1
            out.append(f"%({sql[i + 1:j]})s")
            i = j
        elif ch == "%":
            out.append("%%")
            i += 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def json_text(column: str, key: str, dialect: str = "sqlite") -> str:
    if dialect == "postgres":
        return f"{column} ->> '{key}'"
    return f"json_extract({column}, '$.{key}')"


def ilike_operator(dialect: str = "sqlite") -> str:
    return "ILIKE" if dialect == "postgres" else "LIKE"


def table_columns(conn: ConnectionWrapper, table: str) -> set[str]:
    if conn.dialect == "postgres":
        rows = conn.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = current_schema() AND table_name = ?
            """,
            (table,),
        ).fetchall()
        return {row["column_name"] for row in rows}
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def upsert_replace_sql(table: str, columns: Sequence[str], conflict_columns: Sequence[str]) -> str:
    cols = ", ".join(columns)
    placeholders = ", ".join("?" for _ in columns)
    updates = ", ".join(f"{col} = excluded.{col}" for col in columns if col not in conflict_columns)
    return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT({', '.join(conflict_columns)}) DO UPDATE SET {updates}"


def vector_literal(vector: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in vector) + "]"


def normalized_schema(prefix: str, slug: str, *, max_len: int = 63) -> str:
    import hashlib

    base = re.sub(r"[^a-z0-9_]+", "_", slug.strip().lower()).strip("_") or "default"
    name = f"{prefix}{base}"
    if len(name) <= max_len:
        return name
    digest = hashlib.sha1(slug.encode("utf-8")).hexdigest()[:8]
    return f"{name[: max_len - 9]}_{digest}"


def backend_forced_sqlite() -> bool:
    return os.getenv("KI_KNOWLEDGE_STORE_BACKEND", "").strip().lower() == "sqlite"

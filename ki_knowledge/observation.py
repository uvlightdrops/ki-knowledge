"""Local, sampled ia3simworld observation windows (not simulation sessions)."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import logging
import math
from pathlib import Path
import sqlite3
import time
from urllib.parse import urlsplit
from uuid import uuid4

import requests

from ki_knowledge.app_config import AppConfig
from ki_knowledge.config_runtime import knowledge_store_target
from ki_knowledge.data_layout import DataLayout
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeSource

LOG = logging.getLogger(__name__)
WINDOW_TICKS = 1000
LIMITATIONS = [
    "Sampled snapshots, not a full simulation session or per-tick history.",
    "Only the most recent 50 string events are available per snapshot; complete event history is not guaranteed.",
    "Boundaries are observed ticks, not fabricated exact 1000-tick boundaries.",
    "Resets between samples that preserve identity and recover the tick count cannot be detected.",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def positive_seconds(value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError("interval and timeout must be finite positive seconds")
    return value


def local_url(value: str) -> str:
    url = urlsplit(value)
    if (url.scheme != "http" or url.hostname not in {"127.0.0.1", "localhost", "::1"}
            or url.username or url.password or url.fragment):
        raise ValueError("pilot source must be an HTTP loopback URL without credentials or fragment")
    return value


def validate_state(state: dict) -> None:
    if not isinstance(state, dict):
        raise ValueError("state must be an object")
    if type(state.get("tick")) is not int or state["tick"] < 0:
        raise ValueError("state tick must be a nonnegative integer")
    for key in ("nodeId", "createdAt"):
        if not isinstance(state.get(key), str) or not state[key].strip():
            raise ValueError(f"state {key} must be a nonempty string")
    events = state.get("events")
    if not isinstance(events, list) or len(events) > 50 or any(not isinstance(e, str) for e in events):
        raise ValueError("state events must contain at most 50 strings")


def fetch_state(url: str, timeout: float) -> dict:
    # No proxy, redirects, or distributed sync: this pilot reads only loopback.
    with requests.Session() as session:
        session.trust_env = False
        response = session.get(local_url(url), timeout=positive_seconds(timeout), allow_redirects=False)
        if response.status_code != 200:
            raise ValueError(f"source returned HTTP {response.status_code}")
        state = response.json()
    validate_state(state)
    return state


class ObservationStore:
    """Crash-safe samples and completion outbox, independent of the knowledge DB."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS observation_windows (
                    id TEXT PRIMARY KEY, source_url TEXT NOT NULL,
                    node_id TEXT NOT NULL, source_created_at TEXT NOT NULL,
                    status TEXT NOT NULL, reason TEXT, imported_at TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS observation_one_active
                    ON observation_windows(status) WHERE status = 'active';
                CREATE TABLE IF NOT EXISTS observation_samples (
                    sequence INTEGER PRIMARY KEY, window_id TEXT NOT NULL,
                    captured_at TEXT NOT NULL, tick INTEGER NOT NULL, raw_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS observation_samples_window
                    ON observation_samples(window_id, sequence);
                CREATE TABLE IF NOT EXISTS observation_failures (
                    sequence INTEGER PRIMARY KEY, occurred_at TEXT NOT NULL,
                    kind TEXT NOT NULL, error TEXT NOT NULL
                );
            """)

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    @contextmanager
    def worker_lock(self):
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError("another observation worker/importer owns this journal") from None
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def failure(self, kind: str, error: Exception) -> None:
        LOG.error("%s failed: %s", kind, error)
        with self.connect() as conn:
            conn.execute("INSERT INTO observation_failures(occurred_at, kind, error) VALUES (?, ?, ?)",
                         (now(), kind, str(error)))

    def capture(self, state: dict, source_url: str, captured_at: str | None = None) -> str | None:
        validate_state(state)
        source_url = local_url(source_url)
        timestamp = captured_at or now()
        raw = json.dumps(state, ensure_ascii=False, allow_nan=False)
        completed = None
        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            active = conn.execute("SELECT * FROM observation_windows WHERE status = 'active'").fetchone()
            if active:
                last = conn.execute(
                    "SELECT tick FROM observation_samples WHERE window_id = ? ORDER BY sequence DESC LIMIT 1",
                    (active["id"],),
                ).fetchone()
                reason = None
                if (active["source_url"], active["node_id"], active["source_created_at"]) != (
                        source_url, state["nodeId"], state["createdAt"]):
                    reason = "source_identity_changed"
                elif state["tick"] < last["tick"]:
                    reason = "tick_regressed"
                if reason:
                    conn.execute("UPDATE observation_windows SET status = 'interrupted', reason = ? WHERE id = ?",
                                 (reason, active["id"]))
                    LOG.warning("interrupted partial observation %s: %s", active["id"], reason)
                    active = None

            def start_window():
                window_id = f"ia3-observation:{uuid4()}"
                conn.execute("INSERT INTO observation_windows VALUES (?, ?, ?, ?, 'active', NULL, NULL)",
                             (window_id, source_url, state["nodeId"], state["createdAt"]))
                return window_id

            window_id = active["id"] if active else start_window()
            conn.execute(
                "INSERT INTO observation_samples(window_id, captured_at, tick, raw_json) VALUES (?, ?, ?, ?)",
                (window_id, timestamp, state["tick"], raw),
            )
            first = conn.execute(
                "SELECT tick FROM observation_samples WHERE window_id = ? ORDER BY sequence LIMIT 1",
                (window_id,),
            ).fetchone()["tick"]
            if state["tick"] - first >= WINDOW_TICKS:
                completed = window_id
                conn.execute("UPDATE observation_windows SET status = 'completed' WHERE id = ?", (window_id,))
                # Share the actual end sample as the next start, without inventing a boundary.
                next_id = start_window()
                conn.execute(
                    "INSERT INTO observation_samples(window_id, captured_at, tick, raw_json) VALUES (?, ?, ?, ?)",
                    (next_id, timestamp, state["tick"], raw),
                )
        LOG.info("captured window=%s tick=%s completed=%s", window_id, state["tick"], completed)
        return completed

    def artifact(self, window_id: str) -> dict:
        with self.connect() as conn:
            window = conn.execute("SELECT * FROM observation_windows WHERE id = ?", (window_id,)).fetchone()
            if window is None:
                raise ValueError(f"unknown observation: {window_id}")
            samples = conn.execute(
                "SELECT * FROM observation_samples WHERE window_id = ? ORDER BY sequence", (window_id,),
            ).fetchall()
            failures = conn.execute(
                "SELECT occurred_at, error FROM observation_failures WHERE kind = 'capture' "
                "AND occurred_at >= ? AND occurred_at <= ? ORDER BY sequence",
                (samples[0]["captured_at"], samples[-1]["captured_at"]),
            ).fetchall()
        tick_gaps = [b["tick"] - a["tick"] for a, b in zip(samples, samples[1:])]
        time_gaps = [(datetime.fromisoformat(b["captured_at"]) - datetime.fromisoformat(a["captured_at"])).total_seconds()
                     for a, b in zip(samples, samples[1:])]
        return {
            "schema_version": 1, "observation_id": window_id, "kind": "observation_window",
            "status": window["status"], "interruption_reason": window["reason"],
            "source_url": window["source_url"], "node_id": window["node_id"],
            "source_created_at": window["source_created_at"],
            "requested_tick_span": WINDOW_TICKS,
            "start_tick": samples[0]["tick"], "end_tick": samples[-1]["tick"],
            "actual_tick_span": samples[-1]["tick"] - samples[0]["tick"],
            "started_at": samples[0]["captured_at"], "ended_at": samples[-1]["captured_at"],
            "sample_count": len(samples), "tick_gaps": tick_gaps, "time_gaps_seconds": time_gaps,
            "max_tick_gap": max(tick_gaps, default=0),
            "unsampled_interior_ticks": sum(max(0, gap - 1) for gap in tick_gaps),
            "capture_failures": [dict(row) for row in failures], "limitations": LIMITATIONS,
            "samples": [{"captured_at": s["captured_at"], "state": json.loads(s["raw_json"])} for s in samples],
        }

    def import_completed(self, knowledge: KnowledgeStore) -> int:
        with self.connect() as conn:
            pending = conn.execute(
                "SELECT id FROM observation_windows WHERE status = 'completed' AND imported_at IS NULL ORDER BY rowid",
            ).fetchall()
        count = 0
        for row in pending:
            window_id = row["id"]
            try:
                artifact = self.artifact(window_id)
                raw = json.dumps(artifact, ensure_ascii=False, sort_keys=True, allow_nan=False)
                metadata = {k: v for k, v in artifact.items() if k != "samples"}
                metadata["provenance"] = {
                    "source_format": "ia3simworld_compact_state", "transport": "offline_local_import",
                    "journal": str(self.path), "observation_id": window_id,
                    "raw_artifact_id": window_id + ":raw",
                    "sha256": hashlib.sha256(raw.encode()).hexdigest(),
                }
                title = f"Observation {artifact['node_id']} ticks {artifact['start_tick']}-{artifact['end_tick']}"
                knowledge.upsert_source(KnowledgeSource(
                    window_id, "ia3_observation", title, f"{self.path.as_uri()}#{window_id}", metadata,
                ))
                knowledge.upsert_record(KnowledgeBlockRecord(
                    block_id=window_id + ":summary", source_id=window_id,
                    block_type="observation_summary", object_type="text", title=title,
                    content=json.dumps(metadata, ensure_ascii=False, indent=2), metadata=metadata,
                    tags=["observation", "sampled", "ia3simworld"],
                ))
                knowledge.upsert_artifact(KnowledgeArtifact(
                    window_id + ":raw", "observation_raw", window_id, [window_id + ":summary"], raw, metadata,
                ))
                # Separate stores cannot commit together. Stable IDs make replay after a crash converge.
                with self.connect() as conn:
                    conn.execute("UPDATE observation_windows SET imported_at = ? WHERE id = ?", (now(), window_id))
                count += 1
                LOG.info("imported observation=%s actual_tick_span=%s", window_id, artifact["actual_tick_span"])
            except Exception as exc:
                self.failure("import", exc)
                raise
        return count

    def status(self) -> dict:
        with self.connect() as conn:
            windows = conn.execute("SELECT * FROM observation_windows ORDER BY rowid").fetchall()
            failure_count = conn.execute("SELECT count(*) FROM observation_failures").fetchone()[0]
        summaries = []
        for row in windows:
            artifact = self.artifact(row["id"])
            summaries.append({k: v for k, v in artifact.items() if k not in {"samples", "tick_gaps", "time_gaps_seconds"}})
            summaries[-1]["imported_at"] = row["imported_at"]
        return {"journal": str(self.path), "failure_count": failure_count, "windows": summaries}


def cycle(store: ObservationStore, knowledge: KnowledgeStore, url: str, timeout: float) -> bool:
    ok = True
    try:
        store.capture(fetch_state(url, timeout), url)
    except (requests.RequestException, ValueError, OSError, sqlite3.Error) as exc:
        store.failure("capture", exc)
        ok = False
    try:
        store.import_completed(knowledge)
    except Exception as exc:
        # Worker boundary: also report backend-specific errors, but keep capturing.
        LOG.error("completed observation import pending retry: %s", type(exc).__name__)
        ok = False
    return ok


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["run", "once", "status", "import"])
    parser.add_argument("--source-url")
    parser.add_argument("--interval", type=float)
    parser.add_argument("--timeout", type=float)
    parser.add_argument("--state-db", type=Path)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = AppConfig.from_env()
    options = cfg.raw.get_path("knowledge.observation", {}) or {}
    layout = DataLayout.from_config(cfg)
    store = ObservationStore(args.state_db or layout.observation_db_path())
    if args.command == "status":
        print(json.dumps(store.status(), indent=2))
        return 0
    url = local_url(args.source_url or options.get("source_url", "http://127.0.0.1:17081/state?compact=true"))
    interval = positive_seconds(args.interval if args.interval is not None else options.get("interval_seconds", 10))
    timeout = positive_seconds(args.timeout if args.timeout is not None else options.get("timeout_seconds", 5))
    with store.worker_lock():
        knowledge = KnowledgeStore(knowledge_store_target(cfg))
        LOG.info("local target=%s journal=%s interval=%ss timeout=%ss",
                 knowledge.target.safe_label(), store.path, interval, timeout)
        if args.command == "import":
            store.import_completed(knowledge)
            return 0
        if args.command == "once":
            return 0 if cycle(store, knowledge, url, timeout) else 1
        try:
            while True:
                cycle(store, knowledge, url, timeout)
                time.sleep(interval)
        except KeyboardInterrupt:
            LOG.info("worker stopped; active observation retained for restart")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Persistent semantic term store and enrichment pipeline primitives."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from ki_knowledge.integrations.jira_cache import DomainTerm


@dataclass
class SemanticTerm:
    term_id: str
    canonical_label: str
    normalized_label: str
    language: str
    status: str
    created_at: str
    updated_at: str


@dataclass
class SemanticFact:
    fact_id: str
    term_id: str
    fact_type: str
    content: str
    confidence: float
    model_id: str
    prompt_version: str
    prompt_hash: str
    response_hash: str
    supersedes_fact_id: str | None
    created_at: str


@dataclass
class SemanticJob:
    job_id: str
    term_id: str
    job_type: str
    status: str
    attempts: int
    next_retry_at: str | None
    error_message: str | None
    prompt_text: str | None
    created_at: str
    updated_at: str


@dataclass
class SemanticTermGap:
    term_id: str
    canonical_label: str
    status: str
    fact_count: int
    relation_count: int
    avg_confidence: float
    needs_definition: bool
    needs_facts: bool
    needs_relations: bool
    priority_score: float


class ChatBackend(Protocol):
    def chat(self, messages: list[dict], **options) -> str:
        ...


class SemanticTermStore:
    """Stores canonical terms, enrichment jobs, immutable facts and relations."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_terms (
                    term_id TEXT PRIMARY KEY,
                    canonical_label TEXT NOT NULL,
                    normalized_label TEXT NOT NULL UNIQUE,
                    language TEXT NOT NULL DEFAULT 'de',
                    status TEXT NOT NULL DEFAULT 'new',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_term_aliases (
                    alias_id TEXT PRIMARY KEY,
                    term_id TEXT NOT NULL,
                    alias_label TEXT NOT NULL,
                    normalized_alias TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_term_candidates (
                    candidate_id TEXT PRIMARY KEY,
                    raw_label TEXT NOT NULL,
                    normalized_label TEXT NOT NULL,
                    score REAL NOT NULL,
                    issue_count INTEGER NOT NULL,
                    sample_issue_keys_json TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    promoted_term_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_enrichment_jobs (
                    job_id TEXT PRIMARY KEY,
                    term_id TEXT NOT NULL,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_retry_at TEXT,
                    error_message TEXT,
                    prompt_text TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_facts (
                    fact_id TEXT PRIMARY KEY,
                    term_id TEXT NOT NULL,
                    fact_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    model_id TEXT NOT NULL,
                    prompt_version TEXT NOT NULL,
                    prompt_hash TEXT NOT NULL,
                    response_hash TEXT NOT NULL,
                    supersedes_fact_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_relations (
                    relation_id TEXT PRIMARY KEY,
                    source_term_id TEXT NOT NULL,
                    target_term_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    weight REAL NOT NULL DEFAULT 0.5,
                    provenance_fact_id TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_record_term_links (
                    link_id TEXT PRIMARY KEY,
                    record_id TEXT NOT NULL,
                    term_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL DEFAULT 0.0,
                    evidence TEXT NOT NULL DEFAULT '',
                    job_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(record_id, term_id, source)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_terms_status ON semantic_terms(status)"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_semantic_candidates_normalized
                ON semantic_term_candidates(normalized_label)
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_jobs_status ON semantic_enrichment_jobs(status, updated_at)"
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(semantic_enrichment_jobs)").fetchall()
            }
            if "prompt_text" not in columns:
                conn.execute("ALTER TABLE semantic_enrichment_jobs ADD COLUMN prompt_text TEXT")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_facts_term ON semantic_facts(term_id, fact_type, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_semantic_relations_source ON semantic_relations(source_term_id)"
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_semantic_record_term_links_record
                ON semantic_record_term_links(record_id, updated_at)
                """
            )

    def normalize_term(self, label: str) -> str:
        normalized = label.strip().lower()
        normalized = normalized.replace("_", " ").replace("-", " ")
        normalized = re.sub(r"[^a-z0-9äöüß+.#/ ]+", " ", normalized)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        normalized = normalized.replace("oauth2", "oauth")
        if normalized.endswith(" services"):
            normalized = normalized[:-1]
        if normalized.endswith(" systems"):
            normalized = normalized[:-1]
        return normalized

    def upsert_term(self, label: str, source: str = "domain_terms") -> str:
        with self._connect() as conn:
            return self._upsert_term_with_conn(conn, label=label, source=source)

    def _upsert_term_with_conn(
        self,
        conn: sqlite3.Connection,
        *,
        label: str,
        source: str = "domain_terms",
    ) -> str:
        now = self._now()
        normalized = self.normalize_term(label)
        if not normalized:
            raise ValueError("Normalized term is empty")
        term_id = f"term:{hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:20]}"
        row = conn.execute(
            "SELECT term_id FROM semantic_terms WHERE normalized_label = ?",
            (normalized,),
        ).fetchone()
        if row:
            existing_term_id = row["term_id"]
            conn.execute(
                "UPDATE semantic_terms SET updated_at = ? WHERE term_id = ?",
                (now, existing_term_id),
            )
            self._upsert_alias(conn, existing_term_id, label, source, now)
            return existing_term_id
        conn.execute(
            """
            INSERT INTO semantic_terms (
                term_id, canonical_label, normalized_label, language, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (term_id, label.strip(), normalized, "de", "new", now, now),
        )
        self._upsert_alias(conn, term_id, label, source, now)
        return term_id

    def _upsert_term_with_conn_if_missing(
        self,
        conn: sqlite3.Connection,
        *,
        label: str,
        source: str,
    ) -> str:
        return self._upsert_term_with_conn(conn, label=label, source=source)

    def _upsert_alias(
        self,
        conn: sqlite3.Connection,
        term_id: str,
        alias_label: str,
        source: str,
        now: str,
    ) -> None:
        normalized = self.normalize_term(alias_label)
        if not normalized:
            return
        alias_id = f"alias:{hashlib.sha1(f'{term_id}:{normalized}'.encode('utf-8')).hexdigest()[:20]}"
        conn.execute(
            """
            INSERT OR REPLACE INTO semantic_term_aliases (
                alias_id, term_id, alias_label, normalized_alias, source, created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (alias_id, term_id, alias_label.strip(), normalized, source, now),
        )

    def store_domain_candidates(self, domain_terms: list[DomainTerm]) -> int:
        now = self._now()
        rows = []
        for term in domain_terms:
            normalized = self.normalize_term(term.term)
            if not normalized:
                continue
            source_type = "label" if "label" in term.sources else "text"
            candidate_id = f"cand:{hashlib.sha1(f'{normalized}:{source_type}'.encode('utf-8')).hexdigest()[:20]}"
            rows.append(
                (
                    candidate_id,
                    term.term,
                    normalized,
                    float(term.count),
                    int(term.issue_count),
                    json.dumps(term.sample_issue_keys, ensure_ascii=False),
                    source_type,
                    now,
                )
            )
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO semantic_term_candidates (
                    candidate_id, raw_label, normalized_label, score, issue_count,
                    sample_issue_keys_json, source_type, created_at, promoted_term_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, COALESCE(
                    (SELECT promoted_term_id FROM semantic_term_candidates WHERE candidate_id = ?),
                    NULL
                ))
                """,
                [(*row, row[0]) for row in rows],
            )
        return len(rows)

    def promote_candidates(self, limit: int = 500) -> int:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT candidate_id, raw_label
                FROM semantic_term_candidates
                WHERE promoted_term_id IS NULL
                ORDER BY source_type='label' DESC, score DESC, issue_count DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            promoted = 0
            for row in rows:
                term_id = self._upsert_term_with_conn_if_missing(
                    conn,
                    label=row["raw_label"],
                    source="jira_candidate",
                )
                conn.execute(
                    "UPDATE semantic_term_candidates SET promoted_term_id = ? WHERE candidate_id = ?",
                    (term_id, row["candidate_id"]),
                )
                promoted += 1
        return promoted

    def enqueue_jobs(self, job_type: str = "definition", only_status: str = "new", limit: int = 200) -> int:
        now = self._now()
        with self._connect() as conn:
            terms = conn.execute(
                """
                SELECT term_id
                FROM semantic_terms
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (only_status, limit),
            ).fetchall()
            created = 0
            for row in terms:
                term_id = row["term_id"]
                if self._enqueue_job_if_absent(conn, term_id=term_id, job_type=job_type, now=now):
                    created += 1
        return created

    def enqueue_record_link_jobs(self, record_ids: list[str], job_type: str = "record_terms") -> int:
        now = self._now()
        created = 0
        with self._connect() as conn:
            for record_id in record_ids:
                key = (record_id or "").strip()
                if not key:
                    continue
                existing = conn.execute(
                    """
                    SELECT 1
                    FROM semantic_enrichment_jobs
                    WHERE term_id = ? AND job_type = ? AND status IN ('pending', 'running', 'done')
                    LIMIT 1
                    """,
                    (key, job_type),
                ).fetchone()
                if existing:
                    continue
                job_seed = f"{key}:{job_type}:{now}"
                job_id = f"job:{hashlib.sha1(job_seed.encode('utf-8')).hexdigest()[:20]}"
                conn.execute(
                    """
                    INSERT INTO semantic_enrichment_jobs (
                        job_id, term_id, job_type, status, attempts, next_retry_at, error_message, prompt_text, created_at, updated_at
                    ) VALUES (?, ?, ?, 'pending', 0, NULL, NULL, NULL, ?, ?)
                    """,
                    (job_id, key, job_type, now, now),
                )
                created += 1
        return created

    def list_term_gaps(
        self,
        limit: int = 200,
        min_facts: int = 2,
        min_relations: int = 1,
        min_confidence: float = 0.65,
    ) -> list[SemanticTermGap]:
        terms = self.list_terms(limit=limit * 3)
        result: list[SemanticTermGap] = []
        for term in terms:
            facts = self.current_facts(term.term_id)
            relations = self.term_relations(term.term_id)
            definition_count = sum(1 for fact in facts if fact.fact_type == "definition")
            fact_count = len(facts)
            relation_count = len(relations)
            avg_confidence = (
                sum(fact.confidence for fact in facts) / fact_count if fact_count > 0 else 0.0
            )
            needs_definition = definition_count == 0
            needs_facts = fact_count < min_facts or avg_confidence < min_confidence
            needs_relations = relation_count < min_relations
            if not (needs_definition or needs_facts or needs_relations):
                continue
            priority_score = 0.0
            if needs_definition:
                priority_score += 5.0
            if needs_facts:
                priority_score += 3.0
            if needs_relations:
                priority_score += 2.0
            priority_score += max(0.0, min_confidence - avg_confidence)
            result.append(
                SemanticTermGap(
                    term_id=term.term_id,
                    canonical_label=term.canonical_label,
                    status=term.status,
                    fact_count=fact_count,
                    relation_count=relation_count,
                    avg_confidence=avg_confidence,
                    needs_definition=needs_definition,
                    needs_facts=needs_facts,
                    needs_relations=needs_relations,
                    priority_score=priority_score,
                )
            )
        result.sort(key=lambda item: (item.priority_score, -item.fact_count), reverse=True)
        return result[:limit]

    def enqueue_refinement_jobs(
        self,
        limit: int = 100,
        min_facts: int = 2,
        min_relations: int = 1,
        min_confidence: float = 0.65,
        job_type: str = "refine",
    ) -> int:
        now = self._now()
        gaps = self.list_term_gaps(
            limit=limit,
            min_facts=min_facts,
            min_relations=min_relations,
            min_confidence=min_confidence,
        )
        with self._connect() as conn:
            created = 0
            for gap in gaps:
                if self._enqueue_job_if_absent(conn, term_id=gap.term_id, job_type=job_type, now=now):
                    created += 1
        return created

    def claim_pending_jobs(
        self,
        batch_size: int = 10,
        job_types: tuple[str, ...] | None = None,
    ) -> list[SemanticJob]:
        now = self._now()
        where = """
            WHERE status = 'pending'
              AND (next_retry_at IS NULL OR next_retry_at <= ?)
        """
        params: list[Any] = [now]
        if job_types:
            placeholders = ",".join(["?"] * len(job_types))
            where += f" AND job_type IN ({placeholders})"
            params.extend(job_types)
        params.append(batch_size)
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT *
                FROM semantic_enrichment_jobs
                {where}
                ORDER BY updated_at ASC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
            jobs: list[SemanticJob] = []
            for row in rows:
                conn.execute(
                    """
                    UPDATE semantic_enrichment_jobs
                    SET status='running', attempts=attempts+1, updated_at=?
                    WHERE job_id = ? AND status = 'pending'
                    """,
                    (now, row["job_id"]),
                )
                fresh = conn.execute(
                    "SELECT * FROM semantic_enrichment_jobs WHERE job_id = ?",
                    (row["job_id"],),
                ).fetchone()
                if fresh and fresh["status"] == "running":
                    jobs.append(self._row_to_job(fresh))
        return jobs

    def mark_job_done(self, job_id: str, term_id: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE semantic_enrichment_jobs SET status='done', updated_at=?, error_message=NULL WHERE job_id=?",
                (now, job_id),
            )
            conn.execute(
                "UPDATE semantic_terms SET status='enriched', updated_at=? WHERE term_id=?",
                (now, term_id),
            )

    def mark_job_failed(self, job_id: str, error_message: str, attempts: int) -> None:
        now = self._now()
        if attempts >= 5:
            status = "failed"
            next_retry = None
        else:
            status = "pending"
            delay_minutes = 2**attempts
            retry_ts = datetime.now(UTC).timestamp() + (delay_minutes * 60)
            next_retry = datetime.fromtimestamp(retry_ts, UTC).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE semantic_enrichment_jobs
                SET status=?, next_retry_at=?, error_message=?, updated_at=?
                WHERE job_id=?
                """,
                (status, next_retry, error_message[:500], now, job_id),
            )

    def set_job_prompt(self, job_id: str, prompt_text: str) -> None:
        now = self._now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE semantic_enrichment_jobs
                SET prompt_text=?, updated_at=?
                WHERE job_id=?
                """,
                (prompt_text, now, job_id),
            )

    def add_fact(
        self,
        *,
        term_id: str,
        fact_type: str,
        content: str,
        confidence: float,
        model_id: str,
        prompt_version: str,
        prompt_hash: str,
        response_hash: str,
        supersedes_fact_id: str | None = None,
    ) -> str:
        now = self._now()
        seed = f"{term_id}:{fact_type}:{content}:{now}"
        fact_id = f"fact:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_facts (
                    fact_id, term_id, fact_type, content, confidence, model_id,
                    prompt_version, prompt_hash, response_hash, supersedes_fact_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    fact_id,
                    term_id,
                    fact_type,
                    content.strip(),
                    float(max(0.0, min(confidence, 1.0))),
                    model_id,
                    prompt_version,
                    prompt_hash,
                    response_hash,
                    supersedes_fact_id,
                    now,
                ),
            )
        return fact_id

    def fact_exists(self, term_id: str, fact_type: str, content: str) -> bool:
        text = content.strip().lower()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM semantic_facts
                WHERE term_id = ? AND fact_type = ? AND LOWER(content) = ?
                LIMIT 1
                """,
                (term_id, fact_type, text),
            ).fetchone()
        return row is not None

    def add_relation(
        self,
        *,
        source_term_id: str,
        target_term_id: str,
        relation_type: str,
        weight: float = 0.5,
        provenance_fact_id: str | None = None,
    ) -> str:
        now = self._now()
        seed = f"{source_term_id}:{target_term_id}:{relation_type}:{now}"
        relation_id = f"rel:{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:24]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_relations (
                    relation_id, source_term_id, target_term_id, relation_type, weight, provenance_fact_id, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_id,
                    source_term_id,
                    target_term_id,
                    relation_type,
                    float(max(0.0, min(weight, 1.0))),
                    provenance_fact_id,
                    now,
                ),
            )
        return relation_id

    def relation_exists(self, source_term_id: str, target_term_id: str, relation_type: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1
                FROM semantic_relations
                WHERE source_term_id = ? AND target_term_id = ? AND relation_type = ?
                LIMIT 1
                """,
                (source_term_id, target_term_id, relation_type),
            ).fetchone()
        return row is not None

    def list_terms(self, status: str | None = None, limit: int = 200) -> list[SemanticTerm]:
        query = "SELECT * FROM semantic_terms"
        params: list = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        query += " ORDER BY updated_at DESC, canonical_label ASC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_term(row) for row in rows]

    def forget_term(self, label: str) -> bool:
        normalized = self.normalize_term(label)
        if not normalized:
            return False
        now = self._now()
        with self._connect() as conn:
            term_rows = conn.execute(
                "SELECT term_id FROM semantic_terms WHERE normalized_label = ?",
                (normalized,),
            ).fetchall()
            term_ids = [row["term_id"] for row in term_rows]
            conn.execute(
                "DELETE FROM semantic_term_candidates WHERE normalized_label = ?",
                (normalized,),
            )
            conn.execute(
                "DELETE FROM semantic_term_aliases WHERE normalized_alias = ?",
                (normalized,),
            )
            for term_id in term_ids:
                conn.execute(
                    "DELETE FROM semantic_term_aliases WHERE term_id = ?",
                    (term_id,),
                )
                conn.execute(
                    "UPDATE semantic_terms SET status = 'deprecated', updated_at = ? WHERE term_id = ?",
                    (now, term_id),
                )
        return bool(term_ids)

    def upsert_record_term_link(
        self,
        *,
        record_id: str,
        term_id: str,
        source: str,
        confidence: float,
        evidence: str,
        job_id: str | None = None,
    ) -> str:
        now = self._now()
        source_value = source.strip().lower() or "semantic"
        link_seed = f"{record_id}:{term_id}:{source_value}"
        link_id = f"link:{hashlib.sha1(link_seed.encode('utf-8')).hexdigest()[:24]}"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO semantic_record_term_links (
                    link_id, record_id, term_id, source, confidence, evidence, job_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id, term_id, source) DO UPDATE SET
                    confidence = excluded.confidence,
                    evidence = excluded.evidence,
                    job_id = excluded.job_id,
                    updated_at = excluded.updated_at
                """,
                (
                    link_id,
                    record_id,
                    term_id,
                    source_value,
                    float(max(0.0, min(confidence, 1.0))),
                    (evidence or "").strip()[:800],
                    job_id,
                    now,
                    now,
                ),
            )
        return link_id

    def list_record_term_links(self, record_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        query = """
            SELECT srtl.*, st.canonical_label
            FROM semantic_record_term_links srtl
            LEFT JOIN semantic_terms st ON st.term_id = srtl.term_id
        """
        params: list[Any] = []
        if record_id:
            query += " WHERE srtl.record_id = ?"
            params.append(record_id)
        query += " ORDER BY srtl.updated_at DESC, srtl.confidence DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            {
                "link_id": row["link_id"],
                "record_id": row["record_id"],
                "term_id": row["term_id"],
                "term_label": row["canonical_label"] or row["term_id"],
                "source": row["source"],
                "confidence": float(row["confidence"]),
                "evidence": row["evidence"],
                "job_id": row["job_id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def list_domain_terms(
        self,
        *,
        limit: int = 200,
        min_count: int = 2,
        sort: str = "relevance",
        order: str = "desc",
    ) -> list[DomainTerm]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    st.term_id,
                    st.canonical_label,
                    st.updated_at,
                    c.score,
                    c.issue_count,
                    c.source_type,
                    c.sample_issue_keys_json
                FROM semantic_terms st
                JOIN semantic_term_candidates c ON c.promoted_term_id = st.term_id
                """
            ).fetchall()

        grouped: dict[str, dict] = {}
        for row in rows:
            term_id = row["term_id"]
            item = grouped.setdefault(
                term_id,
                {
                    "term": row["canonical_label"],
                    "count": 0,
                    "issue_count": 0,
                    "sources": set(),
                    "sample_issue_keys": [],
                    "updated_at": row["updated_at"],
                },
            )
            score = int(round(float(row["score"] or 0.0)))
            item["count"] = max(item["count"], score)
            item["issue_count"] = max(item["issue_count"], int(row["issue_count"] or 0))
            source_type = str(row["source_type"] or "").strip()
            if source_type:
                item["sources"].add(source_type)
            try:
                keys = json.loads(row["sample_issue_keys_json"] or "[]")
            except json.JSONDecodeError:
                keys = []
            for key in keys:
                key_str = str(key).strip()
                if key_str and key_str not in item["sample_issue_keys"]:
                    item["sample_issue_keys"].append(key_str)

        terms = [
            DomainTerm(
                term=str(item["term"]),
                count=int(item["count"]),
                issue_count=int(item["issue_count"]),
                sources=sorted(item["sources"]),
                sample_issue_keys=item["sample_issue_keys"][:8],
            )
            for item in grouped.values()
            if int(item["count"]) >= min_count
        ]

        sort_key = (sort or "relevance").strip().lower()
        sort_order = (order or "desc").strip().lower()
        reverse = sort_order != "asc"
        if sort_key == "term":
            terms = sorted(terms, key=lambda item: item.term.lower(), reverse=reverse)
        elif sort_key == "count":
            terms = sorted(terms, key=lambda item: item.count, reverse=reverse)
        elif sort_key == "issue_count":
            terms = sorted(terms, key=lambda item: item.issue_count, reverse=reverse)
        else:
            terms = sorted(
                terms,
                key=lambda item: (item.count, item.issue_count, item.term.lower()),
                reverse=True,
            )
            if not reverse:
                terms = list(reversed(terms))
        return terms[:limit]

    def list_jobs(
        self,
        *,
        status: str | None = None,
        job_type: str | None = None,
        limit: int = 200,
    ) -> list[SemanticJob]:
        query = "SELECT * FROM semantic_enrichment_jobs"
        params: list[Any] = []
        if status:
            query += " WHERE status = ?"
            params.append(status)
        if job_type:
            if params:
                query += " AND job_type = ?"
            else:
                query += " WHERE job_type = ?"
            params.append(job_type)
        query += " ORDER BY updated_at DESC, created_at DESC LIMIT ?"
        params.append(limit)
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [self._row_to_job(row) for row in rows]

    def get_job(self, job_id: str) -> SemanticJob | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM semantic_enrichment_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return self._row_to_job(row) if row else None

    def monitoring_snapshot(
        self,
        *,
        min_facts: int = 2,
        min_relations: int = 1,
        min_confidence: float = 0.65,
        recent_limit: int = 12,
        top_gap_limit: int = 8,
    ) -> dict:
        with self._connect() as conn:
            term_rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM semantic_terms GROUP BY status"
            ).fetchall()
            job_rows = conn.execute(
                "SELECT status, COUNT(*) AS c FROM semantic_enrichment_jobs GROUP BY status"
            ).fetchall()
            job_type_rows = conn.execute(
                """
                SELECT job_type, status, COUNT(*) AS c
                FROM semantic_enrichment_jobs
                GROUP BY job_type, status
                ORDER BY job_type, status
                """
            ).fetchall()
            total_terms_row = conn.execute("SELECT COUNT(*) AS c FROM semantic_terms").fetchone()
            total_facts_row = conn.execute("SELECT COUNT(*) AS c FROM semantic_facts").fetchone()
            total_relations_row = conn.execute("SELECT COUNT(*) AS c FROM semantic_relations").fetchone()
            total_candidates_row = conn.execute("SELECT COUNT(*) AS c FROM semantic_term_candidates").fetchone()
            total_record_links_row = conn.execute(
                "SELECT COUNT(*) AS c FROM semantic_record_term_links"
            ).fetchone()
            gap_row = conn.execute(
                """
                WITH current_facts AS (
                    SELECT sf.term_id, sf.fact_type, sf.confidence
                    FROM semantic_facts sf
                    LEFT JOIN semantic_facts newer
                      ON newer.supersedes_fact_id = sf.fact_id
                    WHERE newer.fact_id IS NULL
                ),
                fact_stats AS (
                    SELECT
                        term_id,
                        COUNT(*) AS fact_count,
                        AVG(confidence) AS avg_confidence,
                        SUM(CASE WHEN fact_type = 'definition' THEN 1 ELSE 0 END) AS def_count
                    FROM current_facts
                    GROUP BY term_id
                ),
                relation_stats AS (
                    SELECT source_term_id AS term_id, COUNT(*) AS relation_count
                    FROM semantic_relations
                    GROUP BY source_term_id
                )
                SELECT
                    SUM(CASE WHEN COALESCE(fs.def_count, 0) = 0 THEN 1 ELSE 0 END) AS needs_definition,
                    SUM(
                        CASE
                            WHEN COALESCE(fs.fact_count, 0) < ?
                              OR COALESCE(fs.avg_confidence, 0.0) < ?
                            THEN 1 ELSE 0
                        END
                    ) AS needs_facts,
                    SUM(CASE WHEN COALESCE(rs.relation_count, 0) < ? THEN 1 ELSE 0 END) AS needs_relations,
                    SUM(
                        CASE
                            WHEN COALESCE(fs.def_count, 0) = 0
                              OR COALESCE(fs.fact_count, 0) < ?
                              OR COALESCE(fs.avg_confidence, 0.0) < ?
                              OR COALESCE(rs.relation_count, 0) < ?
                            THEN 1 ELSE 0
                        END
                    ) AS total_gaps
                FROM semantic_terms st
                LEFT JOIN fact_stats fs ON fs.term_id = st.term_id
                LEFT JOIN relation_stats rs ON rs.term_id = st.term_id
                """,
                (min_facts, min_confidence, min_relations, min_facts, min_confidence, min_relations),
            ).fetchone()
            recent_rows = conn.execute(
                """
                SELECT job_id, term_id, job_type, status, attempts, updated_at, error_message, prompt_text
                FROM semantic_enrichment_jobs
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (recent_limit,),
            ).fetchall()

        term_status = {row["status"]: int(row["c"]) for row in term_rows}
        job_status = {row["status"]: int(row["c"]) for row in job_rows}
        job_type_summary: dict[str, dict[str, int]] = {}
        for row in job_type_rows:
            job_type = row["job_type"]
            job_type_summary.setdefault(job_type, {"pending": 0, "running": 0, "failed": 0, "done": 0})
            status_name = row["status"]
            if status_name in job_type_summary[job_type]:
                job_type_summary[job_type][status_name] = int(row["c"])
        top_gaps = self.list_term_gaps(
            limit=top_gap_limit,
            min_facts=min_facts,
            min_relations=min_relations,
            min_confidence=min_confidence,
        )
        return {
            "totals": {
                "terms": int(total_terms_row["c"]) if total_terms_row else 0,
                "facts": int(total_facts_row["c"]) if total_facts_row else 0,
                "relations": int(total_relations_row["c"]) if total_relations_row else 0,
                "candidates": int(total_candidates_row["c"]) if total_candidates_row else 0,
                "record_term_links": int(total_record_links_row["c"]) if total_record_links_row else 0,
            },
            "term_status": term_status,
            "job_status": job_status,
            "job_type_summary": [
                {
                    "job_type": job_type,
                    "label": job_type.replace("_", " ").title(),
                    "pending": values.get("pending", 0),
                    "running": values.get("running", 0),
                    "failed": values.get("failed", 0),
                    "done": values.get("done", 0),
                }
                for job_type, values in sorted(job_type_summary.items())
            ],
            "gaps": {
                "total": int(gap_row["total_gaps"] or 0) if gap_row else 0,
                "needs_definition": int(gap_row["needs_definition"] or 0) if gap_row else 0,
                "needs_facts": int(gap_row["needs_facts"] or 0) if gap_row else 0,
                "needs_relations": int(gap_row["needs_relations"] or 0) if gap_row else 0,
            },
            "top_gaps": [
                {
                    "term_id": item.term_id,
                    "canonical_label": item.canonical_label,
                    "priority_score": round(item.priority_score, 3),
                    "fact_count": item.fact_count,
                    "relation_count": item.relation_count,
                    "avg_confidence": round(item.avg_confidence, 3),
                }
                for item in top_gaps
            ],
            "recent_jobs": [
                {
                    "job_id": row["job_id"],
                    "term_id": row["term_id"],
                    "job_type": row["job_type"],
                    "status": row["status"],
                    "attempts": int(row["attempts"]),
                    "updated_at": row["updated_at"],
                    "error_message": row["error_message"] or "",
                    "prompt_text": row["prompt_text"] or "",
                }
                for row in recent_rows
            ],
            "updated_at": self._now(),
        }

    def get_term(self, term_id: str) -> SemanticTerm | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM semantic_terms WHERE term_id = ?", (term_id,)).fetchone()
        return self._row_to_term(row) if row else None

    def current_facts(self, term_id: str) -> list[SemanticFact]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sf.*
                FROM semantic_facts sf
                LEFT JOIN semantic_facts newer
                  ON newer.supersedes_fact_id = sf.fact_id
                WHERE sf.term_id = ?
                  AND newer.fact_id IS NULL
                ORDER BY sf.created_at DESC
                """,
                (term_id,),
            ).fetchall()
        return [self._row_to_fact(row) for row in rows]

    def term_relations(self, term_id: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT sr.*, st.canonical_label AS target_label
                FROM semantic_relations sr
                LEFT JOIN semantic_terms st ON st.term_id = sr.target_term_id
                WHERE sr.source_term_id = ?
                ORDER BY sr.weight DESC, sr.created_at DESC
                """,
                (term_id,),
            ).fetchall()
        return [
            {
                "relation_id": row["relation_id"],
                "source_term_id": row["source_term_id"],
                "target_term_id": row["target_term_id"],
                "target_label": row["target_label"] or row["target_term_id"],
                "relation_type": row["relation_type"],
                "weight": float(row["weight"]),
                "provenance_fact_id": row["provenance_fact_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def term_context(self, term_id: str, max_facts: int = 6, max_relations: int = 8) -> dict:
        facts = self.current_facts(term_id)[:max_facts]
        relations = self.term_relations(term_id)[:max_relations]
        return {
            "facts": [
                {"fact_type": item.fact_type, "content": item.content, "confidence": item.confidence}
                for item in facts
            ],
            "relations": [
                {
                    "relation_type": item["relation_type"],
                    "target_label": item["target_label"],
                    "weight": item["weight"],
                }
                for item in relations
            ],
        }

    def _row_to_term(self, row: sqlite3.Row) -> SemanticTerm:
        return SemanticTerm(
            term_id=row["term_id"],
            canonical_label=row["canonical_label"],
            normalized_label=row["normalized_label"],
            language=row["language"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _row_to_fact(self, row: sqlite3.Row) -> SemanticFact:
        return SemanticFact(
            fact_id=row["fact_id"],
            term_id=row["term_id"],
            fact_type=row["fact_type"],
            content=row["content"],
            confidence=float(row["confidence"]),
            model_id=row["model_id"],
            prompt_version=row["prompt_version"],
            prompt_hash=row["prompt_hash"],
            response_hash=row["response_hash"],
            supersedes_fact_id=row["supersedes_fact_id"],
            created_at=row["created_at"],
        )

    def _row_to_job(self, row: sqlite3.Row) -> SemanticJob:
        return SemanticJob(
            job_id=row["job_id"],
            term_id=row["term_id"],
            job_type=row["job_type"],
            status=row["status"],
            attempts=int(row["attempts"]),
            next_retry_at=row["next_retry_at"],
            error_message=row["error_message"],
            prompt_text=row["prompt_text"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    def _now(self) -> str:
        return datetime.now(UTC).isoformat(timespec="seconds")

    def _enqueue_job_if_absent(
        self,
        conn: sqlite3.Connection,
        *,
        term_id: str,
        job_type: str,
        now: str,
    ) -> bool:
        existing = conn.execute(
            """
            SELECT job_id
            FROM semantic_enrichment_jobs
            WHERE term_id = ? AND job_type = ? AND status IN ('pending','running')
            """,
            (term_id, job_type),
        ).fetchone()
        if existing:
            return False
        row = conn.execute(
            """
            SELECT job_id
            FROM semantic_enrichment_jobs
            WHERE term_id = ? AND job_type = ? AND status = 'done'
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (term_id, job_type),
        ).fetchone()
        if row and job_type == "definition":
            return False
        done_count_row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM semantic_enrichment_jobs
            WHERE term_id = ? AND job_type = ?
            """,
            (term_id, job_type),
        ).fetchone()
        done_count = int(done_count_row["c"]) if done_count_row else 0
        job_seed = f"{term_id}:{job_type}:{now}:{done_count}:{hashlib.sha1(term_id.encode('utf-8')).hexdigest()[:8]}"
        job_id = f"job:{hashlib.sha1(job_seed.encode('utf-8')).hexdigest()[:20]}"
        conn.execute(
            """
            INSERT INTO semantic_enrichment_jobs (
                job_id, term_id, job_type, status, attempts, next_retry_at, error_message, prompt_text, created_at, updated_at
            ) VALUES (?, ?, ?, 'pending', 0, NULL, NULL, NULL, ?, ?)
            """,
            (job_id, term_id, job_type, now, now),
        )
        return True


class SemanticEnrichmentService:
    """Worker-like enrichment service that asks LLM for compact term facts."""

    PROMPT_VERSION = "semantic-v1"

    def __init__(
        self,
        store: SemanticTermStore,
        backend: ChatBackend,
        model_id: str,
        knowledge_db_path: str | None = None,
    ):
        self.store = store
        self.backend = backend
        self.model_id = model_id
        self.knowledge_db_path = knowledge_db_path

    def run_batch(
        self,
        batch_size: int = 10,
        job_types: tuple[str, ...] | None = ("definition", "refine"),
    ) -> dict[str, int]:
        jobs = self.store.claim_pending_jobs(batch_size=batch_size, job_types=job_types)
        done = 0
        failed = 0
        for job in jobs:
            try:
                self._run_single(job)
                self.store.mark_job_done(job.job_id, job.term_id)
                done += 1
            except Exception as exc:
                self.store.mark_job_failed(job.job_id, str(exc), attempts=job.attempts)
                failed += 1
        return {"claimed": len(jobs), "done": done, "failed": failed}

    def _run_single(self, job: SemanticJob) -> None:
        if job.job_type == "record_terms":
            self._run_record_term_link_job(job)
            return

        term = self.store.get_term(job.term_id)
        if term is None:
            raise ValueError(f"term not found: {job.term_id}")

        context = self.store.term_context(term.term_id)
        prompt = self._prompt_for_term(term.canonical_label, job.job_type, context)
        self.store.set_job_prompt(job.job_id, prompt)
        raw = self.backend.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        parsed = self._parse_llm_json(raw)
        prompt_hash = self._sha(prompt)
        response_hash = self._sha(raw)
        confidence = float(parsed.get("confidence", 0.6))

        definition = str(parsed.get("definition", "")).strip()
        if definition:
            if not self.store.fact_exists(term.term_id, "definition", definition):
                definition_fact_id = self.store.add_fact(
                    term_id=term.term_id,
                    fact_type="definition",
                    content=definition,
                    confidence=confidence,
                    model_id=self.model_id,
                    prompt_version=self.PROMPT_VERSION,
                    prompt_hash=prompt_hash,
                    response_hash=response_hash,
                )
            else:
                definition_fact_id = None
        else:
            definition_fact_id = None

        facts = parsed.get("short_facts") or []
        for fact in facts[:8]:
            text = str(fact).strip()
            if not text:
                continue
            if self.store.fact_exists(term.term_id, "short_fact", text):
                continue
            self.store.add_fact(
                term_id=term.term_id,
                fact_type="short_fact",
                content=text,
                confidence=confidence,
                model_id=self.model_id,
                prompt_version=self.PROMPT_VERSION,
                prompt_hash=prompt_hash,
                response_hash=response_hash,
            )

        related = parsed.get("related_terms") or []
        for rel in related[:12]:
            if not isinstance(rel, dict):
                continue
            label = str(rel.get("label", "")).strip()
            relation_type = str(rel.get("relation", "related_to")).strip() or "related_to"
            weight = float(rel.get("weight", 0.5))
            if not label:
                continue
            target_term_id = self.store.upsert_term(label, source="llm_related")
            if self.store.relation_exists(term.term_id, target_term_id, relation_type):
                continue
            self.store.add_relation(
                source_term_id=term.term_id,
                target_term_id=target_term_id,
                relation_type=relation_type,
                weight=weight,
                provenance_fact_id=definition_fact_id,
            )

    def _run_record_term_link_job(self, job: SemanticJob) -> None:
        if not self.knowledge_db_path:
            raise ValueError("knowledge_db_path missing for record_terms job")
        from ki_knowledge.integrations.knowledge_store import KnowledgeStore

        knowledge_store = KnowledgeStore(self.knowledge_db_path)
        record = knowledge_store.get_record(job.term_id)
        if record is None:
            raise ValueError(f"record not found: {job.term_id}")

        text = (record.content or "").strip()
        if len(text) < 20:
            return

        known_terms = self.store.list_terms(limit=5000)
        if not known_terms:
            return
        normalized_text = self.store.normalize_term(text)
        by_normalized = {item.normalized_label: item for item in known_terms}
        lexical_matches: list[tuple[str, float, str]] = []
        for normalized_label, term in by_normalized.items():
            if len(normalized_label) < 4:
                continue
            if re.search(rf"\b{re.escape(normalized_label)}\b", normalized_text):
                lexical_matches.append((term.term_id, 0.82, normalized_label))
        for term_id, confidence, evidence in lexical_matches[:14]:
            self.store.upsert_record_term_link(
                record_id=record.block_id,
                term_id=term_id,
                source="lexical",
                confidence=confidence,
                evidence=f"matched '{evidence}'",
                job_id=job.job_id,
            )

        candidate_labels = self._record_candidate_labels(text, known_terms)
        prompt = self._prompt_for_record_terms(record.content, candidate_labels)
        self.store.set_job_prompt(job.job_id, prompt)
        raw = self.backend.chat([{"role": "user", "content": prompt}], temperature=0.1)
        parsed = self._parse_llm_json(raw)
        matches = parsed.get("matches") or []
        for item in matches[:20]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label", "")).strip()
            if not label:
                continue
            normalized = self.store.normalize_term(label)
            term = by_normalized.get(normalized)
            if not term:
                continue
            confidence = float(item.get("confidence", 0.55))
            reason = str(item.get("reason", "")).strip()
            self.store.upsert_record_term_link(
                record_id=record.block_id,
                term_id=term.term_id,
                source="llm",
                confidence=confidence,
                evidence=reason or label,
                job_id=job.job_id,
            )

    def _record_candidate_labels(self, text: str, terms: list[SemanticTerm], limit: int = 180) -> list[str]:
        normalized_text = self.store.normalize_term(text)
        tokens = {token for token in normalized_text.split() if len(token) >= 4}
        scored: list[tuple[int, str]] = []
        for term in terms:
            parts = [item for item in term.normalized_label.split() if len(item) >= 4]
            if not parts:
                continue
            overlap = len(tokens.intersection(parts))
            if overlap <= 0:
                continue
            scored.append((overlap, term.canonical_label))
        scored.sort(key=lambda item: (item[0], item[1].lower()), reverse=True)
        labels = [label for _, label in scored[:limit]]
        if not labels:
            labels = [term.canonical_label for term in terms[: min(limit, len(terms))]]
        return labels

    def _prompt_for_term(self, term: str, job_type: str, context: dict) -> str:
        context_json = json.dumps(context, ensure_ascii=False)
        job_hint = (
            "Fokus: Lücken schließen und Wissen ergänzen."
            if job_type == "refine"
            else "Fokus: initiale kompakte Definition und Basisfakten."
        )
        return (
            "Du bist ein fachlicher IT-Assistent. "
            "Erzeuge kompaktes, belastbares Wissen fuer einen Term.\n\n"
            f"Term: {term}\n\n"
            f"Job-Typ: {job_type}\n"
            f"{job_hint}\n"
            f"Bekannter Kontext (JSON): {context_json}\n\n"
            "Antworte STRICTLY als JSON ohne Markdown im Format:\n"
            "{\n"
            '  "definition": "1-2 Saetze",\n'
            '  "short_facts": ["kurzer Fakt 1", "kurzer Fakt 2"],\n'
            '  "related_terms": [{"label":"...","relation":"related_to","weight":0.0}],\n'
            '  "confidence": 0.0\n'
            "}\n"
            "Regeln: Nur IT-Kontext, keine erfundenen Quellen, kurze saubere Aussagen."
        )

    def _prompt_for_record_terms(self, content: str, candidate_terms: list[str]) -> str:
        candidates = "\n".join(f"- {item}" for item in candidate_terms[:180])
        excerpt = content[:2200]
        return (
            "Du analysierst einen Markdown-Wissensblock und ordnest ihn vorhandenen Terms zu.\n\n"
            f"Block-Text:\n{excerpt}\n\n"
            "Erlaubte Candidate Terms:\n"
            f"{candidates}\n\n"
            "Antworte STRICTLY als JSON ohne Markdown im Format:\n"
            "{\n"
            '  "matches": [\n'
            '    {"label":"Candidate Term","confidence":0.0,"reason":"kurze Begruendung"}\n'
            "  ]\n"
            "}\n"
            "Regeln: Nur Terms aus der Candidate-Liste verwenden. Maximal 12 Matches."
        )

    def build_prompt_for_job(self, job: SemanticJob) -> str:
        if job.prompt_text:
            return job.prompt_text
        if job.job_type == "record_terms":
            if not self.knowledge_db_path:
                return ""
            from ki_knowledge.integrations.knowledge_store import KnowledgeStore

            knowledge_store = KnowledgeStore(self.knowledge_db_path)
            record = knowledge_store.get_record(job.term_id)
            if record is None:
                return ""
            known_terms = self.store.list_terms(limit=5000)
            if not known_terms:
                return ""
            candidate_labels = self._record_candidate_labels(record.content or "", known_terms)
            return self._prompt_for_record_terms(record.content or "", candidate_labels)

        term = self.store.get_term(job.term_id)
        if term is None:
            return ""
        context = self.store.term_context(term.term_id)
        return self._prompt_for_term(term.canonical_label, job.job_type, context)

    def _parse_llm_json(self, raw: str) -> dict:
        text = (raw or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text).strip()
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        payload = json.loads(text)
        if not isinstance(payload, dict):
            raise ValueError("LLM output is not a JSON object")
        return payload

    def _sha(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

"""Structured cache and daily timeline analytics for Jira issues."""

from __future__ import annotations

import json
import re
import sqlite3
import math
import unicodedata
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Iterable, Protocol

from ki_knowledge.integrations.jira_client import JiraIssue


@dataclass
class DailyTopicSummary:
    """Aggregated per-day issue summary with topic signals."""

    day: str
    issue_count: int
    issue_keys: list[str]
    topics: list[str]


@dataclass
class CachedIssue:
    """Structured issue representation from SQLite cache."""

    key: str
    summary: str
    description: str | None
    status: str
    issue_type: str
    assignee: str | None
    labels: list[str]
    created_at: str | None
    updated_at: str | None
    event_day: str | None
    text_fields: dict[str, str]
    full_text: str


@dataclass
class HybridSearchHit:
    """Hybrid retrieval result with score transparency."""

    issue: CachedIssue
    lexical_score: float
    semantic_score: float
    combined_score: float


@dataclass
class DomainTerm:
    """Candidate domain term extracted from Jira issue content."""

    term: str
    count: int
    issue_count: int
    sources: list[str]
    sample_issue_keys: list[str]


@dataclass
class FieldSemanticHit:
    """Semantic hit for a specific textual issue field."""

    issue_key: str
    issue_summary: str
    field_name: str
    field_kind: str
    score: float
    top_terms: list[str]
    excerpt: str


class EmbeddingBackend(Protocol):
    """Embedding backend interface."""

    def embed(self, text: str) -> list[float]:
        ...


class JiraIssueCache:
    """SQLite-backed structured cache for Jira dump analysis."""

    _STOPWORDS = {
        "und", "oder", "der", "die", "das", "ein", "eine", "mit", "von", "für",
        "auf", "in", "zu", "den", "dem", "des", "ist", "sind", "nicht", "bei",
        "the", "and", "for", "with", "from", "this", "that", "into", "issue",
        "task", "story", "bug", "todo", "done",
    }
    _DOMAIN_NOISE_TERMS = {
        "bitte", "danke", "sowie", "sollte", "koennen", "können", "wurde", "wurden",
        "wird", "wurden", "haben", "hier", "diese", "dieser", "dieses", "there",
        "would", "should", "could", "about", "after", "before", "because", "while",
        "where", "which", "when", "what", "ticket", "tickets", "request", "requests",
        "service", "system", "feature", "problem", "problems", "update", "updates",
        "description", "kommentar", "comment", "body", "field", "text", "info",
        "error", "errors", "failed", "failure", "please", "need", "needs",
        "user", "users", "team", "seite", "frage", "fragen",
    }
    _DOMAIN_MIN_LEN = 4
    _DOMAIN_LABEL_WEIGHT = 6
    _DOMAIN_TEXT_WEIGHT = 1
    _COMMENT_FIELD_HINTS = (
        "comment",
        "kommentar",
        "comments",
        "rueckmeldung",
        "rückmeldung",
        "feedback",
        "discussion",
    )

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
                CREATE TABLE IF NOT EXISTS jira_issues (
                    issue_key TEXT PRIMARY KEY,
                    summary TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    assignee TEXT,
                    labels_json TEXT NOT NULL,
                    created_at TEXT,
                    updated_at TEXT,
                    event_day TEXT,
                    text_fields_json TEXT NOT NULL,
                    full_text TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_jira_issues_event_day ON jira_issues(event_day)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_issue_embeddings (
                    issue_key TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (issue_key, embedding_model)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_issue_embeddings_model ON jira_issue_embeddings(embedding_model)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_field_embeddings (
                    issue_key TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    field_kind TEXT NOT NULL,
                    embedding_model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    top_terms_json TEXT NOT NULL,
                    excerpt TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (issue_key, field_name, embedding_model)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_field_embeddings_model
                ON jira_field_embeddings(embedding_model, field_kind)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jira_excluded_terms (
                    normalized_term TEXT PRIMARY KEY,
                    display_term TEXT NOT NULL,
                    kind TEXT NOT NULL DEFAULT 'exception',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def ingest_issues(self, issues: Iterable[JiraIssue]) -> int:
        rows = [self._issue_to_row(issue) for issue in issues]
        if not rows:
            return 0

        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO jira_issues (
                    issue_key, summary, description, status, issue_type, assignee,
                    labels_json, created_at, updated_at, event_day, text_fields_json, full_text
                )
                VALUES (
                    :issue_key, :summary, :description, :status, :issue_type, :assignee,
                    :labels_json, :created_at, :updated_at, :event_day, :text_fields_json, :full_text
                )
                ON CONFLICT(issue_key) DO UPDATE SET
                    summary=excluded.summary,
                    description=excluded.description,
                    status=excluded.status,
                    issue_type=excluded.issue_type,
                    assignee=excluded.assignee,
                    labels_json=excluded.labels_json,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    event_day=excluded.event_day,
                    text_fields_json=excluded.text_fields_json,
                    full_text=excluded.full_text
                """,
                rows,
            )
        return len(rows)

    def daily_timeline(self, limit_days: int | None = None) -> list[DailyTopicSummary]:
        query = """
            SELECT event_day, issue_key, labels_json, full_text
            FROM jira_issues
            WHERE event_day IS NOT NULL
            ORDER BY event_day ASC, issue_key ASC
        """
        params: tuple = ()
        if limit_days:
            query = """
                SELECT event_day, issue_key, labels_json, full_text
                FROM jira_issues
                WHERE event_day IS NOT NULL
                ORDER BY event_day DESC, issue_key ASC
            """

        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()

        buckets: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            day = row["event_day"]
            buckets.setdefault(day, []).append(row)

        days = sorted(buckets.keys())
        if limit_days:
            days = days[-limit_days:]

        summaries: list[DailyTopicSummary] = []
        for day in days:
            day_rows = buckets[day]
            issue_keys = [row["issue_key"] for row in day_rows]
            topics = self._extract_topics(day_rows)
            summaries.append(
                DailyTopicSummary(
                    day=day,
                    issue_count=len(issue_keys),
                    issue_keys=issue_keys,
                    topics=topics,
                )
            )
        return summaries

    def issue_count(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM jira_issues").fetchone()
        return int(row["c"]) if row else 0

    def list_issues(self, limit: int = 500) -> list[CachedIssue]:
        """List cached issues."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    issue_key, summary, description, status, issue_type, assignee,
                    labels_json, created_at, updated_at, event_day, text_fields_json, full_text
                FROM jira_issues
                ORDER BY updated_at DESC, issue_key ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._row_to_cached_issue(row) for row in rows]

    def search_issues(self, query: str, limit: int = 8) -> list[CachedIssue]:
        """Search cached issues with weighted text matching."""
        hits = self._search_issues_with_scores(query, limit=limit)
        return [item[0] for item in hits]

    def build_embeddings(
        self,
        backend: EmbeddingBackend,
        embedding_model: str,
        issue_limit: int = 5000,
        min_text_len: int = 20,
    ) -> int:
        """Build or refresh embeddings for cached issues."""
        issues = self.list_issues(limit=issue_limit)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        rows = []
        for issue in issues:
            text = (issue.full_text or "").strip()
            if len(text) < min_text_len:
                continue
            vector = backend.embed(text)
            if not vector:
                continue
            rows.append(
                {
                    "issue_key": issue.key,
                    "embedding_model": embedding_model,
                    "vector_json": json.dumps(vector),
                    "updated_at": now,
                }
            )
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO jira_issue_embeddings (issue_key, embedding_model, vector_json, updated_at)
                VALUES (:issue_key, :embedding_model, :vector_json, :updated_at)
                ON CONFLICT(issue_key, embedding_model) DO UPDATE SET
                    vector_json=excluded.vector_json,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def semantic_search(
        self,
        query: str,
        backend: EmbeddingBackend,
        embedding_model: str,
        limit: int = 8,
        candidate_limit: int = 5000,
    ) -> list[HybridSearchHit]:
        """Search issues by embedding similarity."""
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        query_vector = backend.embed(normalized_query)
        if not query_vector:
            return []

        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    ji.issue_key, ji.summary, ji.description, ji.status, ji.issue_type, ji.assignee,
                    ji.labels_json, ji.created_at, ji.updated_at, ji.event_day, ji.text_fields_json, ji.full_text,
                    jie.vector_json
                FROM jira_issue_embeddings jie
                JOIN jira_issues ji ON ji.issue_key = jie.issue_key
                WHERE jie.embedding_model = ?
                ORDER BY jie.updated_at DESC
                LIMIT ?
                """,
                (embedding_model, candidate_limit),
            ).fetchall()

        scored: list[HybridSearchHit] = []
        for row in rows:
            issue = self._row_to_cached_issue(row)
            vector = json.loads(row["vector_json"])
            sim = self._cosine_similarity(query_vector, vector)
            if sim <= 0:
                continue
            scored.append(
                HybridSearchHit(
                    issue=issue,
                    lexical_score=0.0,
                    semantic_score=sim,
                    combined_score=sim,
                )
            )
        scored.sort(key=lambda item: item.combined_score, reverse=True)
        return scored[:limit]

    def hybrid_search(
        self,
        query: str,
        backend: EmbeddingBackend,
        embedding_model: str,
        limit: int = 8,
        lexical_weight: float = 0.35,
        semantic_weight: float = 0.65,
    ) -> list[HybridSearchHit]:
        """Hybrid retrieval combining lexical score and embedding similarity."""
        lexical_hits = self._search_issues_with_scores(query, limit=max(limit * 4, 20))
        semantic_hits = self.semantic_search(
            query=query,
            backend=backend,
            embedding_model=embedding_model,
            limit=max(limit * 4, 20),
        )

        lexical_max = max((score for _, score in lexical_hits), default=1.0)
        semantic_max = max((hit.semantic_score for hit in semantic_hits), default=1.0)

        merged: dict[str, HybridSearchHit] = {}
        for issue, score in lexical_hits:
            normalized = score / lexical_max if lexical_max > 0 else 0.0
            merged[issue.key] = HybridSearchHit(
                issue=issue,
                lexical_score=normalized,
                semantic_score=0.0,
                combined_score=lexical_weight * normalized,
            )

        for hit in semantic_hits:
            normalized = hit.semantic_score / semantic_max if semantic_max > 0 else 0.0
            existing = merged.get(hit.issue.key)
            if existing:
                existing.semantic_score = normalized
                existing.combined_score = (
                    lexical_weight * existing.lexical_score
                    + semantic_weight * normalized
                )
            else:
                merged[hit.issue.key] = HybridSearchHit(
                    issue=hit.issue,
                    lexical_score=0.0,
                    semantic_score=normalized,
                    combined_score=semantic_weight * normalized,
                )

        ranked = sorted(merged.values(), key=lambda item: item.combined_score, reverse=True)
        return ranked[:limit]

    def semantic_text_corpus(self, issue_limit: int = 5000) -> list[str]:
        """Return description/comment texts as corpus for local embedding backends."""
        issues = self.list_issues(limit=issue_limit)
        corpus: list[str] = []
        for issue in issues:
            for _, _, text in self._iter_semantic_fields(issue):
                cleaned = text.strip()
                if cleaned:
                    corpus.append(cleaned)
        return corpus

    def build_field_embeddings(
        self,
        backend: EmbeddingBackend,
        embedding_model: str,
        issue_limit: int = 5000,
        min_text_len: int = 40,
    ) -> int:
        """Build embeddings for issue description and comment-like named fields."""
        issues = self.list_issues(limit=issue_limit)
        now = datetime.now(UTC).isoformat(timespec="seconds")
        rows = []
        for issue in issues:
            for field_name, field_kind, text in self._iter_semantic_fields(issue):
                cleaned = text.strip()
                if len(cleaned) < min_text_len:
                    continue
                vector = backend.embed(cleaned)
                if not vector:
                    continue
                excerpt = cleaned[:280]
                rows.append(
                    {
                        "issue_key": issue.key,
                        "field_name": field_name,
                        "field_kind": field_kind,
                        "embedding_model": embedding_model,
                        "vector_json": json.dumps(vector),
                        "top_terms_json": json.dumps(self._top_terms(cleaned), ensure_ascii=False),
                        "excerpt": excerpt,
                        "updated_at": now,
                    }
                )
        if not rows:
            return 0
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO jira_field_embeddings (
                    issue_key, field_name, field_kind, embedding_model,
                    vector_json, top_terms_json, excerpt, updated_at
                )
                VALUES (
                    :issue_key, :field_name, :field_kind, :embedding_model,
                    :vector_json, :top_terms_json, :excerpt, :updated_at
                )
                ON CONFLICT(issue_key, field_name, embedding_model) DO UPDATE SET
                    field_kind=excluded.field_kind,
                    vector_json=excluded.vector_json,
                    top_terms_json=excluded.top_terms_json,
                    excerpt=excluded.excerpt,
                    updated_at=excluded.updated_at
                """,
                rows,
            )
        return len(rows)

    def semantic_field_search(
        self,
        query: str,
        backend: EmbeddingBackend,
        embedding_model: str,
        limit: int = 10,
        field_kind: str | None = None,
        candidate_limit: int = 5000,
    ) -> list[FieldSemanticHit]:
        """Semantic search over issue description/comment fields."""
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []
        query_vector = backend.embed(normalized_query)
        if not query_vector:
            return []

        where_kind = ""
        params: list[str | int] = [embedding_model]
        if field_kind:
            where_kind = " AND jfe.field_kind = ?"
            params.append(field_kind)
        params.extend([candidate_limit])

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    jfe.issue_key,
                    jfe.field_name,
                    jfe.field_kind,
                    jfe.vector_json,
                    jfe.top_terms_json,
                    jfe.excerpt,
                    ji.summary
                FROM jira_field_embeddings jfe
                JOIN jira_issues ji ON ji.issue_key = jfe.issue_key
                WHERE jfe.embedding_model = ? {where_kind}
                ORDER BY jfe.updated_at DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()

        hits: list[FieldSemanticHit] = []
        for row in rows:
            vector = json.loads(row["vector_json"])
            score = self._cosine_similarity(query_vector, vector)
            if score <= 0:
                continue
            top_terms = json.loads(row["top_terms_json"] or "[]")
            hits.append(
                FieldSemanticHit(
                    issue_key=row["issue_key"],
                    issue_summary=row["summary"],
                    field_name=row["field_name"],
                    field_kind=row["field_kind"],
                    score=score,
                    top_terms=top_terms,
                    excerpt=row["excerpt"],
                )
            )
        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def field_embedding_count(
        self,
        embedding_model: str,
        field_kind: str | None = None,
    ) -> int:
        """Count stored field embeddings for a model and optional field kind."""
        query = "SELECT COUNT(*) AS c FROM jira_field_embeddings WHERE embedding_model = ?"
        params: list[str] = [embedding_model]
        if field_kind:
            query += " AND field_kind = ?"
            params.append(field_kind)
        with self._connect() as conn:
            row = conn.execute(query, tuple(params)).fetchone()
        return int(row["c"]) if row else 0

    def extract_domain_terms(
        self,
        issue_limit: int = 5000,
        min_count: int = 2,
        limit: int = 40,
    ) -> list[DomainTerm]:
        """Extract IT-domain terms from labels, descriptions and comments."""
        issues = self.list_issues(limit=issue_limit)
        excluded_terms = self._excluded_terms()
        term_counts: Counter[str] = Counter()
        term_label_counts: Counter[str] = Counter()
        term_text_counts: Counter[str] = Counter()
        term_issue_keys: dict[str, set[str]] = {}
        term_sources: dict[str, set[str]] = {}

        for issue in issues:
            for label in issue.labels:
                for token in self._label_terms(label, excluded_terms=excluded_terms):
                    term_counts[token] += self._DOMAIN_LABEL_WEIGHT
                    term_label_counts[token] += 1
                    term_issue_keys.setdefault(token, set()).add(issue.key)
                    term_sources.setdefault(token, set()).add("label")

            for _, field_kind, text in self._iter_semantic_fields(issue):
                for token in self._text_domain_terms(text, excluded_terms=excluded_terms):
                    term_counts[token] += self._DOMAIN_TEXT_WEIGHT
                    term_text_counts[token] += 1
                    term_issue_keys.setdefault(token, set()).add(issue.key)
                    term_sources.setdefault(token, set()).add(field_kind)

        ranked_candidates: list[tuple[str, int, int, int]] = []
        for term, count in term_counts.items():
            issues_for_term = term_issue_keys.get(term, set())
            if not issues_for_term:
                continue
            label_hits = term_label_counts.get(term, 0)
            text_hits = term_text_counts.get(term, 0)
            if label_hits <= 0 and count < (min_count + 1):
                continue
            if label_hits <= 0 and len(issues_for_term) < 2:
                continue
            if label_hits <= 0 and text_hits < min_count:
                continue
            if self._is_noise_term(term):
                continue
            ranked_candidates.append((term, count, label_hits, len(issues_for_term)))

        ranked_candidates.sort(
            key=lambda item: (
                item[2],    # label hits first
                item[1],    # weighted score
                item[3],    # issue spread
                -len(item[0]),
            ),
            reverse=True,
        )

        ranked: list[DomainTerm] = []
        for term, count, _, issue_count in ranked_candidates:
            issues_for_term = term_issue_keys.get(term, set())
            ranked.append(
                DomainTerm(
                    term=term,
                    count=int(count),
                    issue_count=issue_count,
                    sources=sorted(term_sources.get(term, set())),
                    sample_issue_keys=sorted(issues_for_term)[:5],
                )
            )
            if len(ranked) >= limit:
                break
        return ranked

    def _search_issues_with_scores(self, query: str, limit: int) -> list[tuple[CachedIssue, float]]:
        """Internal lexical search with raw score."""
        normalized_query = (query or "").strip()
        if not normalized_query:
            return []

        tokens = self._tokenize(normalized_query)
        if not tokens:
            tokens = [normalized_query.lower()]

        where_clause = " OR ".join(["LOWER(full_text) LIKE ?"] * len(tokens))
        score_parts = []
        score_params: list[str] = []
        where_params: list[str] = []
        for token in tokens:
            like_value = f"%{token}%"
            score_parts.append("CASE WHEN LOWER(summary) LIKE LOWER(?) THEN 4 ELSE 0 END")
            score_parts.append("CASE WHEN LOWER(description) LIKE LOWER(?) THEN 2 ELSE 0 END")
            score_parts.append("CASE WHEN LOWER(full_text) LIKE LOWER(?) THEN 1 ELSE 0 END")
            score_params.extend([like_value, like_value, like_value])
            where_params.append(like_value)

        score_expr = " + ".join(score_parts)
        params = tuple(score_params + where_params + [limit])
        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    issue_key, summary, description, status, issue_type, assignee,
                    labels_json, created_at, updated_at, event_day, text_fields_json, full_text,
                    ({score_expr}) AS score
                FROM jira_issues
                WHERE ({where_clause})
                ORDER BY score DESC, updated_at DESC, issue_key ASC
                LIMIT ?
                """,
                params,
            ).fetchall()

        return [
            (self._row_to_cached_issue(row), float(row["score"]))
            for row in rows
        ]

    def _issue_to_row(self, issue: JiraIssue) -> dict[str, str | None]:
        event_day = self._derive_event_day(issue)
        full_text = " ".join(
            [
                issue.summary or "",
                issue.description or "",
                " ".join(issue.labels),
                " ".join(issue.text_fields.values()),
            ]
        ).strip()
        return {
            "issue_key": issue.key,
            "summary": issue.summary,
            "description": issue.description,
            "status": issue.status,
            "issue_type": issue.issue_type,
            "assignee": issue.assignee,
            "labels_json": json.dumps(issue.labels, ensure_ascii=False),
            "created_at": issue.created_at,
            "updated_at": issue.updated_at,
            "event_day": event_day,
            "text_fields_json": json.dumps(issue.text_fields, ensure_ascii=False),
            "full_text": full_text,
        }

    def _row_to_cached_issue(self, row: sqlite3.Row) -> CachedIssue:
        return CachedIssue(
            key=row["issue_key"],
            summary=row["summary"],
            description=row["description"],
            status=row["status"],
            issue_type=row["issue_type"],
            assignee=row["assignee"],
            labels=json.loads(row["labels_json"] or "[]"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            event_day=row["event_day"],
            text_fields=json.loads(row["text_fields_json"] or "{}"),
            full_text=row["full_text"],
        )

    def _derive_event_day(self, issue: JiraIssue) -> str | None:
        ts = issue.updated_at or issue.created_at
        if not ts:
            return None
        parsed = self._try_parse_datetime(ts)
        return parsed.strftime("%Y-%m-%d") if parsed else None

    def _try_parse_datetime(self, value: str) -> datetime | None:
        for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _extract_topics(self, rows: list[sqlite3.Row], max_topics: int = 5) -> list[str]:
        excluded_terms = self._excluded_terms()
        label_counter: Counter[str] = Counter()
        token_counter: Counter[str] = Counter()

        for row in rows:
            labels = json.loads(row["labels_json"] or "[]")
            for label in labels:
                normalized_label = self._normalize_exclusion_term(label)
                if normalized_label and normalized_label not in excluded_terms:
                    label_counter.update([label])
            token_counter.update(self._tokenize(row["full_text"] or "", excluded_terms=excluded_terms))

        topics: list[str] = []
        topics.extend([label for label, _ in label_counter.most_common(max_topics)])
        remaining = max_topics - len(topics)
        if remaining > 0:
            topics.extend(
                token for token, _ in token_counter.most_common(remaining) if token not in topics
            )
        return topics[:max_topics]

    def _tokenize(self, text: str, excluded_terms: set[str] | None = None) -> list[str]:
        raw_tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9_-]{4,}", text.lower())
        excluded = excluded_terms or set()
        return [tok for tok in raw_tokens if tok not in self._STOPWORDS and tok not in excluded]

    def _top_terms(self, text: str, max_terms: int = 6) -> list[str]:
        counter = Counter(self._tokenize(text))
        return [token for token, _ in counter.most_common(max_terms)]

    def _iter_semantic_fields(self, issue: CachedIssue) -> list[tuple[str, str, str]]:
        result: list[tuple[str, str, str]] = []
        if issue.description and issue.description.strip():
            result.append(("description", "description", issue.description))

        for name, value in issue.text_fields.items():
            if not value or not value.strip():
                continue
            normalized_name = self._normalize_term(name)
            if self._is_comment_field(normalized_name):
                result.append((name, "comment", value))
        return result

    def _is_comment_field(self, normalized_name: str) -> bool:
        return any(hint in normalized_name for hint in self._COMMENT_FIELD_HINTS)

    def _normalize_term(self, value: str) -> str:
        return value.lower().replace("_", " ").replace("-", " ")

    def _label_terms(self, label: str, excluded_terms: set[str] | None = None) -> list[str]:
        normalized = self._normalize_term(label).strip()
        if not normalized:
            return []
        terms: list[str] = []
        if self._is_valid_domain_term(normalized, excluded_terms=excluded_terms):
            terms.append(normalized)
        for token in self._tokenize(normalized, excluded_terms=excluded_terms):
            if self._is_valid_domain_term(token, excluded_terms=excluded_terms):
                terms.append(token)
        return list(dict.fromkeys(terms))

    def _text_domain_terms(self, text: str, excluded_terms: set[str] | None = None) -> list[str]:
        return [
            token
            for token in self._tokenize(text, excluded_terms=excluded_terms)
            if self._is_valid_domain_term(token, excluded_terms=excluded_terms)
        ]

    def _is_valid_domain_term(self, token: str, excluded_terms: set[str] | None = None) -> bool:
        normalized = token.strip().lower()
        if len(normalized) < self._DOMAIN_MIN_LEN:
            return False
        if not any(ch.isalpha() for ch in normalized):
            return False
        if normalized.isdigit():
            return False
        if normalized in self._STOPWORDS:
            return False
        if normalized in (excluded_terms or set()):
            return False
        if self._is_noise_term(normalized):
            return False
        if re.fullmatch(r"[a-z]{1,2}\d+", normalized):
            return False
        return True

    def _is_noise_term(self, token: str) -> bool:
        normalized = token.strip().lower()
        return normalized in self._DOMAIN_NOISE_TERMS

    def _excluded_terms(self) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT normalized_term FROM jira_excluded_terms").fetchall()
        return {row["normalized_term"] for row in rows if row["normalized_term"]}

    def list_excluded_terms(self, kind: str | None = None) -> list[dict[str, str]]:
        query = "SELECT normalized_term, display_term, kind, created_at, updated_at FROM jira_excluded_terms"
        params: list[str] = []
        if kind:
            query += " WHERE kind = ?"
            params.append(kind)
        query += " ORDER BY kind ASC, display_term ASC"
        with self._connect() as conn:
            rows = conn.execute(query, tuple(params)).fetchall()
        return [
            {
                "normalized_term": row["normalized_term"],
                "display_term": row["display_term"],
                "kind": row["kind"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def add_excluded_term(self, term: str, kind: str = "exception") -> bool:
        display = (term or "").strip()
        if not display:
            return False
        normalized = self._normalize_exclusion_term(display)
        if not normalized:
            return False
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO jira_excluded_terms (
                    normalized_term, display_term, kind, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(normalized_term) DO UPDATE SET
                    display_term=excluded.display_term,
                    kind=excluded.kind,
                    updated_at=excluded.updated_at
                """,
                (normalized, display, kind or "exception", now, now),
            )
        return True

    def remove_excluded_term(self, term: str) -> bool:
        normalized = self._normalize_exclusion_term(term)
        if not normalized:
            return False
        with self._connect() as conn:
            conn.execute("DELETE FROM jira_excluded_terms WHERE normalized_term = ?", (normalized,))
        return True

    def _normalize_exclusion_term(self, value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "").strip().lower()
        text = text.replace("_", " ").replace("-", " ")
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _cosine_similarity(self, left: list[float], right: list[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_norm = math.sqrt(sum(a * a for a in left))
        right_norm = math.sqrt(sum(b * b for b in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

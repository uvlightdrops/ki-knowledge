"""Retrieval-augmented assistant over Jira issue cache."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ki_knowledge.integrations.jira_cache import JiraIssueCache, CachedIssue, EmbeddingBackend
from ki_knowledge.integrations.jira_graph import JiraKnowledgeGraph


class ChatBackend(Protocol):
    """Backend interface compatible with KIClient and OllamaProvider."""

    def chat(self, messages: list[dict], **options) -> str:
        ...


@dataclass
class AssistantAnswer:
    """Answer object with explicit source trace."""

    answer: str
    sources: list[str]
    graph_expanded: list[str]
    prompt: str


class JiraSupportAssistant:
    """Support assistant that answers questions grounded in cached Jira data."""

    def __init__(
        self,
        backend: ChatBackend,
        cache: JiraIssueCache,
        embedding_backend: EmbeddingBackend | None = None,
        embedding_model: str | None = None,
        graph: JiraKnowledgeGraph | None = None,
    ):
        self.backend = backend
        self.cache = cache
        self.embedding_backend = embedding_backend
        self.embedding_model = embedding_model
        self.graph = graph

    def ask(self, question: str, limit: int = 8) -> AssistantAnswer:
        if self.embedding_backend and self.embedding_model:
            hybrid_hits = self.cache.hybrid_search(
                question,
                backend=self.embedding_backend,
                embedding_model=self.embedding_model,
                limit=limit,
            )
            context_issues = [hit.issue for hit in hybrid_hits]
        else:
            context_issues = self.cache.search_issues(question, limit=limit)

        seed_keys = [i.key for i in context_issues]
        graph_expanded: list[str] = []

        if self.graph and seed_keys:
            neighbor_keys = self.graph.related_issue_keys(
                seed_keys,
                relations=("related_label",),
                limit_per_seed=3,
            )
            if neighbor_keys:
                extra = self.cache.search_issues(" ".join(neighbor_keys[:8]), limit=4)
                extra_keys = {i.key for i in context_issues}
                for issue in extra:
                    if issue.key not in extra_keys:
                        context_issues.append(issue)
                        graph_expanded.append(issue.key)

        prompt = self._build_prompt(question, context_issues, graph_expanded)
        if self.backend is None:
            answer = "Kein Chat-Backend konfiguriert."
        else:
            answer = self.backend.chat([{"role": "user", "content": prompt}]).strip()
        return AssistantAnswer(
            answer=answer,
            sources=seed_keys,
            graph_expanded=graph_expanded,
            prompt=prompt,
        )

    def _build_prompt(
        self,
        question: str,
        issues: list[CachedIssue],
        graph_expanded: list[str],
    ) -> str:
        if not issues:
            context_block = "Keine passenden Issues gefunden."
        else:
            rows = []
            for issue in issues:
                expanded_marker = " [graph]" if issue.key in graph_expanded else ""
                rows.append(
                    "\n".join(
                        [
                            f"- Key: {issue.key}{expanded_marker}",
                            f"  Summary: {issue.summary}",
                            f"  Status: {issue.status}",
                            f"  Type: {issue.issue_type}",
                            f"  Labels: {', '.join(issue.labels) if issue.labels else '(keine)'}",
                            f"  Updated: {issue.updated_at or '(unbekannt)'}",
                            f"  Description: {issue.description or '(keine Beschreibung)'}",
                        ]
                    )
                )
            context_block = "\n\n".join(rows)

        graph_note = (
            f"\nHinweis: {', '.join(graph_expanded)} wurden per Wissensgraph ergänzt."
            if graph_expanded
            else ""
        )

        return f"""Du bist ein Jira-Support-Assistent.
Antworte ausschließlich auf Basis des bereitgestellten Jira-Kontexts.
Wenn Kontext fehlt, sage das klar und erfinde nichts.

Frage:
{question}

Kontext-Issues:
{context_block}{graph_note}

Antworte prägnant und nenne relevante Issue-Keys explizit.
"""

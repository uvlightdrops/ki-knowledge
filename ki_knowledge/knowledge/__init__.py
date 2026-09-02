"""Shared knowledge-core contracts for Phase A convergence."""

from ki_knowledge.knowledge.adapters import (
    IasemQuizAdapter,
    JiraKnowledgeAdapter,
    MarkdownKnowledgeAdapter,
    OntologyKnowledgeAdapter,
)
from ki_knowledge.knowledge.models import (
    KnowledgeArtifact,
    KnowledgeBlockRecord,
    KnowledgeRelationRecord,
    KnowledgeSource,
)
from ki_knowledge.knowledge.quiz_schema import QuizModuleSpec, QuizOptionSpec, QuizQuestionSpec

__all__ = [
    "IasemQuizAdapter",
    "JiraKnowledgeAdapter",
    "KnowledgeArtifact",
    "KnowledgeBlockRecord",
    "KnowledgeRelationRecord",
    "KnowledgeSource",
    "MarkdownKnowledgeAdapter",
    "OntologyKnowledgeAdapter",
    "QuizModuleSpec",
    "QuizOptionSpec",
    "QuizQuestionSpec",
]

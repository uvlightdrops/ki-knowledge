"""Shared knowledge-core contracts for Phase A convergence."""

from ki_knowledge.knowledge.adapters import (
    IasemQuizAdapter,
    InfoSiteSourceAdapter,
    JiraKnowledgeAdapter,
    MarkdownKnowledgeAdapter,
    OntologyKnowledgeAdapter,
)
from ki_knowledge.knowledge.models import (
    DataSourceDescriptor,
    KnowledgeArtifact,
    KnowledgeBlockRecord,
    KnowledgeRelationRecord,
    KnowledgeSource,
    SourceDocumentRecord,
)
from ki_knowledge.knowledge.quiz_schema import QuizModuleSpec, QuizOptionSpec, QuizQuestionSpec

__all__ = [
    "DataSourceDescriptor",
    "IasemQuizAdapter",
    "InfoSiteSourceAdapter",
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
    "SourceDocumentRecord",
]

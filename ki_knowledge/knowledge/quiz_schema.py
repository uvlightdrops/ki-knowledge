"""Neutral quiz schema derived from iasem's quiz format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class QuizOptionSpec:
    """Single answer option in the shared quiz schema."""

    option_id: str
    text: str


@dataclass
class QuizQuestionSpec:
    """Shared question format usable by APIs, UI, and generators."""

    question_id: str
    question: str
    options: list[QuizOptionSpec]
    correct_option_id: str
    explanation: str = ""
    same_as: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class QuizModuleSpec:
    """Shared quiz module format adapted from iasem YAML."""

    module_id: str
    title: str
    description: str = ""
    questions: list[QuizQuestionSpec] = field(default_factory=list)
    knowledge_blocks: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def question_count(self) -> int:
        return len(self.questions)

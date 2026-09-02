"""Phase-C generators for derived learning artifacts."""

from __future__ import annotations

import json
from dataclasses import asdict
from collections import Counter

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord
from ki_knowledge.knowledge.quiz_schema import QuizModuleSpec, QuizOptionSpec, QuizQuestionSpec


class KnowledgeArtifactGenerator:
    """Generate quiz and flashcard artifacts from generic knowledge records."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def generate_quiz_module(
        self,
        source_id: str,
        *,
        max_questions: int = 8,
        min_content_length: int = 40,
    ) -> KnowledgeArtifact:
        records = self._candidate_records(source_id, min_content_length=min_content_length)
        if not records:
            raise ValueError(f"No suitable records found for quiz generation from source '{source_id}'.")

        option_pool = self._option_pool(records)
        questions: list[QuizQuestionSpec] = []

        for idx, record in enumerate(records[:max_questions], start=1):
            correct_label = self._label_for_record(record)
            distractors = [label for label in option_pool if label != correct_label][:3]
            options = [QuizOptionSpec(option_id="A", text=correct_label)]
            option_ids = ["B", "C", "D"]
            for option_id, distractor in zip(option_ids, distractors):
                options.append(QuizOptionSpec(option_id=option_id, text=distractor))

            questions.append(
                QuizQuestionSpec(
                    question_id=f"gen_q_{idx}",
                    question=(
                        "Welcher Wissensbaustein passt am besten zu dieser Beschreibung?\n\n"
                        f"{self._snippet(record.content)}"
                    ),
                    options=options,
                    correct_option_id="A",
                    explanation=f"Der Inhalt stammt aus '{correct_label}'.",
                    metadata={"source_block_id": record.block_id},
                )
            )

        module = QuizModuleSpec(
            module_id=self._safe_artifact_suffix(source_id, "quiz"),
            title=f"Generated quiz for {source_id}",
            description="Automatisch aus Wissensbausteinen erzeugtes Quizmodul.",
            questions=questions,
            metadata={"generated_from_source_id": source_id, "generator": "KnowledgeArtifactGenerator"},
        )
        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:generated-quiz:{module.module_id}",
            artifact_type="generated_quiz_module",
            source_id=source_id,
            source_block_ids=[record.block_id for record in records[:max_questions]],
            content=json.dumps(
                {
                    "module_id": module.module_id,
                    "title": module.title,
                    "description": module.description,
                    "questions": [self._question_to_dict(question) for question in module.questions],
                },
                ensure_ascii=False,
            ),
            metadata={
                "question_count": len(module.questions),
                "generator": "KnowledgeArtifactGenerator",
            },
        )
        self.store.upsert_artifact(artifact)
        return artifact

    def generate_flashcards(
        self,
        source_id: str,
        *,
        max_cards: int = 12,
        min_content_length: int = 20,
    ) -> KnowledgeArtifact:
        records = self._candidate_records(source_id, min_content_length=min_content_length)
        if not records:
            raise ValueError(f"No suitable records found for flashcard generation from source '{source_id}'.")

        cards = []
        for idx, record in enumerate(records[:max_cards], start=1):
            cards.append(
                {
                    "card_id": f"card_{idx}",
                    "front": self._label_for_record(record),
                    "back": self._snippet(record.content, limit=260),
                    "source_block_id": record.block_id,
                }
            )

        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:flashcards:{self._safe_artifact_suffix(source_id, 'flashcards')}",
            artifact_type="flashcard_set",
            source_id=source_id,
            source_block_ids=[record.block_id for record in records[:max_cards]],
            content=json.dumps({"title": f"Flashcards for {source_id}", "cards": cards}, ensure_ascii=False),
            metadata={"card_count": len(cards), "generator": "KnowledgeArtifactGenerator"},
        )
        self.store.upsert_artifact(artifact)
        return artifact

    def generate_summary_note(
        self,
        source_id: str,
        *,
        max_sections: int = 6,
    ) -> KnowledgeArtifact:
        records = self._candidate_records(source_id, min_content_length=20)
        if not records:
            raise ValueError(f"No suitable records found for summary generation from source '{source_id}'.")

        sections = [
            {
                "title": self._label_for_record(record),
                "summary": self._snippet(record.content, limit=220),
                "source_block_id": record.block_id,
            }
            for record in records[:max_sections]
        ]
        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:summary:{self._safe_artifact_suffix(source_id, 'summary')}",
            artifact_type="summary_note",
            source_id=source_id,
            source_block_ids=[record.block_id for record in records[:max_sections]],
            content=json.dumps(
                {
                    "title": f"Summary for {source_id}",
                    "sections": sections,
                },
                ensure_ascii=False,
            ),
            metadata={"section_count": len(sections), "generator": "KnowledgeArtifactGenerator"},
        )
        self.store.upsert_artifact(artifact)
        return artifact

    def generate_glossary(
        self,
        source_id: str,
        *,
        max_terms: int = 12,
    ) -> KnowledgeArtifact:
        records = self._candidate_records(source_id, min_content_length=12)
        if not records:
            raise ValueError(f"No suitable records found for glossary generation from source '{source_id}'.")

        term_counter: Counter[str] = Counter()
        for record in records:
            term_counter[self._label_for_record(record)] += 1

        terms = []
        for record in records[:max_terms]:
            terms.append(
                {
                    "term": self._label_for_record(record),
                    "definition": self._snippet(record.content, limit=200),
                    "source_block_id": record.block_id,
                    "frequency": term_counter[self._label_for_record(record)],
                }
            )

        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:glossary:{self._safe_artifact_suffix(source_id, 'glossary')}",
            artifact_type="glossary",
            source_id=source_id,
            source_block_ids=[record.block_id for record in records[:max_terms]],
            content=json.dumps(
                {
                    "title": f"Glossary for {source_id}",
                    "terms": terms,
                },
                ensure_ascii=False,
            ),
            metadata={"term_count": len(terms), "generator": "KnowledgeArtifactGenerator"},
        )
        self.store.upsert_artifact(artifact)
        return artifact

    def generate_study_guide(
        self,
        source_id: str,
        *,
        max_items: int = 8,
    ) -> KnowledgeArtifact:
        records = self._candidate_records(source_id, min_content_length=20)
        if not records:
            raise ValueError(f"No suitable records found for study guide generation from source '{source_id}'.")

        items = []
        for record in records[:max_items]:
            items.append(
                {
                    "topic": self._label_for_record(record),
                    "focus": self._snippet(record.content, limit=180),
                    "prompt": f"Erkläre {self._label_for_record(record)} in eigenen Worten.",
                    "source_block_id": record.block_id,
                }
            )

        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:studyguide:{self._safe_artifact_suffix(source_id, 'studyguide')}",
            artifact_type="study_guide",
            source_id=source_id,
            source_block_ids=[record.block_id for record in records[:max_items]],
            content=json.dumps(
                {
                    "title": f"Study guide for {source_id}",
                    "items": items,
                },
                ensure_ascii=False,
            ),
            metadata={"item_count": len(items), "generator": "KnowledgeArtifactGenerator"},
        )
        self.store.upsert_artifact(artifact)
        return artifact

    def _candidate_records(self, source_id: str, *, min_content_length: int) -> list[KnowledgeBlockRecord]:
        ignored_types = {"semantic_reference", "quiz_option"}
        return [
            record
            for record in self.store.list_records(source_id=source_id, limit=500)
            if record.block_type not in ignored_types and len(record.content.strip()) >= min_content_length
        ]

    def _option_pool(self, records: list[KnowledgeBlockRecord]) -> list[str]:
        seen: set[str] = set()
        labels: list[str] = []
        for record in records:
            label = self._label_for_record(record)
            if label not in seen:
                seen.add(label)
                labels.append(label)
        return labels

    def _label_for_record(self, record: KnowledgeBlockRecord) -> str:
        return record.title or record.path or record.block_type

    def _snippet(self, text: str, *, limit: int = 180) -> str:
        normalized = " ".join(text.split())
        if len(normalized) <= limit:
            return normalized
        return normalized[: limit - 1].rstrip() + "…"

    def _safe_artifact_suffix(self, source_id: str, kind: str) -> str:
        return f"{source_id}:{kind}".replace("/", "_").replace(" ", "_")

    def _question_to_dict(self, question: QuizQuestionSpec) -> dict:
        return {
            "id": question.question_id,
            "question": question.question,
            "correct_option_id": question.correct_option_id,
            "explanation": question.explanation,
            "same_as": question.same_as,
            "options": [asdict(option) for option in question.options],
            "metadata": question.metadata,
        }

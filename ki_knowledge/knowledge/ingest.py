"""Phase-B ingestion services for shared knowledge sources."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.adapters import IasemQuizAdapter
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeSource


class KnowledgeIngestService:
    """Import external source formats into the shared knowledge store."""

    def __init__(self, store: KnowledgeStore):
        self.store = store

    def import_iasem_quiz_file(self, path: str | Path) -> dict[str, Any]:
        file_path = Path(path)
        payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
        return self.import_iasem_quiz_payload(
            payload,
            source_path=str(file_path.resolve()),
            source_name=file_path.name,
        )

    def import_iasem_quiz_payload(
        self,
        payload: dict[str, Any],
        *,
        source_path: str,
        source_name: str,
    ) -> dict[str, Any]:
        module = IasemQuizAdapter.to_quiz_module(payload)
        source = KnowledgeSource(
            source_id=f"iasem-quiz:{module.module_id}",
            source_type="iasem_quiz",
            title=module.title,
            location=source_path,
            metadata={
                "source_name": source_name,
                "description": module.description,
                "source_format": module.metadata.get("source_format", "iasem.quiz"),
            },
        )
        self.store.upsert_source(source)

        created_ids: list[str] = []
        module_block_id = f"{module.module_id}:module"
        module_record = KnowledgeBlockRecord(
            block_id=module_block_id,
            source_id=source.source_id,
            block_type="quiz_module",
            title=module.title,
            content=module.description or module.title,
            path=module.title,
            order_index=0,
            metadata={"question_count": module.question_count()},
        )
        self.store.upsert_record(module_record)
        created_ids.append(module_block_id)

        order_index = 1
        for idx, block in enumerate(module.knowledge_blocks, start=1):
            block_id = f"{module.module_id}:knowledge:{idx}"
            content_parts = [block["title"]]
            if block.get("summary"):
                content_parts.append(block["summary"])
            content_parts.extend(block.get("bullets", []))
            record = KnowledgeBlockRecord(
                block_id=block_id,
                source_id=source.source_id,
                block_type="knowledge_section",
                title=block["title"],
                content="\n".join(part for part in content_parts if part).strip(),
                parent_block_id=module_block_id,
                path=f"{module.title} / {block['title']}",
                order_index=order_index,
                metadata={"same_as": block.get("same_as", "")},
            )
            self.store.upsert_record(record)
            self.store.add_relation(module_block_id, block_id, relation="contains")
            created_ids.append(block_id)
            order_index += 1

            same_as = (block.get("same_as") or "").strip()
            if same_as:
                ref_id = self._semantic_ref_block_id(same_as)
                self.store.upsert_record(
                    KnowledgeBlockRecord(
                        block_id=ref_id,
                        source_id=source.source_id,
                        block_type="semantic_reference",
                        title=same_as,
                        content=same_as,
                        path=f"{module.title} / semantic",
                        order_index=10_000 + idx,
                        metadata={"external_uri": same_as},
                    )
                )
                self.store.add_relation(block_id, ref_id, relation="same_as", weight=0.95)

        for question_idx, question in enumerate(module.questions, start=1):
            question_id = f"{module.module_id}:question:{question.question_id}"
            question_record = KnowledgeBlockRecord(
                block_id=question_id,
                source_id=source.source_id,
                block_type="quiz_question",
                title=question.question_id,
                content="\n".join(part for part in [question.question, question.explanation] if part).strip(),
                parent_block_id=module_block_id,
                path=f"{module.title} / question / {question.question_id}",
                order_index=order_index,
                metadata={"correct_option_id": question.correct_option_id},
            )
            self.store.upsert_record(question_record)
            self.store.add_relation(module_block_id, question_id, relation="contains")
            created_ids.append(question_id)
            order_index += 1

            if question.same_as:
                ref_id = self._semantic_ref_block_id(question.same_as)
                self.store.upsert_record(
                    KnowledgeBlockRecord(
                        block_id=ref_id,
                        source_id=source.source_id,
                        block_type="semantic_reference",
                        title=question.same_as,
                        content=question.same_as,
                        path=f"{module.title} / semantic",
                        order_index=20_000 + question_idx,
                        metadata={"external_uri": question.same_as},
                    )
                )
                self.store.add_relation(question_id, ref_id, relation="same_as", weight=0.95)

            for option_idx, option in enumerate(question.options, start=1):
                option_id = f"{module.module_id}:question:{question.question_id}:option:{option.option_id}"
                option_record = KnowledgeBlockRecord(
                    block_id=option_id,
                    source_id=source.source_id,
                    block_type="quiz_option",
                    title=option.option_id,
                    content=option.text,
                    parent_block_id=question_id,
                    path=f"{module.title} / question / {question.question_id} / {option.option_id}",
                    order_index=order_index,
                    metadata={"question_id": question.question_id},
                )
                self.store.upsert_record(option_record)
                self.store.add_relation(question_id, option_id, relation="has_option")
                if option.option_id == question.correct_option_id:
                    self.store.add_relation(question_id, option_id, relation="correct_option", weight=1.0)
                created_ids.append(option_id)
                order_index += 1

        artifact = KnowledgeArtifact(
            artifact_id=f"artifact:quiz:{module.module_id}",
            artifact_type="quiz_module",
            source_id=source.source_id,
            source_block_ids=created_ids,
            content=json.dumps(
                {
                    "module_id": module.module_id,
                    "title": module.title,
                    "description": module.description,
                    "questions": [
                        {
                            "id": question.question_id,
                            "question": question.question,
                            "correct_option_id": question.correct_option_id,
                            "explanation": question.explanation,
                            "same_as": question.same_as,
                            "options": [
                                {"id": option.option_id, "text": option.text}
                                for option in question.options
                            ],
                        }
                        for question in module.questions
                    ],
                },
                ensure_ascii=False,
            ),
            metadata={
                "question_count": module.question_count(),
                "knowledge_block_count": len(module.knowledge_blocks),
            },
        )
        self.store.upsert_artifact(artifact)

        return {
            "source_id": source.source_id,
            "module_id": module.module_id,
            "blocks": len(created_ids),
            "artifact_id": artifact.artifact_id,
        }

    def _semantic_ref_block_id(self, value: str) -> str:
        return f"semantic:{hashlib.sha1(value.encode('utf-8')).hexdigest()[:20]}"

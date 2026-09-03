"""Phase-A adapters that align ki_knowledge and iasem data structures."""

from __future__ import annotations

from typing import Any

from hashlib import sha256
from pathlib import Path

from ki_knowledge.integrations.jira_client import JiraIssue
from ki_knowledge.integrations.markdown_blocks import KnowledgeBlock
from ki_knowledge.knowledge.models import DataSourceDescriptor, KnowledgeBlockRecord, KnowledgeSource, SourceDocumentRecord
from ki_knowledge.knowledge.quiz_schema import QuizModuleSpec, QuizOptionSpec, QuizQuestionSpec


class InfoSiteSourceAdapter:
    """Adapt the legacy InfoSite model layer to the canonical data-source contract."""

    @staticmethod
    def make_source_id(source_type: str, title: str, uri: str) -> str:
        seed = f"{source_type}:{title}:{uri}".strip(":")
        digest = sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"{source_type}:{digest}"

    @staticmethod
    def to_descriptor(project: object, source_directory: str | None = None) -> DataSourceDescriptor:
        domain = getattr(project, "domain", "default") or "default"
        title = getattr(project, "title", "") or getattr(project, "working_title", "") or domain
        working_title = getattr(project, "working_title", "") or ""
        if source_directory:
            uri = source_directory
        elif getattr(project, "source_directory", ""):
            uri = project.source_directory
        else:
            from django.conf import settings as django_settings

            data_root = Path(django_settings.KI_CONFIG.knowledge_data_root)
            uri = str(data_root / "md" / domain / working_title)
        source_type = "filesystem_markdown"
        return DataSourceDescriptor(
            source_id=InfoSiteSourceAdapter.make_source_id(source_type, title, uri),
            source_type=source_type,
            title=title,
            uri=uri,
            provider="infosite",
            status=getattr(project, "sync_status", "discovered") or "discovered",
            metadata={
                "domain": domain,
                "working_title": working_title,
                "project_id": getattr(project, "id", None),
                "enabled": getattr(project, "enabled", True),
            },
        )

    @staticmethod
    def to_document(project: object, document: object) -> SourceDocumentRecord:
        source_descriptor = InfoSiteSourceAdapter.to_descriptor(project)
        file_path = getattr(document, "file_path", "") or ""
        title = getattr(document, "title", "") or Path(file_path).name
        document_type = getattr(document, "file_type", "other") or "other"
        status = getattr(document, "import_status", "discovered") or "discovered"
        return SourceDocumentRecord(
            document_id=InfoSiteSourceAdapter.make_source_id(document_type, title, file_path),
            source_id=source_descriptor.source_id,
            document_type=document_type,
            title=title,
            uri=file_path,
            version="v1",
            status=status,
            checksum=getattr(document, "checksum", None),
            metadata={
                "project_id": getattr(project, "id", None),
                "file_size": getattr(document, "file_size", None),
                "modified_at": getattr(document, "modified_at", None),
                "imported": getattr(document, "imported", False),
            },
        )

    @staticmethod
    def to_documents(project: object, documents: list[object]) -> list[SourceDocumentRecord]:
        return [InfoSiteSourceAdapter.to_document(project, doc) for doc in documents]


class MarkdownKnowledgeAdapter:
    """Map markdown parser output into the shared knowledge-core contract."""

    @staticmethod
    def to_records(blocks: list[KnowledgeBlock], source: KnowledgeSource) -> list[KnowledgeBlockRecord]:
        return [
            KnowledgeBlockRecord(
                block_id=block.id,
                source_id=source.source_id,
                block_type=block.block_type,
                title=block.heading_path or block.block_type,
                content=block.content,
                parent_block_id=block.parent_id,
                path=block.heading_path,
                order_index=block.order_index,
                metadata=dict(block.metadata),
            )
            for block in blocks
        ]


class JiraKnowledgeAdapter:
    """Represent a Jira issue as reusable knowledge blocks."""

    @staticmethod
    def to_records(issue: JiraIssue, source: KnowledgeSource) -> list[KnowledgeBlockRecord]:
        records = [
            KnowledgeBlockRecord(
                block_id=f"{issue.key}:summary",
                source_id=source.source_id,
                block_type="issue_summary",
                title=issue.key,
                content=issue.summary,
                path=issue.key,
                order_index=0,
                tags=list(issue.labels),
                metadata={
                    "status": issue.status,
                    "issue_type": issue.issue_type,
                    "assignee": issue.assignee,
                },
            )
        ]
        if issue.description:
            records.append(
                KnowledgeBlockRecord(
                    block_id=f"{issue.key}:description",
                    source_id=source.source_id,
                    block_type="issue_description",
                    title=issue.summary,
                    content=issue.description,
                    parent_block_id=f"{issue.key}:summary",
                    path=f"{issue.key} / description",
                    order_index=1,
                    tags=list(issue.labels),
                )
            )
        for idx, (field_name, value) in enumerate(issue.text_fields.items(), start=2):
            if not value:
                continue
            records.append(
                KnowledgeBlockRecord(
                    block_id=f"{issue.key}:field:{field_name}",
                    source_id=source.source_id,
                    block_type="issue_text_field",
                    title=field_name,
                    content=value,
                    parent_block_id=f"{issue.key}:summary",
                    path=f"{issue.key} / {field_name}",
                    order_index=idx,
                    tags=list(issue.labels),
                    metadata={"field_name": field_name},
                )
            )
        return records


class OntologyKnowledgeAdapter:
    """Map ontology concepts into knowledge records."""

    @staticmethod
    def to_records(concepts: list[Any], source: KnowledgeSource) -> list[KnowledgeBlockRecord]:
        """Convert ontology concepts to knowledge records.
        
        Args:
            concepts: List of OntologyConcept dataclass instances
            source: KnowledgeSource for the ontology
        
        Returns:
            List of KnowledgeBlockRecord with one record per concept
        """
        from ki_knowledge.knowledge.ontology_ingest import OntologyConcept
        
        records: list[KnowledgeBlockRecord] = []
        for idx, concept in enumerate(concepts):
            concept_cast = concept if isinstance(concept, OntologyConcept) else concept
            
            record = KnowledgeBlockRecord(
                block_id=concept_cast.concept_id,
                source_id=source.source_id,
                block_type="ontology_concept",
                title=concept_cast.label,
                content=concept_cast.definition or f"Concept: {concept_cast.label}",
                path=concept_cast.label,
                order_index=idx,
                tags=concept_cast.relations[:5] if concept_cast.relations else [],
                metadata={
                    "concept_id": concept_cast.concept_id,
                    "quality_score": concept_cast.quality_score,
                    "source_format": concept_cast.source_format,
                    "relations": concept_cast.relations,
                },
            )
            records.append(record)
        
        return records


class IasemQuizAdapter:
    """Normalize iasem quiz payloads into a shared quiz contract."""

    @staticmethod
    def to_quiz_module(payload: dict[str, Any]) -> QuizModuleSpec:
        quiz = IasemQuizAdapter._extract_quiz_mapping(payload)

        raw_questions = quiz.get("questions") or quiz.get("quiz_fragen") or []
        questions: list[QuizQuestionSpec] = []
        for idx, question in enumerate(raw_questions, start=1):
            options = [
                QuizOptionSpec(
                    option_id=str(option.get("id") or option.get("option_id") or chr(ord("A") + opt_idx)),
                    text=option.get("text") or option.get("option_text") or f"Option {opt_idx + 1}",
                )
                for opt_idx, option in enumerate(question.get("options") or question.get("antwort_optionen") or [])
            ]
            questions.append(
                QuizQuestionSpec(
                    question_id=str(question.get("id") or question.get("question_id") or f"q_{idx}"),
                    question=question.get("question") or question.get("frage_text") or "Frage ohne Text",
                    options=options,
                    correct_option_id=str(
                        question.get("correct_option_id") or question.get("korrekte_antwort_id") or ""
                    ),
                    explanation=question.get("explanation") or question.get("erklaerung") or "",
                    same_as=question.get("sameAs") or question.get("same_as") or "",
                )
            )

        knowledge_blocks = []
        for module in (
            quiz.get("sections")
            or quiz.get("unterkapitel")
            or quiz.get("modules")
            or IasemQuizAdapter._extract_chapter_like_blocks(quiz)
        ):
            block_title = module.get("title") or module.get("titel") or "Abschnitt"
            bullets = module.get("kerninhalte") or module.get("bullets") or []
            knowledge_blocks.append(
                {
                    "title": block_title,
                    "summary": module.get("summary") or module.get("beschreibung") or "",
                    "same_as": module.get("sameAs") or module.get("same_as") or "",
                    "bullets": bullets,
                }
            )

        return QuizModuleSpec(
            module_id=str(quiz.get("id") or "quiz_module"),
            title=quiz.get("title") or "Quiz",
            description=quiz.get("description") or "",
            questions=questions,
            knowledge_blocks=knowledge_blocks,
            metadata={"source_format": "iasem.quiz"},
        )

    @staticmethod
    def _extract_quiz_mapping(payload: dict[str, Any]) -> dict[str, Any]:
        quiz = payload.get("quiz")
        if isinstance(quiz, dict):
            return quiz

        data_root = payload.get("data", {})
        module = data_root.get("SchulungsModul")
        if isinstance(module, dict):
            return {
                "id": module.get("id", payload.get("id", "quiz_module")),
                "title": module.get("titel") or payload.get("title") or payload.get("name") or "Quiz",
                "description": module.get("beschreibung") or payload.get("description") or "",
                "unterkapitel": module.get("unterkapitel") or [],
                "quiz_fragen": module.get("quiz_fragen") or [],
                "kernkonzepte": module.get("kernkonzepte") or [],
                "massnahmen_praevention": module.get("massnahmen_praevention") or [],
            }

        if isinstance(data_root, dict):
            for value in data_root.values():
                if isinstance(value, dict):
                    return {
                        "id": value.get("id", payload.get("id", "knowledge_module")),
                        "title": value.get("titel") or payload.get("title") or payload.get("name") or "Wissensmodul",
                        "description": value.get("beschreibung") or payload.get("description") or "",
                        "unterkapitel": value.get("unterkapitel") or [],
                        "quiz_fragen": value.get("quiz_fragen") or [],
                        "kernkonzepte": value.get("kernkonzepte") or [],
                        "massnahmen_praevention": value.get("massnahmen_praevention") or [],
                    }

        if isinstance(payload.get("quiz_fragen"), list):
            return {
                "id": payload.get("id", "quiz_module"),
                "title": payload.get("titel") or payload.get("title") or "Quiz",
                "description": payload.get("beschreibung") or payload.get("description") or "",
                "unterkapitel": payload.get("unterkapitel") or [],
                "quiz_fragen": payload.get("quiz_fragen") or [],
                "kernkonzepte": payload.get("kernkonzepte") or [],
                "massnahmen_praevention": payload.get("massnahmen_praevention") or [],
            }

        raise ValueError(
            "Expected iasem-style payload with 'quiz', 'data.SchulungsModul', or top-level 'quiz_fragen'."
        )

    @staticmethod
    def _extract_chapter_like_blocks(quiz: dict[str, Any]) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        for concept in quiz.get("kernkonzepte") or []:
            blocks.append(
                {
                    "titel": concept.get("begriff") or "Kernkonzept",
                    "beschreibung": concept.get("definition") or "",
                    "sameAs": concept.get("sameAs") or concept.get("same_as") or "",
                    "kerninhalte": concept.get("dimensionen") or [],
                }
            )
        for measure in quiz.get("massnahmen_praevention") or []:
            blocks.append(
                {
                    "titel": measure.get("bereich") or "Maßnahme",
                    "beschreibung": "",
                    "sameAs": measure.get("sameAs") or measure.get("same_as") or "",
                    "kerninhalte": measure.get("handlungsanweisungen") or [],
                }
            )
        return blocks

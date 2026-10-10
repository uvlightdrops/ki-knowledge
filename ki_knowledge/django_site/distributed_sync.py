from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from django.utils import timezone

from ki_knowledge.app_config import AppConfig as Config
from ki_knowledge.django_site.knowledge_summary import _domain_scoped_sources, store
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.models import KnowledgeArtifact, KnowledgeBlockRecord, KnowledgeRelationRecord, KnowledgeSource
from ki_knowledge.node_sync import SyncClient, new_operation_id
from ki_knowledge.node_sync.client import PATH_EXPORT, normalize_domains

from .infosite_models import Domain, InfoSiteProject, NodeConfig, SourceDocument, SyncRun, current_node_id


@dataclass
class LocalNodeSnapshot:
    node_id: str
    role: str
    base_url: str
    sync_on_connect: bool
    distributed_enabled: bool
    master_url: str


def _local_node_settings() -> tuple[NodeConfig | None, LocalNodeSnapshot]:
    snapshot = local_node_snapshot()
    node = NodeConfig.objects.filter(node_id=snapshot.node_id).first()
    return node, snapshot


def resolved_master_url() -> str:
    node, snapshot = _local_node_settings()
    if node and node.base_url:
        return str(node.base_url).strip()
    return snapshot.master_url


def resolved_sync_secret() -> str:
    node, _snapshot = _local_node_settings()
    if node and node.sync_shared_secret:
        return str(node.sync_shared_secret).strip()
    return (Config.from_env().distributed_sync_shared_secret or "").strip()


def sync_client(origin: str) -> SyncClient:
    """Client for a peer node, with this node's shared secret and timeout."""
    return SyncClient(origin, secret=resolved_sync_secret(), timeout=Config.from_env().request_timeout)


def local_node_snapshot() -> LocalNodeSnapshot:
    config = Config.from_env()
    return LocalNodeSnapshot(
        node_id=current_node_id(),
        role=(config.distributed_node_role or "standalone").strip() or "standalone",
        base_url="",
        sync_on_connect=bool(config.distributed_sync_on_connect),
        distributed_enabled=bool(config.distributed_enabled),
        master_url=(config.distributed_master_url or "").strip(),
    )


def ensure_local_node_config() -> NodeConfig:
    snapshot = local_node_snapshot()
    node, _ = NodeConfig.objects.update_or_create(
        node_id=snapshot.node_id,
        defaults={
            "role": snapshot.role,
            "base_url": snapshot.base_url,
            "sync_on_connect": snapshot.sync_on_connect,
            "is_enabled": snapshot.distributed_enabled or snapshot.role == "master",
            "sync_shared_secret": (Config.from_env().distributed_sync_shared_secret or "").strip(),
            "last_seen_at": timezone.now(),
        },
    )
    return node


def _domain_for_slug(domain_slug: str | None) -> Domain | None:
    if not domain_slug:
        return None
    return Domain.objects.filter(slug=str(domain_slug).strip()).first()


def record_sync_run_started(*, direction: str, domain_slug: str | None = None, source_url: str = "") -> SyncRun:
    return SyncRun.objects.create(
        domain=_domain_for_slug(domain_slug),
        node=ensure_local_node_config(),
        direction=direction,
        status="started",
        source_url=source_url,
    )


def record_sync_run_finished(run: SyncRun, *, status: str, summary: dict[str, Any] | None = None, error_message: str = "") -> SyncRun:
    run.status = status
    run.summary_json = summary or {}
    run.error_message = error_message
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "summary_json", "error_message", "completed_at"])
    return run


def domain_metadata_snapshot(domain: Domain, *, include_projects: bool = True, include_documents: bool = True) -> dict[str, Any]:
    project_qs = InfoSiteProject.objects.filter(domain=domain.slug).order_by("id")
    projects = (
        [project_metadata_snapshot(project, include_documents=include_documents) for project in project_qs]
        if include_projects
        else []
    )
    return {
        "slug": domain.slug,
        "display_name": domain.display_name,
        "description": domain.description,
        "home_node": domain.home_node,
        "sync_mode": domain.sync_mode,
        "visibility": domain.visibility,
        "last_sync_at": domain.last_sync_at.isoformat() if domain.last_sync_at else None,
        "project_count": len(projects) if include_projects else project_qs.count(),
        "projects": projects,
    }


def project_metadata_snapshot(project: InfoSiteProject, *, include_documents: bool = True) -> dict[str, Any]:
    return {
        "remote_id": project.id,
        "title": project.title,
        "domain": project.domain,
        "working_title": project.working_title,
        "description": project.description,
        "source_directory": project.source_directory,
        "site_structure": project.site_structure,
        "enabled": project.enabled,
        "auto_discover": project.auto_discover,
        "sync_status": project.sync_status,
        "last_sync_at": project.last_sync_at.isoformat() if project.last_sync_at else None,
        "last_sync_error": project.last_sync_error,
        "generation_status": project.generation_status,
        "output_dir": project.output_dir,
        "generated_at": project.generated_at.isoformat() if project.generated_at else None,
        "generation_error": project.generation_error,
        "version_count": project.version_count,
        "generate_html_site": project.generate_html_site,
        "html_site_generated": project.html_site_generated,
        "updated_at": project.updated_at.isoformat() if project.updated_at else None,
        "documents": [
            source_document_metadata_snapshot(document)
            for document in project.documents.order_by("file_path")
        ]
        if include_documents
        else [],
    }


def source_document_metadata_snapshot(document: SourceDocument) -> dict[str, Any]:
    return {
        "file_path": document.file_path,
        "file_type": document.file_type,
        "title": document.title,
        "file_size": document.file_size,
        "modified_at": document.modified_at.isoformat() if document.modified_at else None,
        "import_status": document.import_status,
        "imported": document.imported,
        "imported_at": document.imported_at.isoformat() if document.imported_at else None,
        "import_error": document.import_error,
        "review_status": document.review_status,
        "editor_notes": document.editor_notes,
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


def local_sync_payload(
    domains: list[str] | None = None,
    *,
    include_projects: bool = True,
    include_documents: bool = True,
    include_knowledge: bool = True,
) -> dict[str, Any]:
    """Export payload; the include_* switches skip work instead of discarding results."""
    node = ensure_local_node_config()
    queryset = Domain.objects.all().order_by("slug")
    if domains:
        queryset = queryset.filter(slug__in=domains)
    payload = {
        "node": asdict(local_node_snapshot()),
        "registered_node": {
            "node_id": node.node_id,
            "role": node.role,
            "sync_on_connect": node.sync_on_connect,
            "is_enabled": node.is_enabled,
            "last_seen_at": node.last_seen_at.isoformat() if node.last_seen_at else None,
        },
        "domains": [
            domain_metadata_snapshot(domain, include_projects=include_projects, include_documents=include_documents)
            for domain in queryset
        ],
        "generated_at": timezone.now().isoformat(),
    }
    by_slug = (
        {entry["slug"]: entry for entry in knowledge_sync_payload(domains or None)["domains"]}
        if include_knowledge
        else {}
    )
    for domain in payload["domains"]:
        knowledge_entry = by_slug.get(domain["slug"], {})
        domain["knowledge_sources"] = knowledge_entry.get("knowledge_sources", [])
        domain["knowledge_records"] = knowledge_entry.get("knowledge_records", [])
        domain["knowledge_artifacts"] = knowledge_entry.get("knowledge_artifacts", [])
        domain["knowledge_relations"] = knowledge_entry.get("knowledge_relations", [])
    return payload


def remote_domain_catalog(*, master_url: str | None = None) -> dict[str, Any]:
    from .distributed_api import build_domain_catalog_from_payload

    target_master_url = (master_url or resolved_master_url()).strip()
    if not target_master_url:
        raise ValueError("master_url not configured")

    payload = sync_client(target_master_url).export(
        include_projects=False, include_documents=False, include_knowledge=False
    )
    return {"master_url": target_master_url, **build_domain_catalog_from_payload(payload)}


def known_host_registry() -> list[NodeConfig]:
    return list(
        NodeConfig.objects.exclude(node_id=current_node_id())
        .exclude(role="standalone")
        .order_by("-last_seen_at", "node_id")
    )


def trigger_host_pull(*, host_node_id: str, domains: list[str] | None = None) -> dict[str, Any]:
    host = NodeConfig.objects.filter(node_id=str(host_node_id).strip()).first()
    if host is None:
        raise ValueError("unknown host node")
    if host.role != "host":
        raise ValueError("selected node is not a host")
    host_url = str(host.base_url or "").strip()
    if not host_url:
        raise ValueError("host base_url not configured")

    requested = normalize_domains(domains)
    operation_id = new_operation_id()
    result = sync_client(host_url).trigger_pull(domains=requested, operation_id=operation_id)
    return {
        "host_node_id": host.node_id,
        "host_url": host_url,
        "requested_domains": requested,
        "operation_id": operation_id,
        **result,
    }


def knowledge_source_snapshot(source: KnowledgeSource) -> dict[str, Any]:
    return {
        "source_id": source.source_id,
        "source_type": source.source_type,
        "title": source.title,
        "location": source.location,
        "metadata": source.metadata,
    }


def knowledge_record_snapshot(record: KnowledgeBlockRecord) -> dict[str, Any]:
    return {
        "block_id": record.block_id,
        "source_id": record.source_id,
        "block_type": record.block_type,
        "title": record.title,
        "content": record.content,
        "parent_block_id": record.parent_block_id,
        "path": record.path,
        "order_index": record.order_index,
        "tags": record.tags,
        "metadata": record.metadata,
        "object_type": record.object_type,
    }


def knowledge_artifact_snapshot(artifact: KnowledgeArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "artifact_type": artifact.artifact_type,
        "source_id": artifact.source_id,
        "source_block_ids": artifact.source_block_ids,
        "content": artifact.content,
        "metadata": artifact.metadata,
    }


def knowledge_relation_snapshot(relation: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_block_id": str(relation.get("source_block_id", "")).strip(),
        "target_block_id": str(relation.get("target_block_id", "")).strip(),
        "relation": str(relation.get("relation", "")).strip(),
        "weight": float(relation.get("weight", 1.0) or 1.0),
        "metadata": relation.get("metadata") if isinstance(relation.get("metadata"), dict) else {},
    }


def knowledge_sync_payload(domains: list[str] | None = None) -> dict[str, Any]:
    store_obj = store()
    resolved_domains = domains or [domain.slug for domain in Domain.objects.all().order_by("slug")]
    domain_entries: list[dict[str, Any]] = []
    for domain_slug in resolved_domains:
        sources = _domain_scoped_sources(domain_slug)
        source_snapshots = [knowledge_source_snapshot(source) for source in sources]
        records: list[dict[str, Any]] = []
        artifacts: list[dict[str, Any]] = []
        relation_rows: list[dict[str, Any]] = []
        block_ids: list[str] = []
        for source in sources:
            source_records = store_obj.list_records(source_id=source.source_id)
            records.extend(knowledge_record_snapshot(record) for record in source_records)
            artifacts.extend(
                knowledge_artifact_snapshot(artifact)
                for artifact in store_obj.list_artifacts(source_id=source.source_id)
            )
            block_ids.extend(record.block_id for record in source_records)
        relation_rows.extend(
            knowledge_relation_snapshot(relation)
            for relation in store_obj.list_relations_for_blocks(block_ids)
        )
        domain_entries.append(
            {
                "slug": domain_slug,
                "knowledge_sources": source_snapshots,
                "knowledge_records": records,
                "knowledge_artifacts": artifacts,
                "knowledge_relations": relation_rows,
            }
        )
    return {
        "node": asdict(local_node_snapshot()),
        "domains": domain_entries,
        "generated_at": timezone.now().isoformat(),
    }


def _parse_dt(value: Any):
    if not value:
        return None
    return timezone.datetime.fromisoformat(str(value))


def _upsert_project(domain: Domain, payload: dict[str, Any]) -> InfoSiteProject:
    project, _ = InfoSiteProject.objects.update_or_create(
        domain=domain.slug,
        working_title=str(payload.get("working_title", "")).strip(),
        defaults={
            "title": str(payload.get("title", "")).strip() or str(payload.get("working_title", "")).strip() or domain.slug,
            "description": str(payload.get("description", "")).strip(),
            "source_directory": str(payload.get("source_directory", "")).strip(),
            "site_structure": payload.get("site_structure") if isinstance(payload.get("site_structure"), (dict, list)) else {},
            "enabled": bool(payload.get("enabled", True)),
            "auto_discover": bool(payload.get("auto_discover", True)),
            "sync_status": str(payload.get("sync_status", "pending")).strip() or "pending",
            "last_sync_at": _parse_dt(payload.get("last_sync_at")),
            "last_sync_error": str(payload.get("last_sync_error", "")).strip(),
            "generation_status": str(payload.get("generation_status", "pending")).strip() or "pending",
            "output_dir": str(payload.get("output_dir", "")).strip(),
            "generated_at": _parse_dt(payload.get("generated_at")),
            "generation_error": str(payload.get("generation_error", "")).strip(),
            "version_count": int(payload.get("version_count", 0) or 0),
            "generate_html_site": bool(payload.get("generate_html_site", False)),
            "html_site_generated": bool(payload.get("html_site_generated", False)),
        },
    )
    return project


def _upsert_source_document(project: InfoSiteProject, payload: dict[str, Any]) -> SourceDocument:
    document, _ = SourceDocument.objects.update_or_create(
        project=project,
        file_path=str(payload.get("file_path", "")).strip(),
        defaults={
            "file_type": str(payload.get("file_type", "other")).strip() or "other",
            "title": str(payload.get("title", "")).strip(),
            "file_size": payload.get("file_size"),
            "modified_at": _parse_dt(payload.get("modified_at")),
            "import_status": str(payload.get("import_status", "discovered")).strip() or "discovered",
            "imported": bool(payload.get("imported", False)),
            "imported_at": _parse_dt(payload.get("imported_at")),
            "import_error": str(payload.get("import_error", "")).strip(),
            "review_status": str(payload.get("review_status", "none")).strip() or "none",
            "editor_notes": str(payload.get("editor_notes", "")).strip(),
        },
    )
    return document


def _upsert_knowledge_source(store_obj: KnowledgeStore, payload: dict[str, Any]) -> None:
    store_obj.upsert_source(
        KnowledgeSource(
            source_id=str(payload.get("source_id", "")).strip(),
            source_type=str(payload.get("source_type", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            location=str(payload.get("location", "")).strip(),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    )


def _upsert_knowledge_record(store_obj: KnowledgeStore, payload: dict[str, Any]) -> None:
    source_id = str(payload.get("source_id", "")).strip()
    block_id = str(payload.get("block_id", "")).strip()
    if not source_id or not block_id:
        return
    store_obj.upsert_record(
        KnowledgeBlockRecord(
            block_id=block_id,
            source_id=source_id,
            block_type=str(payload.get("block_type", "")).strip(),
            title=str(payload.get("title", "")).strip(),
            content=str(payload.get("content", "")).strip(),
            parent_block_id=str(payload.get("parent_block_id", "")).strip() or None,
            path=str(payload.get("path", "")).strip(),
            order_index=int(payload.get("order_index", 0) or 0),
            tags=[str(tag) for tag in payload.get("tags", []) if str(tag).strip()],
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
            object_type=str(payload.get("object_type", "")).strip(),
        )
    )


def _upsert_knowledge_artifact(store_obj: KnowledgeStore, payload: dict[str, Any]) -> None:
    artifact_id = str(payload.get("artifact_id", "")).strip()
    source_id = str(payload.get("source_id", "")).strip()
    if not artifact_id or not source_id:
        return
    store_obj.upsert_artifact(
        KnowledgeArtifact(
            artifact_id=artifact_id,
            artifact_type=str(payload.get("artifact_type", "")).strip(),
            source_id=source_id,
            source_block_ids=[str(block_id) for block_id in payload.get("source_block_ids", []) if str(block_id).strip()],
            content=str(payload.get("content", "")).strip(),
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
        )
    )


def _upsert_knowledge_relation(store_obj: KnowledgeStore, payload: dict[str, Any]) -> None:
    relation = KnowledgeRelationRecord(
        source_block_id=str(payload.get("source_block_id", "")).strip(),
        target_block_id=str(payload.get("target_block_id", "")).strip(),
        relation=str(payload.get("relation", "")).strip() or "related_to",
        weight=float(payload.get("weight", 1.0) or 1.0),
        metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    )
    if not relation.source_block_id or not relation.target_block_id:
        return
    store_obj.add_relation(
        relation.source_block_id,
        relation.target_block_id,
        relation=relation.relation,
        weight=relation.weight,
        metadata=relation.metadata,
    )


def apply_remote_node_heartbeat(payload: dict[str, Any]) -> NodeConfig:
    node_id = str(payload.get("node_id", "")).strip()
    if not node_id:
        raise ValueError("node_id missing")
    # additive shared-node field; older hosts do not send it
    remote_federation = str(payload.get("federation_id", "") or "").strip()
    local_federation = (Config.from_env().distributed_federation_id or "default").strip()
    if remote_federation and remote_federation != local_federation:
        raise ValueError(f"node belongs to federation {remote_federation!r}, not {local_federation!r}")
    node, _ = NodeConfig.objects.update_or_create(
        node_id=node_id,
        defaults={
            "display_name": str(payload.get("display_name", "")).strip(),
            "role": str(payload.get("role", "host")).strip() or "host",
            "base_url": str(payload.get("base_url", "")).strip(),
            "sync_on_connect": bool(payload.get("sync_on_connect", True)),
            "is_enabled": bool(payload.get("is_enabled", True)),
            "last_seen_at": timezone.now(),
        },
    )
    return node


def apply_remote_domain_payload(payload: dict[str, Any]) -> dict[str, Any]:
    remote_node_id = str(payload.get("node_id", "")).strip()
    if not remote_node_id:
        raise ValueError("node_id missing")
    domains = payload.get("domains")
    if not isinstance(domains, list):
        raise ValueError("domains must be a list")

    applied: list[dict[str, Any]] = []
    for item in domains:
        if not isinstance(item, dict):
            continue
        slug = str(item.get("slug", "")).strip()
        if not slug:
            continue
        domain, created = Domain.objects.get_or_create(
            slug=slug,
            defaults={
                "display_name": str(item.get("display_name", "")).strip() or slug,
                "description": str(item.get("description", "")).strip(),
                "home_node": str(item.get("home_node", "")).strip() or remote_node_id,
                "sync_mode": str(item.get("sync_mode", "push")).strip() or "push",
                "visibility": str(item.get("visibility", "private")).strip() or "private",
                "last_sync_at": timezone.now(),
            },
        )
        updated_fields: list[str] = []
        if not created:
            target_home_node = str(item.get("home_node", "")).strip() or domain.home_node or remote_node_id
            next_values = {
                "display_name": str(item.get("display_name", "")).strip() or domain.display_name or slug,
                "description": str(item.get("description", "")).strip(),
                "sync_mode": str(item.get("sync_mode", "")).strip() or domain.sync_mode,
                "visibility": str(item.get("visibility", "")).strip() or domain.visibility,
                "last_sync_at": timezone.now(),
            }
            if not domain.home_node:
                next_values["home_node"] = target_home_node
            for field_name, next_value in next_values.items():
                if getattr(domain, field_name) != next_value:
                    setattr(domain, field_name, next_value)
                    updated_fields.append(field_name)
            if updated_fields:
                domain.save(update_fields=updated_fields)
        projects_payload = item.get("projects")
        applied_projects: list[dict[str, Any]] = []
        applied_documents: list[dict[str, Any]] = []
        if isinstance(projects_payload, list):
            for project_payload in projects_payload:
                if not isinstance(project_payload, dict):
                    continue
                project = _upsert_project(domain, project_payload)
                applied_projects.append(
                    {
                        "title": project.title,
                        "working_title": project.working_title,
                    }
                )
                documents_payload = project_payload.get("documents")
                if isinstance(documents_payload, list):
                    for document_payload in documents_payload:
                        if not isinstance(document_payload, dict):
                            continue
                        file_path = str(document_payload.get("file_path", "")).strip()
                        if not file_path:
                            continue
                        document = _upsert_source_document(project, document_payload)
                        applied_documents.append(
                            {
                                "project": project.working_title,
                                "file_path": document.file_path,
                            }
                        )
        knowledge_sources_payload = item.get("knowledge_sources")
        knowledge_records_payload = item.get("knowledge_records")
        knowledge_artifacts_payload = item.get("knowledge_artifacts")
        knowledge_relations_payload = item.get("knowledge_relations")
        applied_knowledge_sources = 0
        applied_knowledge_records = 0
        applied_knowledge_artifacts = 0
        applied_knowledge_relations = 0
        if (
            isinstance(knowledge_sources_payload, list)
            or isinstance(knowledge_records_payload, list)
            or isinstance(knowledge_artifacts_payload, list)
            or isinstance(knowledge_relations_payload, list)
        ):
            store_obj = store()
            if isinstance(knowledge_sources_payload, list):
                for source_payload in knowledge_sources_payload:
                    if not isinstance(source_payload, dict):
                        continue
                    if not str(source_payload.get("source_id", "")).strip():
                        continue
                    _upsert_knowledge_source(store_obj, source_payload)
                    applied_knowledge_sources += 1
            if isinstance(knowledge_records_payload, list):
                for record_payload in knowledge_records_payload:
                    if not isinstance(record_payload, dict):
                        continue
                    _upsert_knowledge_record(store_obj, record_payload)
                    applied_knowledge_records += 1
            if isinstance(knowledge_artifacts_payload, list):
                for artifact_payload in knowledge_artifacts_payload:
                    if not isinstance(artifact_payload, dict):
                        continue
                    _upsert_knowledge_artifact(store_obj, artifact_payload)
                    applied_knowledge_artifacts += 1
            if isinstance(knowledge_relations_payload, list):
                for relation_payload in knowledge_relations_payload:
                    if not isinstance(relation_payload, dict):
                        continue
                    _upsert_knowledge_relation(store_obj, relation_payload)
                    applied_knowledge_relations += 1
        applied.append(
            {
                "slug": domain.slug,
                "created": created,
                "home_node": domain.home_node,
                "sync_mode": domain.sync_mode,
                "visibility": domain.visibility,
                "projects": applied_projects,
                "documents": applied_documents,
                "knowledge_sources": applied_knowledge_sources,
                "knowledge_records": applied_knowledge_records,
                "knowledge_artifacts": applied_knowledge_artifacts,
                "knowledge_relations": applied_knowledge_relations,
            }
        )
    return {"applied_domains": applied, "count": len(applied)}


def pull_from_master(*, domains: list[str] | None = None, operation_id: str = "") -> dict[str, Any]:
    master_url = resolved_master_url()
    if not master_url:
        raise ValueError("master_url not configured")

    client = sync_client(master_url)
    export_url = client.url(PATH_EXPORT)
    requested = normalize_domains(domains)
    run = record_sync_run_started(direction="pull", domain_slug=requested[0] if requested else None, source_url=export_url)

    try:
        payload = client.export(domains=requested)
        result = apply_remote_domain_payload(payload)
        result["pulled_from"] = export_url
        result["requested_domains"] = requested
        if operation_id:
            result["operation_id"] = operation_id
        record_sync_run_finished(run, status="succeeded", summary=result)
        return result
    except Exception as exc:
        record_sync_run_finished(run, status="failed", error_message=str(exc))
        raise


def export_sync_summary(*, domains: list[str] | None = None) -> dict[str, Any]:
    primary_domain = domains[0] if domains else None
    run = record_sync_run_started(direction="export", domain_slug=primary_domain)
    try:
        payload = local_sync_payload(domains)
        domain_count = len(payload.get("domains", []))
        project_count = sum(len(domain.get("projects", [])) for domain in payload.get("domains", []))
        source_count = sum(len(domain.get("knowledge_sources", [])) for domain in payload.get("domains", []))
        record_count = sum(len(domain.get("knowledge_records", [])) for domain in payload.get("domains", []))
        result = {
            "domains": domain_count,
            "projects": project_count,
            "knowledge_sources": source_count,
            "knowledge_records": record_count,
        }
        record_sync_run_finished(run, status="succeeded", summary=result)
        return result
    except Exception as exc:
        record_sync_run_finished(run, status="failed", error_message=str(exc))
        raise

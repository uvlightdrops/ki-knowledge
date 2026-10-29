"""Knowledge store access, artifacts, API browsing and graph presentation."""

from __future__ import annotations

from typing import Any
import json

from django.conf import settings
from ki_knowledge.integrations.knowledge_graph import KnowledgeGraph
from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.generate import KnowledgeArtifactGenerator
from ki_knowledge.ui.knowledge_api_client import KnowledgeAPIClient, default_knowledge_api_url
from ki_knowledge.ui.knowledge_graph_viz import (
    create_pyvis_network,
    graph_dict_to_networkx,
    graph_statistics,
)
from ki_knowledge.ui.knowledge_workspace import build_markdown_tree
import networkx as nx

from .domain_registry import data_dir


def knowledge_api_default_url() -> str:
    return default_knowledge_api_url()


def knowledge_api_health(api_url: str | None = None) -> dict[str, Any]:
    client = KnowledgeAPIClient((api_url or knowledge_api_default_url()).strip())
    return client.health()


def knowledge_api_browser_context(
    *,
    api_url: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    query: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    client = KnowledgeAPIClient((api_url or knowledge_api_default_url()).strip())
    health = client.health()
    normalized_source_type = None if not source_type or source_type == "(all)" else source_type
    sources = client.list_sources(source_type=normalized_source_type)
    selected_source = None
    selected_source_id = (source_id or "").strip()
    if not selected_source_id and sources:
        selected_source_id = sources[0]["source_id"]
    if selected_source_id:
        selected_source = next((source for source in sources if source["source_id"] == selected_source_id), None)
        if selected_source is None:
            selected_source = client.get_source(selected_source_id)

    search_results = client.search_blocks(query, limit=limit) if query.strip() else []
    records = client.list_records(source_id=selected_source_id or None, limit=limit) if selected_source_id else []
    artifacts = client.list_artifacts(source_id=selected_source_id or None) if selected_source_id else []
    graph = client.get_source_graph(selected_source_id, limit=min(max(limit, 1) * 10, 400)) if selected_source_id else {}
    return {
        "client": client,
        "health": health,
        "status": str(health.get("status", "ok")),
        "sources": sources,
        "selected_source": selected_source,
        "selected_source_id": selected_source_id,
        "search_results": search_results,
        "records": records,
        "artifacts": artifacts,
        "graph": graph,
        "source_type": normalized_source_type or "(all)",
        "query": query,
        "limit": limit,
    }


def store() -> KnowledgeStore:
    return KnowledgeStore(settings.KNOWLEDGE_STORE_TARGET)


def root_markdown_tree(query: str = "", domain: str | None = None):
    return build_markdown_tree(data_dir(domain), query=query)


def generate_all_artifacts(source_id: str, max_items: int = 8) -> list[dict[str, Any]]:
    generator = KnowledgeArtifactGenerator(store())
    return [
        generator.generate_quiz_module(source_id, max_questions=max_items),
        generator.generate_flashcards(source_id, max_cards=max_items),
        generator.generate_summary_note(source_id, max_sections=max_items),
        generator.generate_glossary(source_id, max_terms=max_items),
        generator.generate_study_guide(source_id, max_items=max_items),
    ]


def graph_payload(source_id: str, limit: int = 400) -> dict[str, Any]:
    graph = KnowledgeGraph(settings.KNOWLEDGE_STORE_TARGET)
    return graph.source_graph_payload(store(), source_id=source_id, limit=limit)


def graph_context(source_id: str, limit: int = 400) -> dict[str, Any]:
    payload = graph_payload(source_id, limit=limit)
    network = create_pyvis_network(graph_dict_to_networkx(payload), physics_enabled=True)
    stats = graph_statistics(graph_dict_to_networkx(payload))
    return {
        "payload": payload,
        "graph_html": network.generate_html(),
        "stats": stats,
    }


def graph_3d_context(source_id: str, limit: int = 400) -> dict[str, Any]:
    payload = graph_payload(source_id, limit=limit)
    graph = graph_dict_to_networkx(payload)
    stats = graph_statistics(graph)
    if graph.number_of_nodes() == 0:
        return {"graph_3d": {"nodes": [], "edges": []}, "stats": stats}

    positions = nx.spring_layout(graph, dim=3, seed=42)
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for node_id, data in graph.nodes(data=True):
        pos = positions.get(node_id, [0.0, 0.0, 0.0])
        degree = graph.degree(node_id)
        nodes.append(
            {
                "id": node_id,
                "label": data.get("label", node_id),
                "node_type": data.get("node_type", "unknown"),
                "path": data.get("path", ""),
                "x": float(pos[0]),
                "y": float(pos[1]),
                "z": float(pos[2]),
                "size": max(4, min(22, 6 + degree)),
            }
        )

    for src, dst, edge_data in graph.edges(data=True):
        src_pos = positions.get(src, [0.0, 0.0, 0.0])
        dst_pos = positions.get(dst, [0.0, 0.0, 0.0])
        edges.append(
            {
                "source": src,
                "target": dst,
                "predicate": edge_data.get("predicate", ""),
                "weight": float(edge_data.get("weight", 1.0)),
                "x0": float(src_pos[0]),
                "y0": float(src_pos[1]),
                "z0": float(src_pos[2]),
                "x1": float(dst_pos[0]),
                "y1": float(dst_pos[1]),
                "z1": float(dst_pos[2]),
            }
        )

    return {
        "graph_3d": {"nodes": nodes, "edges": edges},
        "graph_3d_json": json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False),
        "stats": stats,
    }


def _candidate_record_ids_for_semantic_linking(limit: int = 1200, min_len: int = 40) -> list[str]:
    records = store().list_records(limit=limit)
    allowed_types = {"paragraph", "list_item", "code_block", "quote", "heading"}
    ids: list[str] = []
    for item in records:
        if item.block_type not in allowed_types:
            continue
        content = (item.content or "").strip()
        if len(content) < min_len:
            continue
        ids.append(item.block_id)
    return ids

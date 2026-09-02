"""Graph visualization helpers for the Streamlit knowledge explorer."""

from __future__ import annotations

from collections import Counter

import networkx as nx
from pyvis.network import Network


NODE_COLORS = {
    "quiz_module": "#FF6B6B",
    "knowledge_section": "#4ECDC4",
    "quiz_question": "#45B7D1",
    "quiz_option": "#74B9FF",
    "semantic_reference": "#F4A261",
    "heading": "#2A9D8F",
    "paragraph": "#A8DADC",
    "list_item": "#BDE0FE",
    "code_block": "#CDB4DB",
    "issue_summary": "#E76F51",
    "issue_description": "#F4A261",
    "issue_text_field": "#E9C46A",
    "ontology_concept": "#9B5DE5",
}


def graph_dict_to_networkx(graph_data: dict) -> nx.DiGraph:
    """Convert API graph payload to a NetworkX digraph."""
    graph = nx.DiGraph()
    for node in graph_data.get("nodes", []):
        graph.add_node(
            node["node_id"],
            label=node.get("label", node["node_id"]),
            node_type=node.get("node_type", "unknown"),
            path=node.get("path", ""),
            metadata=node.get("metadata", {}),
        )
    for edge in graph_data.get("edges", []):
        graph.add_edge(
            edge["source"],
            edge["target"],
            predicate=edge.get("predicate", ""),
            weight=edge.get("weight", 1.0),
            metadata=edge.get("metadata", {}),
        )
    return graph


def create_pyvis_network(graph: nx.DiGraph, *, physics_enabled: bool = True) -> Network:
    """Create a PyVis network from a NetworkX graph."""
    net = Network(height="680px", width="100%", directed=True, notebook=False)
    for node_id, data in graph.nodes(data=True):
        node_type = data.get("node_type", "unknown")
        label = data.get("label", node_id)
        title = f"{node_type}: {label}"
        if data.get("path"):
            title += f"\n{data['path']}"
        net.add_node(
            node_id,
            label=label,
            title=title,
            color=NODE_COLORS.get(node_type, "#CCCCCC"),
            size=24,
            physics=True,
        )

    for source, target, data in graph.edges(data=True):
        net.add_edge(
            source,
            target,
            label=data.get("predicate", ""),
            title=f"{data.get('predicate', '')} (w={float(data.get('weight', 1.0)):.2f})",
            value=max(float(data.get("weight", 1.0)), 0.2),
        )

    net.toggle_physics(physics_enabled)
    net.set_options(
        """
        {
          "physics": {
            "enabled": true,
            "barnesHut": {
              "gravitationalConstant": -12000,
              "centralGravity": 0.2,
              "springLength": 130,
              "springConstant": 0.05
            }
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          }
        }
        """
    )
    return net


def graph_statistics(graph: nx.DiGraph) -> dict:
    """Return basic graph statistics for UI display."""
    node_types = Counter(graph.nodes[node].get("node_type", "unknown") for node in graph.nodes())
    predicates = Counter(data.get("predicate", "unknown") for _, _, data in graph.edges(data=True))
    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "node_types": dict(node_types),
        "edge_predicates": dict(predicates),
        "density": nx.density(graph) if graph.number_of_nodes() > 1 else 0.0,
    }


def ontology_concepts_to_networkx(concepts: list[object]) -> nx.DiGraph:
    """Convert parsed ontology concepts into a NetworkX graph."""
    graph = nx.DiGraph()
    concept_map: dict[str, object] = {}
    for concept in concepts:
        concept_id = str(getattr(concept, "concept_id", "")).strip()
        if not concept_id:
            continue
        concept_map[concept_id] = concept
        graph.add_node(
            concept_id,
            label=str(getattr(concept, "label", "")).strip() or concept_id,
            node_type="ontology_concept",
            path=concept_id,
            metadata={
                "quality_score": getattr(concept, "quality_score", 0),
                "source_format": getattr(concept, "source_format", ""),
                "relations": list(getattr(concept, "relations", [])),
            },
        )

    for concept_id, concept in concept_map.items():
        for raw_relation in getattr(concept, "relations", []):
            relation, _, target_id = str(raw_relation or "").partition("->")
            target_id = target_id.strip()
            if not relation or not target_id or target_id not in concept_map:
                continue
            graph.add_edge(
                concept_id,
                target_id,
                predicate=relation.rsplit(":", 1)[-1],
                weight=1.0,
                metadata={},
            )
    return graph

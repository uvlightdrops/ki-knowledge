"""Ontology parsing and conversion into knowledge-ready markdown."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from rdflib import Graph, Namespace
from rdflib.namespace import OWL, RDF, RDFS, SKOS


@dataclass
class OntologyConcept:
    concept_id: str
    label: str
    definition: str
    relations: list[str]
    source_format: str
    quality_score: int


@dataclass
class OntologyDocument:
    source_url: str
    source_format: str
    title: str
    concepts: list[OntologyConcept]


def fetch_ontology_url(url: str, timeout: int = 30) -> tuple[str, str]:
    """Fetch ontology file from a web URL."""
    response = requests.get(
        url,
        timeout=timeout,
        headers={
            "User-Agent": "ki-knowledge-ontology-ingest/1.0 (+https://github.com/uvlightdrops/ki-knowledge)",
            "Accept": "application/rdf+xml, application/ld+json, text/turtle, application/json;q=0.8, */*;q=0.5",
        },
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    return response.text, content_type


def parse_ontology_text(
    text: str,
    *,
    source_url: str = "",
    content_type: str = "",
    title: str | None = None,
) -> OntologyDocument:
    """Parse ontology text (JSON-LD or RDF/XML) into normalized concepts."""
    normalized = text.lstrip()
    if _looks_like_turtle(content_type, normalized, source_url):
        concepts = _parse_turtle_concepts(text)
        source_format = "turtle"
    elif _looks_like_json(content_type, normalized):
        concepts = _parse_jsonld_concepts(text)
        source_format = "jsonld"
    else:
        try:
            concepts = _parse_rdfxml_concepts(text)
            source_format = "rdfxml"
        except ET.ParseError:
            concepts = _parse_turtle_concepts(text)
            source_format = "turtle"

    doc_title = title or _derive_title(source_url, source_format)
    return OntologyDocument(
        source_url=source_url,
        source_format=source_format,
        title=doc_title,
        concepts=sorted(concepts, key=lambda c: c.quality_score, reverse=True),
    )


def write_ontology_markdown(
    document: OntologyDocument,
    output_path: Path,
    *,
    focus_terms: list[str] | None = None,
    top_n: int = 50,
) -> Path:
    """Write extracted ontology concepts as markdown knowledge source."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    selected = select_high_quality_concepts(document.concepts, top_n=top_n, focus_terms=focus_terms)

    lines = [
        f"# Ontology Import: {document.title}",
        "",
        f"- Source URL: {document.source_url or '(local file)'}",
        f"- Source format: {document.source_format}",
        f"- Concepts parsed: {len(document.concepts)}",
        f"- High-quality concepts selected: {len(selected)}",
        "",
        "## Summary",
        "",
        (
            "Automatisch extrahierte Ontologie-Begriffe mit Qualitätsbewertung. "
            "Berücksichtigt werden Label, Definitionstiefe und semantische Relationen."
        ),
        "",
        "## High-quality concepts",
        "",
    ]

    for idx, concept in enumerate(selected, start=1):
        lines.extend(
            [
                f"### {idx}. {concept.label}",
                f"- id: `{concept.concept_id}`",
                f"- quality_score: {concept.quality_score}",
                f"- source_format: {concept.source_format}",
                f"- relations: {', '.join(concept.relations[:8]) if concept.relations else '(none)'}",
                "",
                concept.definition or "_No definition provided._",
                "",
            ]
        )

    output_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
    return output_path


def select_high_quality_concepts(
    concepts: list[OntologyConcept],
    *,
    top_n: int = 50,
    focus_terms: list[str] | None = None,
) -> list[OntologyConcept]:
    """Pick best concepts by score, optionally biased to focus terms."""
    focus = [item.strip().lower() for item in (focus_terms or []) if item.strip()]
    ranked = sorted(concepts, key=lambda c: c.quality_score, reverse=True)
    if not focus:
        return ranked[:top_n]

    def is_focus(concept: OntologyConcept) -> bool:
        haystack = f"{concept.label} {concept.definition}".lower()
        return any(term in haystack for term in focus)

    focused = [concept for concept in ranked if is_focus(concept)]
    if len(focused) >= top_n:
        return focused[:top_n]

    used = {concept.concept_id for concept in focused}
    for concept in ranked:
        if concept.concept_id in used:
            continue
        focused.append(concept)
        if len(focused) >= top_n:
            break
    return focused


def _parse_jsonld_concepts(text: str) -> list[OntologyConcept]:
    payload = json.loads(text)
    nodes: list[dict[str, Any]]
    if isinstance(payload, dict) and isinstance(payload.get("@graph"), list):
        nodes = [node for node in payload["@graph"] if isinstance(node, dict)]
    elif isinstance(payload, list):
        nodes = [node for node in payload if isinstance(node, dict)]
    elif isinstance(payload, dict):
        nodes = [payload]
    else:
        nodes = []

    concepts: list[OntologyConcept] = []
    for node in nodes:
        concept_id = _as_text(node.get("@id")) or _as_text(node.get("id"))
        if not concept_id:
            continue
        label = _first_text(
            node,
            keys=("rdfs:label", "skos:prefLabel", "label", "name"),
        )
        definition = _first_text(
            node,
            keys=("definition", "skos:definition", "rdfs:comment", "comment", "description"),
        )
        relations = _extract_jsonld_relations(node)
        quality = _quality_score(label=label, definition=definition, relations=relations)
        concepts.append(
            OntologyConcept(
                concept_id=concept_id,
                label=label or _id_tail(concept_id),
                definition=definition,
                relations=relations,
                source_format="jsonld",
                quality_score=quality,
            )
        )
    return _deduplicate_concepts(concepts)


def _parse_rdfxml_concepts(text: str) -> list[OntologyConcept]:
    root = ET.fromstring(text)
    concepts: list[OntologyConcept] = []
    for element in root.iter():
        if not _looks_like_concept_tag(element.tag):
            continue
        concept_id = (
            element.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}about")
            or element.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}ID")
            or element.attrib.get("about")
            or element.attrib.get("ID")
        )
        if not concept_id:
            continue
        label = _find_child_text(
            element,
            suffixes=("label", "prefLabel", "name"),
        )
        definition = _find_child_text(
            element,
            suffixes=("definition", "comment", "description"),
        )
        relations = _extract_xml_relations(element)
        quality = _quality_score(label=label, definition=definition, relations=relations)
        concepts.append(
            OntologyConcept(
                concept_id=concept_id,
                label=label or _id_tail(concept_id),
                definition=definition,
                relations=relations,
                source_format="rdfxml",
                quality_score=quality,
            )
        )
    return _deduplicate_concepts(concepts)


def _parse_turtle_concepts(text: str) -> list[OntologyConcept]:
    graph = Graph()
    graph.parse(data=text, format="turtle")

    UCO = Namespace("https://ontology.unifiedcyberontology.org/uco/")
    accepted_types = {
        OWL.Class,
        SKOS.Concept,
        RDFS.Class,
        UCO.UcoObject,
    }

    concepts: list[OntologyConcept] = []
    candidate_subjects = set(graph.subjects(RDF.type, None))
    for predicate in (RDFS.label, SKOS.prefLabel, SKOS.definition, RDFS.comment, RDFS.subClassOf):
        candidate_subjects.update(graph.subjects(predicate, None))

    for subject in candidate_subjects:
        concept_id = str(subject)
        if not concept_id.startswith(("http://", "https://", "urn:")):
            continue

        types = set(graph.objects(subject, RDF.type))
        label = _first_graph_literal(graph, subject, [RDFS.label, SKOS.prefLabel])
        definition = _first_graph_literal(
            graph,
            subject,
            [SKOS.definition, RDFS.comment],
        )
        relations = _graph_relations(graph, subject)
        if not label and not definition and not relations and not any(item in accepted_types for item in types):
            continue
        quality = _quality_score(label=label, definition=definition, relations=relations)
        concepts.append(
            OntologyConcept(
                concept_id=concept_id,
                label=label or _id_tail(concept_id),
                definition=definition,
                relations=relations,
                source_format="turtle",
                quality_score=quality,
            )
        )
    return _deduplicate_concepts(concepts)


def _extract_jsonld_relations(node: dict[str, Any]) -> list[str]:
    relation_keys = (
        "skos:broader",
        "skos:narrower",
        "skos:related",
        "broader",
        "narrower",
        "related",
        "subClassOf",
        "rdfs:subClassOf",
    )
    relations: list[str] = []
    for key in relation_keys:
        raw = node.get(key)
        if raw is None:
            continue
        values = raw if isinstance(raw, list) else [raw]
        for value in values:
            if isinstance(value, dict):
                target = _as_text(value.get("@id")) or _as_text(value.get("id"))
            else:
                target = _as_text(value)
            if target:
                relations.append(f"{key}->{target}")
    return relations


def _extract_xml_relations(element: ET.Element) -> list[str]:
    relation_tags = {"broader", "narrower", "related", "subclassof"}
    relations: list[str] = []
    for child in list(element):
        local = _tag_local_name(child.tag).lower()
        if local not in relation_tags:
            continue
        target = (
            child.attrib.get("{http://www.w3.org/1999/02/22-rdf-syntax-ns#}resource")
            or child.attrib.get("resource")
            or (child.text or "").strip()
        )
        if target:
            relations.append(f"{local}->{target}")
    return relations


def _deduplicate_concepts(concepts: list[OntologyConcept]) -> list[OntologyConcept]:
    merged: dict[str, OntologyConcept] = {}
    for concept in concepts:
        existing = merged.get(concept.concept_id)
        if existing is None or concept.quality_score > existing.quality_score:
            merged[concept.concept_id] = concept
    return list(merged.values())


def _quality_score(*, label: str, definition: str, relations: list[str]) -> int:
    score = 0
    if label.strip():
        score += 2
    definition_len = len(definition.strip())
    if definition_len >= 60:
        score += 2
    elif definition_len >= 20:
        score += 1
    score += min(len(relations), 4)
    return score


def _first_text(node: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = node.get(key)
        text = _as_text(value)
        if text:
            return text
    return ""


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in value:
            text = _as_text(item)
            if text:
                return text
        return ""
    if isinstance(value, dict):
        for key in ("@value", "value", "text", "@id", "id"):
            text = _as_text(value.get(key))
            if text:
                return text
        return ""
    return str(value).strip()


def _find_child_text(element: ET.Element, suffixes: tuple[str, ...]) -> str:
    suffix_set = {item.lower() for item in suffixes}
    for child in list(element):
        local = _tag_local_name(child.tag).lower()
        if local in suffix_set and (child.text or "").strip():
            return child.text.strip()
    return ""


def _looks_like_concept_tag(tag: str) -> bool:
    local = _tag_local_name(tag).lower()
    return local in {"class", "concept", "description", "namedindividual"}


def _tag_local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _looks_like_json(content_type: str, text: str) -> bool:
    ct = content_type.lower()
    if "json" in ct or "ld+json" in ct:
        return True
    return text.startswith("{") or text.startswith("[")


def _looks_like_turtle(content_type: str, text: str, source_url: str = "") -> bool:
    ct = content_type.lower()
    if "text/turtle" in ct or "application/x-turtle" in ct or "application/n-triples" in ct:
        return True
    if source_url.lower().endswith(".ttl") or source_url.lower().endswith(".nt"):
        return True
    prefix = text[:250].lower()
    return "@prefix " in prefix or prefix.startswith("prefix ")


def _derive_title(source_url: str, source_format: str) -> str:
    if source_url:
        parsed = urlparse(source_url)
        name = Path(parsed.path).name or parsed.netloc or "ontology"
        clean = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")
        return clean or f"ontology_{source_format}"
    return f"ontology_{source_format}"


def _id_tail(concept_id: str) -> str:
    tail = concept_id.rsplit("/", 1)[-1].rsplit("#", 1)[-1]
    tail = tail.strip()
    return tail or concept_id


def _first_graph_literal(graph: Graph, subject, predicates: list) -> str:
    for predicate in predicates:
        for obj in graph.objects(subject, predicate):
            value = str(obj).strip()
            if value:
                return value
    return ""


def _graph_relations(graph: Graph, subject) -> list[str]:
    relation_predicates = {
        SKOS.broader,
        SKOS.narrower,
        SKOS.related,
        RDFS.subClassOf,
    }
    relations: list[str] = []
    for predicate in relation_predicates:
        for target in graph.objects(subject, predicate):
            relations.append(f"{_id_tail(str(predicate))}->{str(target)}")
    return relations


def import_ontology_to_store(
    text: str,
    *,
    source_url: str = "",
    content_type: str = "",
    title: str | None = None,
    store: Any = None,
    top_n: int = 50,
) -> tuple[int, str]:
    """Parse ontology text and import concepts directly as OWL source records.
    
    Args:
        text: Ontology content (RDF/XML, Turtle, JSON-LD)
        source_url: URL or identifier for the ontology
        content_type: Content type hint
        title: Optional title override
        store: KnowledgeStore instance (uses default if None)
        top_n: Number of high-quality concepts to import
    
    Returns:
        Tuple of (record_count, source_id)
    """
    from ki_knowledge.knowledge.adapters import OntologyKnowledgeAdapter
    from ki_knowledge.knowledge.models import KnowledgeSource

    if store is None:
        from ki_knowledge.django_site.services import store as get_store

        store = get_store()

    document = parse_ontology_text(text, source_url=source_url, content_type=content_type, title=title)
    selected_concepts = select_high_quality_concepts(document.concepts, top_n=top_n)

    source_id = f"owl:{_slug_from_url(source_url) or document.title.lower().replace(' ', '_')}"
    source = KnowledgeSource(
        source_id=source_id,
        source_type="owl",
        title=document.title,
        location=source_url,
        metadata={"source_format": document.source_format, "concepts_parsed": len(document.concepts)},
    )

    store.upsert_source(source)

    records = OntologyKnowledgeAdapter.to_records(selected_concepts, source)
    for record in records:
        store.upsert_record(record)
    selected_ids = {concept.concept_id for concept in selected_concepts}
    for concept in selected_concepts:
        for relation in concept.relations:
            relation_name, target_id = _split_relation_target(relation)
            if not relation_name or not target_id:
                continue
            if target_id == concept.concept_id or target_id not in selected_ids:
                continue
            store.add_relation(
                source_block_id=concept.concept_id,
                target_block_id=target_id,
                relation=relation_name,
                metadata={
                    "created_by": "ontology_import",
                    "source_format": concept.source_format,
                    "source_id": source_id,
                },
            )

    return len(records), source_id


def _split_relation_target(value: str) -> tuple[str, str]:
    relation, _, target = (value or "").partition("->")
    return _normalize_relation_name(relation), target.strip()


def _normalize_relation_name(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if ":" in raw:
        return raw.rsplit(":", 1)[-1]
    if "#" in raw or "/" in raw:
        return _id_tail(raw)
    return raw


def _slug_from_url(url: str) -> str:
    """Generate slug from URL."""
    if not url:
        return "ontology"
    parsed = urlparse(url)
    base = Path(parsed.path).stem or "ontology"
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", base).strip("-")
    return slug or "ontology"

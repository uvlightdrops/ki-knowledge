"""Tests for ontology web parsing and concept ranking."""

from ki_knowledge.integrations.knowledge_store import KnowledgeStore
from ki_knowledge.knowledge.ontology_ingest import import_ontology_to_store, parse_ontology_text, select_high_quality_concepts


def test_parse_jsonld_ontology_extracts_concepts():
    text = """
    {
      "@graph": [
        {
          "@id": "http://example.org/Psychology",
          "rdfs:label": "Psychology",
          "skos:definition": "Scientific study of mind and behavior with empirical methods.",
          "skos:broader": {"@id": "http://example.org/SocialScience"},
          "skos:related": [{"@id": "http://example.org/Cognition"}]
        },
        {
          "@id": "http://example.org/Cognition",
          "rdfs:label": "Cognition",
          "rdfs:comment": "Mental processes including attention and memory."
        }
      ]
    }
    """
    document = parse_ontology_text(text, source_url="https://example.org/psych.jsonld", content_type="application/ld+json")
    assert document.source_format == "jsonld"
    assert len(document.concepts) == 2
    best = document.concepts[0]
    assert best.label == "Psychology"
    assert best.quality_score >= 4


def test_parse_rdfxml_ontology_extracts_concepts():
    text = """
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
             xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
             xmlns:owl="http://www.w3.org/2002/07/owl#">
      <owl:Class rdf:about="http://example.org/Therapy">
        <rdfs:label>Therapy</rdfs:label>
        <rdfs:comment>Structured intervention to improve mental health outcomes.</rdfs:comment>
      </owl:Class>
    </rdf:RDF>
    """
    document = parse_ontology_text(text, source_url="https://example.org/psych.owl", content_type="application/rdf+xml")
    assert document.source_format == "rdfxml"
    assert len(document.concepts) == 1
    assert document.concepts[0].label == "Therapy"


def test_select_focus_concepts_biases_psychology_terms():
    text = """
    {
      "@graph": [
        {"@id":"a","label":"Database","description":"Storage system"},
        {"@id":"b","label":"Cognitive Bias","description":"Systematic pattern of deviation in judgment."},
        {"@id":"c","label":"Behavioral Therapy","description":"Evidence based psychotherapy approach."}
      ]
    }
    """
    document = parse_ontology_text(text, content_type="application/json")
    selected = select_high_quality_concepts(document.concepts, top_n=2, focus_terms=["psychology", "therapy", "cognitive"])
    labels = [item.label for item in selected]
    assert "Cognitive Bias" in labels or "Behavioral Therapy" in labels


def test_parse_turtle_ontology_extracts_concepts():
    text = """
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix skos: <http://www.w3.org/2004/02/skos/core#> .
    @prefix ex: <http://example.org/> .

    ex:SecurityControl a owl:Class ;
      rdfs:label "Security Control" ;
      skos:definition "A safeguard or countermeasure to reduce risk in IT systems." ;
      rdfs:subClassOf ex:Control .
    """
    document = parse_ontology_text(text, source_url="https://example.org/uco.ttl", content_type="text/turtle")
    assert document.source_format == "turtle"
    assert len(document.concepts) >= 1
    assert any(item.label == "Security Control" for item in document.concepts)


def test_import_ontology_creates_relations_between_imported_concepts(tmp_path):
    db_path = tmp_path / "knowledge.sqlite"
    store = KnowledgeStore(str(db_path))
    text = """
    @prefix owl: <http://www.w3.org/2002/07/owl#> .
    @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
    @prefix ex: <http://example.org/> .

    ex:Person a owl:Class ;
      rdfs:label "Person" .

    ex:Employee a owl:Class ;
      rdfs:label "Employee" ;
      rdfs:subClassOf ex:Person .
    """
    imported, source_id = import_ontology_to_store(
        text,
        source_url="https://example.org/people.owl",
        content_type="text/turtle",
        store=store,
        top_n=10,
    )
    assert imported == 2
    assert source_id.startswith("owl:")
    relations = store.list_relations_for_blocks(["http://example.org/Employee", "http://example.org/Person"])
    assert any(
        relation["source_block_id"] == "http://example.org/Employee"
        and relation["target_block_id"] == "http://example.org/Person"
        and relation["relation"] == "subClassOf"
        for relation in relations
    )

---
project: ki-knowledge
agent_project: ki-knowledge
scope: features
created: "2026-09-02 07"
updated: "2026-11-08 03"
update_reason: "Bestehende Records vom neuen fachlichen Wissensblockmodell abgegrenzt"
status: active
semantic_blocks:
  - purpose
  - capabilities
  - components
  - usage
  - extensions
  - curation-guidelines
relations:
  - target: archiv/KNOWLEDGE_BLOCKS_BOOK_CONCEPT.md
    type: reference
    reason: "Archivierter älterer Buch- und Kuratierungsansatz"
---

# Knowledge Blocks

> Source intake and UI are defined in
> [Source Workspace and Workflow Concept](../architecture/SOURCE-WORKSPACE-AND-WORKFLOW-CONCEPT.md).
> Block extraction is downstream of discovery and import; structural parsing
> alone does not constitute semantic understanding.

<a id="zweck"></a>
<a id="purpose"></a>
## Zweck [purpose]

Diese Seite beschreibt die automatische Zerlegung von Markdown und den
allgemeinen KnowledgeStore. Die manuell angelegten Markierungen und
Relationen der Textwerkstatt sind ein eigener Arbeitsweg; siehe
[Textwerkstatt-Anleitung](../guides/text-workbench.md) und
[Content-Modell](../architecture/CONTENT-MODEL-MATRIX.md).
Weder ein extrahierter `KnowledgeBlockRecord` noch eine Markierung ist
automatisch ein fachlicher Wissensblock im
[neuen Konzept](../architecture/TEXT-AND-KNOWLEDGE-BLOCKS.md#distinction).

<a id="was-es-kann"></a>
<a id="capabilities"></a>
## Was es kann [capabilities]

- Markdown in Blöcke zerlegen (Heading, Paragraph, List Item, Code Block)
- Records im KnowledgeStore speichern (SQLite oder PostgreSQL)
- Relationen zwischen Records speichern und daraus einen Graphen aufbauen
- im Beispielskript einfache lokale Bag-of-Words-Vektoren erzeugen

Die Zerlegung und ein angelegter Graph sind für sich genommen kein Nachweis
semantischen Verstehens. Der InfoSite-Blockspeicher ist ein separater
Verbraucher des Stores, nicht automatisch dieselbe Datenbank.

<a id="hauptkomponenten"></a>
<a id="components"></a>
## Hauptkomponenten [components]

- `ki_knowledge/integrations/markdown_blocks.py` – Parser und Datenmodell
- `ki_knowledge/integrations/knowledge_store.py` – persistente Speicherung
- `ki_knowledge/integrations/knowledge_graph.py` – Graph-Relationen
- `ki_knowledge/integrations/block_embeddings.py` – lokale Embeddings
- `ki_knowledge/api/knowledge_app.py` – FastAPI-API

<a id="nutzung"></a>
<a id="usage"></a>
## Nutzung [usage]

Die folgenden Beispiele verwenden den skriptbasierten Import; sie beschreiben
nicht die manuelle Textwerkstatt. `--embed` und `--graph` starten zusätzliche
Schreibvorgänge im gewählten Store beziehungsweise Graphen.

```bash
python examples/knowledge_block_import.py path/to/file.md --embed --graph
```

```bash
python examples/knowledge_block_import.py path/to/quiz.yaml --format iasem_quiz --graph
```

```bash
stackctl run api
```

Dann sind die Endpunkte unter `http://localhost:8090/docs` verfügbar.

<a id="erweiterungen"></a>
<a id="extensions"></a>
## Erweiterungen [extensions]

Im Wissensmodell gibt es unter anderem:

- `KnowledgeSource`
- `KnowledgeBlockRecord`
- `KnowledgeArtifact`

Es gibt außerdem Importadapter für `iasem`-Quiz-YAML und Ontologien.

Aus denselben Wissensbausteinen können Lernartefakte erzeugt werden:

- `generated_quiz_module`
- `flashcard_set`
- `summary_note`
- `glossary`
- `study_guide`

Zusätzlich gibt es:

- ein Streamlit-Beispiel für Source-/Record-/Artifact-Inspektion
- Graph-Visualisierung
- eine FastAPI unter `/api/knowledge/...`

<a id="leitlinien-für-review-und-kuratierung"></a>
<a id="curation-guidelines"></a>
## Frühere Leitlinien für Review und Kuratierung [curation-guidelines]

Der frühere buchzentrierte Ansatz ist [archiviert](archiv/KNOWLEDGE_BLOCKS_BOOK_CONCEPT.md).
Er legt das neue Wissensmodell nicht fest. Für die gemeinsam erarbeitete
Produktrichtung siehe [Product Direction](../architecture/SYSTEM_OVERVIEW.md#product-direction).

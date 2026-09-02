# Knowledge Blocks

## Zweck

Dieses Modul extrahiert hierarchische Elemente aus Markdown-Dateien und speichert sie als einzelne Wissensbausteine.

## Was es kann

- Markdown in Blöcke zerlegen (Heading, Paragraph, List Item, Code Block)
- Blöcke in SQLite speichern
- semantische Relationen anlegen
- einfache lokale Embeddings erzeugen
- Graph-Struktur über Blöcke aufbauen

## Hauptkomponenten

- `ki_knowledge/integrations/markdown_blocks.py` – Parser und Datenmodell
- `ki_knowledge/integrations/knowledge_store.py` – persistente Speicherung
- `ki_knowledge/integrations/knowledge_graph.py` – Graph-Relationen
- `ki_knowledge/integrations/block_embeddings.py` – lokale Embeddings
- `ki_knowledge/api/knowledge_app.py` – FastAPI-API

## Nutzung

```bash
python examples/knowledge_block_import.py path/to/file.md --embed --graph
```

```bash
python examples/knowledge_block_import.py path/to/quiz.yaml --format iasem_quiz --graph
```

```bash
python examples/run_knowledge_api.py
```

Dann sind die Endpunkte unter `http://localhost:8090/docs` verfügbar.

## Erweiterungen

Zusätzlich zu Markdown unterstützt der Store:

- `KnowledgeSource`
- `KnowledgeBlockRecord`
- `KnowledgeArtifact`
- `iasem`-Quiz-YAML als Importformat
- Ontology-Import

Aus denselben Wissensbausteinen können Lernartefakte erzeugt werden:

- `generated_quiz_module`
- `flashcard_set`
- `summary_note`
- `glossary`
- `study_guide`

Zusätzlich gibt es:

- eine Streamlit-Oberfläche für Source-/Record-/Artifact-Inspektion
- Graph-Visualisierung
- eine FastAPI unter `/api/knowledge/...`

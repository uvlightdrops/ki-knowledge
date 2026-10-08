# Source Workspace and Workflow Concept

**Leading document for the Data Sources UI and source-intake workflow.**
Related documents describe implementation details; this document defines the
shared functionality and intended interaction model.

## One functionality, multiple views

Data Sources brings files in their domain and directory hierarchy into a
controlled workflow. Markdown, PDF, ontology, tables, images, and Jira inputs
are formats or connectors, not separate intake applications.

The primary UI is **one domain source table** at `/data-sources/sources/`.
Discovery runs when the page opens; importing remains an explicit next step.
The table combines discovered files and registered sources without duplicating
the same file. Directory hierarchy is context, not a reason to create another
widget or another source record.

The intended table supports:

- domain-relative path and directory/subtree navigation;
- format, workflow status, and text/path filters;
- title, path, modification time, and status sorting;
- title, format, origin, status, and processing results in each row;
- per-file and selected-file actions appropriate to their workflow state.

Shortcuts such as **PDFs**, **new files**, **failed imports**, **Markdown**,
and **ontologies** should open reduced views of the same inventory. They must
reuse its filters and workflow actions, not maintain independent file lists.
Summary widgets may show counts and links; they should not duplicate the table.

The workspace is a preparation/detail view for selected sources. The job queue
is a processing monitor. Neither is a competing inventory. Upload adds files
to intake; whether an upload starts import must be explicit in the UI.

### Implementation status and remaining consolidation

Implementiert: sofortige Discovery der aktiven Domain, zusammengeführte Datei-/Store-Zeilen,
Filter nach Format, Workflow-Status, Herkunftsordner, Pfadpräfix und Freitext, Sortierung nach
Titel, Pfad, Stand, Status, Einträgen und Typ, Pagination sowie Einzel- und Mehrfachimport
im Haupt-Widget. Die Kurzfilter **Alle**, **Neu**, **Fehlgeschlagen**, **PDFs**,
**Markdown** und **Ontologien** sind Presets derselben Tabelle. Registrierte Quellen behalten
Record-, Artefakt-, Reimport- und Löschaktionen. Das frühere Filter-Widget ist in der Liste
aufgegangen; „Neu im Eingang“ ist nur noch eine kompakte Zusammenfassung mit Links und
Sammelimport.

Noch offen: Workspace-/Detail-Flows für vorbereitende Bearbeitung, feinere Job- und Review-
Statusdimensionen sowie die fachliche Prüfung weiterer historischer Markdown-, PDF- und
Formatübersichten gegen diese zentrale Inventar-Sicht.

Discovery status, import-job status, semantic processing, and editorial review
are distinct dimensions. An imported file is not automatically semantically
understood, reviewed, or published. The UI must not imply otherwise.

## Related documentation

- [System overview](SYSTEM_OVERVIEW.md): system boundaries and integration.
- [PDF import](pdf_batch_import.md): PDF inventory, extraction and job handling.
- [Knowledge blocks](knowledge_blocks.md): downstream records and artifacts.
- [Import and AI refinement](IMPORT_AI_REFINEMENT.md): project-specific
  InfoSite operations, not an alternative general source inventory.
- [InfoSite architecture](INFOSITE_ARCHITECTURE.md): presentation pipeline and
  historical architecture plan.
- [Content model matrix](content-model-matrix.md): source, record, output and
  editorial ownership.
- [Widget preview audit](../docs/widget-catalog-preview-audit.md): rendering
  inventory, subordinate to the interaction model defined here.

## Purpose

The Data Sources area is the intake and preparation layer for raw inputs. It covers discovery, validation, preparation, and registration before a source is imported or handed over to another workflow.

## Core idea

- A source is first **captured**.
- Then it is **checked**.
- If preparation is required, it enters the **workspace**.
- When preparation is complete or unnecessary, it is marked as **prepared**.
- Import is then triggered **explicitly**; any later automation must be
  configured separately and must not run merely because a list is opened.

## Workspace meaning

The workspace is the pre-import work area. It is not the whole Data Sources section.
It is the place where a source can be reviewed, transformed, normalized, or staged before import.

This applies to:

- Markdown sources
- PDF sources
- and, where relevant, other source types such as OWL or Jira-backed inputs

## Workflow separation

### Data Sources workflow

The Data Sources workflow handles raw source intake:

1. discover source
2. validate source
3. prepare source if needed
4. mark source as prepared
5. start import
6. track job status

### Wagtail workflows

Wagtail is not a mix of source intake and output publishing.
There are two separate editorial workflows:

- **Input-side workflow** for source documents and source-related editorial handling
- **Output-side workflow** for generated documents and publication review

These workflows are conceptually related, but they remain separate.
Both model a status-driven lifecycle around preparation, review, and publication.

## Relationship to generated output

Generated output documents follow the same general idea: content passes through workflow states before it becomes visible or publishable.

That means the same mental model can be reused:

- intake
- prepare
- review
- publish

But the source side and the output side must not be collapsed into one mixed bucket.

## GUI implication

The GUI should reflect the workflow order:

1. capture and inspect
2. prepare in workspace
3. register as prepared
4. trigger import
5. monitor jobs

This should make the Data Sources page feel like a staging area, not just a file browser.

### Domain source inventory

`/data-sources/sources/` scans the active domain's configured source folders on
every GET. The main list merges files from `md/`, `pdf/`, `owl/`, `mix/`, and
`jira/` with registered store sources; filtering, counts, and pagination include
unimported files. Resolved and configured symlink paths identify the same file.
Folder names do not limit formats: a PDF in `md/` is still listed as a PDF.

Discovery only reads directory entries, file metadata, and an existing PDF queue
in read-only mode. It does not import, queue jobs, run OCR, or call an LLM.
Files show **new**, **queued**, **failed**, or **unsupported** status; store sources
show **imported**. Import is a separate POST action. Only imported sources link to
records and offer generation, reimport, and deletion. Failed jobs show their error
and can be retried; queued files cannot be imported again from the list.

Jira CSV files use the separate Jira workflow, never the mixed table importer or
bulk import. Unsupported files remain visible with import disabled. The bulk
import widget includes supported, unregistered non-Jira files and preserves the
existing exclusion of completed PDF jobs without a matching source; those files
remain visible in the main inventory. Hidden files and temporary Office files are
excluded by the shared filesystem discovery helper.

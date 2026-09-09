# Source Workspace and Workflow Concept

## Purpose

The Data Sources area is the intake and preparation layer for raw inputs. It covers discovery, validation, preparation, and registration before a source is imported or handed over to another workflow.

## Core idea

- A source is first **captured**.
- Then it is **checked**.
- If preparation is required, it enters the **workspace**.
- When preparation is complete or unnecessary, it is marked as **prepared**.
- Import is then triggered **automatically or manually**.

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


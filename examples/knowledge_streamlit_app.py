"""Streamlit UI for browsing the shared knowledge core."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import requests
import networkx as nx
import streamlit as st
import streamlit.components.v1 as components

from ki_knowledge.knowledge.ontology_ingest import parse_ontology_text, select_high_quality_concepts
from ki_knowledge.integrations.markdown_blocks import MarkdownBlockParser
from ki_knowledge.ui.knowledge_api_client import (
    KnowledgeAPIClient,
    artifact_title,
    default_markdown_directory,
    discover_ontology_files,
    default_knowledge_api_url,
    discover_markdown_files,
    short_text,
)
from ki_knowledge.ui.knowledge_graph_viz import (
    create_pyvis_network,
    graph_dict_to_networkx,
    graph_statistics,
    ontology_concepts_to_networkx,
)
from ki_knowledge.ui.knowledge_workspace import (
    MarkdownTreeNode,
    WorkspaceState,
    add_snapshot,
    build_markdown_tree,
    diff_snapshot,
    file_digest,
    is_favorite_file,
    load_workspace_state,
    mark_recent_file,
    restore_snapshot,
    save_workspace_state,
    set_favorite_file,
    snapshots_for_file,
)


BLOCK_TYPE_OPTIONS = ["heading", "paragraph", "list_item", "code_block"]
ARTIFACT_TYPE_OPTIONS = [
    "generated_quiz_module",
    "flashcard_set",
    "summary_note",
    "glossary",
    "study_guide",
]
SECTION_OPTIONS = ["Markdown", "Ontologies", "Editor", "Export"]


def _set_selected_markdown(file_path: str, markdown_directory: str, state: WorkspaceState) -> None:
    st.session_state["selected_markdown_path"] = file_path
    mark_recent_file(state, file_path)
    save_workspace_state(markdown_directory, state)


def _set_selected_markdown_directory(directory_path: str, markdown_directory: str) -> None:
    st.session_state["selected_markdown_directory"] = directory_path
    st.session_state["selected_markdown_path"] = ""


def _selected_markdown_directory() -> Path | None:
    directory_path = st.session_state.get("selected_markdown_directory")
    if not directory_path:
        return None
    directory = Path(directory_path)
    if directory.exists() and directory.is_dir():
        return directory
    return None


def _relative_label(path: str | Path, root: str | Path) -> str:
    try:
        relative = Path(path).resolve().relative_to(Path(root).resolve())
    except (OSError, RuntimeError, ValueError):
        return str(path)
    return "." if not relative.parts else relative.as_posix()


def _markdown_directory_options(markdown_directory: str, query: str = "") -> list[str]:
    root = Path(markdown_directory)
    directories = {str(root)}
    for file_path in discover_markdown_files(root):
        rel_path = _relative_label(file_path, root).lower()
        if query.strip() and query.lower() not in rel_path:
            continue
        directories.add(str(file_path.parent))
    return sorted(directories, key=lambda item: _relative_label(item, root))


def _filtered_markdown_files(directory: str | Path, query: str = "") -> list[Path]:
    files = discover_markdown_files(directory)
    if not query.strip():
        return files
    query_value = query.lower()
    return [
        file_path
        for file_path in files
        if query_value in file_path.name.lower() or query_value in str(file_path).lower()
    ]


def _render_markdown_tree(node: MarkdownTreeNode, *, markdown_directory: str, state: WorkspaceState) -> None:
    current_selected = st.session_state.get("selected_markdown_path")
    current_directory = st.session_state.get("selected_markdown_directory")
    directory_label = f"Ordner wählen ({len(node.iter_files())} Dateien)"
    if st.sidebar.button(directory_label, key=f"select-dir:{node.path}", width="stretch"):
        _set_selected_markdown_directory(str(node.path), markdown_directory)
        st.rerun()
    if current_directory == str(node.path):
        st.sidebar.caption("Aktueller Ordner")
    for child in node.iter_children():
        with st.sidebar.expander(child.name, expanded=False):
            _render_markdown_tree(child, markdown_directory=markdown_directory, state=state)

    for file_path in node.files:
        rel_path = os.path.relpath(file_path, markdown_directory)
        label = f"★ {rel_path}" if is_favorite_file(state, file_path) else rel_path
        if current_selected == str(file_path):
            label = f"▶ {label}"
        if st.sidebar.button(label, key=f"select-markdown:{file_path}", width="stretch"):
            _set_selected_markdown(str(file_path), markdown_directory, state)
            st.rerun()


def _render_sidebar(*, markdown_directory: str, workspace_state: WorkspaceState) -> None:
    st.sidebar.title("Knowledge workspace")
    st.sidebar.caption("Lokale Auswahl und globale Filter.")
    st.sidebar.markdown("[Knowledge API browser](/knowledge-api/)")
    st.sidebar.caption(f"Workspace root: `{markdown_directory}`")

    tree_query = st.sidebar.text_input("Markdown-Suche", value=st.session_state.get("markdown_query", ""))
    st.session_state["markdown_query"] = tree_query
    directory_options = _markdown_directory_options(markdown_directory, tree_query)
    current_directory = st.session_state.get("selected_markdown_directory") or markdown_directory
    if current_directory not in directory_options and directory_options:
        current_directory = directory_options[0]
    selected_directory = st.sidebar.selectbox(
        "Ordner",
        options=directory_options,
        index=directory_options.index(current_directory) if directory_options else None,
        format_func=lambda item: _relative_label(item, markdown_directory),
    )
    if selected_directory and selected_directory != st.session_state.get("selected_markdown_directory"):
        _set_selected_markdown_directory(selected_directory, markdown_directory)

    selected_directory_path = _selected_markdown_directory() or Path(markdown_directory)
    markdown_files = _filtered_markdown_files(selected_directory_path, tree_query)
    if markdown_files:
        current_markdown = st.session_state.get("selected_markdown_path", "")
        if current_markdown not in {str(item) for item in markdown_files}:
            current_markdown = str(markdown_files[0])
        selected_markdown = st.sidebar.selectbox(
            "Markdown-Datei",
            options=[str(item) for item in markdown_files],
            index=[str(item) for item in markdown_files].index(current_markdown),
            format_func=lambda item: _relative_label(item, selected_directory_path),
        )
        if selected_markdown != st.session_state.get("selected_markdown_path"):
            _set_selected_markdown(selected_markdown, markdown_directory, workspace_state)
    else:
        st.sidebar.caption("Keine Markdown-Dateien im gewählten Ordner.")

    ontology_files = discover_ontology_files(markdown_directory)
    if ontology_files:
        current_ontology = st.session_state.get("selected_ontology_path", "")
        ontology_options = [str(item) for item in ontology_files]
        if current_ontology not in ontology_options:
            current_ontology = ontology_options[0]
        selected_ontology = st.sidebar.selectbox(
            "Ontology-Datei",
            options=ontology_options,
            index=ontology_options.index(current_ontology),
            format_func=lambda item: _relative_label(item, markdown_directory),
        )
        if selected_ontology != st.session_state.get("selected_ontology_path"):
            _set_selected_ontology(selected_ontology)
    else:
        st.sidebar.caption("Keine OWL/RDF/Turtle-Dateien gefunden.")

    recent_files = [file_path for file_path in workspace_state.recent_files if Path(file_path).exists()]
    if recent_files:
        with st.sidebar.expander("Zuletzt geöffnet", expanded=False):
            recent_selected = st.selectbox(
                "Recent",
                options=["", *recent_files[:8]],
                format_func=lambda item: "Bitte wählen" if not item else _relative_label(item, markdown_directory),
                label_visibility="collapsed",
                key="recent_markdown_select",
            )
            if recent_selected and recent_selected != st.session_state.get("selected_markdown_path"):
                _set_selected_markdown(recent_selected, markdown_directory, workspace_state)

    favorite_files = [file_path for file_path in workspace_state.favorite_files if Path(file_path).exists()]
    if favorite_files:
        with st.sidebar.expander("Favoriten", expanded=False):
            favorite_selected = st.selectbox(
                "Favorites",
                options=["", *favorite_files[:8]],
                format_func=lambda item: "Bitte wählen" if not item else _relative_label(item, markdown_directory),
                label_visibility="collapsed",
                key="favorite_markdown_select",
            )
            if favorite_selected and favorite_selected != st.session_state.get("selected_markdown_path"):
                _set_selected_markdown(favorite_selected, markdown_directory, workspace_state)


def _render_header_navigation(markdown_directory: str) -> str:
    selected_markdown = _selected_markdown_file()
    selected_ontology = _selected_ontology_file()
    with st.container(border=True):
        st.caption("Arbeitsbereich")
        section = st.segmented_control(
            "Bereich",
            options=SECTION_OPTIONS,
            default=st.session_state.get("workspace_section", "Markdown"),
            key="workspace_section",
        )
        meta_col1, meta_col2 = st.columns(2)
        with meta_col1:
            st.caption(
                f"Markdown: `{_relative_label(selected_markdown, markdown_directory)}`"
                if selected_markdown
                else "Markdown: nicht ausgewählt"
            )
        with meta_col2:
            st.caption(
                f"Ontology: `{_relative_label(selected_ontology, markdown_directory)}`"
                if selected_ontology
                else "Ontology: nicht ausgewählt"
            )
    return section or "Markdown"


def _selected_markdown_file() -> Path | None:
    preview_path = st.session_state.get("selected_markdown_path")
    if not preview_path:
        return
    preview_file = Path(preview_path)
    if preview_file.exists():
        return preview_file
    return None


def _set_selected_ontology(file_path: str) -> None:
    st.session_state["selected_ontology_path"] = file_path


def _selected_ontology_file() -> Path | None:
    preview_path = st.session_state.get("selected_ontology_path")
    if not preview_path:
        return None
    preview_file = Path(preview_path)
    if preview_file.exists():
        return preview_file
    return None


def _render_markdown_explorer(
    client: KnowledgeAPIClient,
    *,
    markdown_directory: str,
    workspace_state: WorkspaceState,
) -> None:
    selected_file = _selected_markdown_file()
    st.markdown("### Markdown-Explorer")
    if selected_file is None:
        st.info("Wähle links eine Markdown-Datei aus.")
        return

    try:
        content = selected_file.read_text(encoding="utf-8")
    except OSError as exc:
        st.warning(f"Markdown-Vorschau nicht lesbar: {exc}")
        return

    parser = MarkdownBlockParser()
    blocks = parser.parse_markdown(content, source_path=str(selected_file.resolve()))
    latest_snapshot = snapshots_for_file(workspace_state, str(selected_file))
    current_digest = file_digest(content)
    st.caption(f"Quelle: `{selected_file}`")
    if latest_snapshot:
        if latest_snapshot[0].get("digest") == current_digest:
            st.success("Datei entspricht der letzten gespeicherten Version.")
        else:
            st.warning("Datei hat Änderungen gegenüber der letzten gespeicherten Version.")

    col1, col2, col3 = st.columns([1.2, 1, 1])
    with col1:
        if st.button("Vorschau merken", width="stretch"):
            mark_recent_file(workspace_state, str(selected_file))
            save_workspace_state(markdown_directory, workspace_state)
            st.success("Als zuletzt geöffnet gespeichert.")
    with col2:
        favorite = is_favorite_file(workspace_state, selected_file)
        if st.button("★" if not favorite else "☆", width="stretch"):
            set_favorite_file(workspace_state, str(selected_file), not favorite)
            save_workspace_state(markdown_directory, workspace_state)
            st.rerun()
    with col3:
        if st.button("Als Preview setzen", width="stretch"):
            st.session_state["markdown_preview_path"] = str(selected_file)

    preview_col, import_col, refresh_col = st.columns([1.4, 1, 1])
    with preview_col:
        with st.expander("Markdown-Vorschau", expanded=False):
            st.code(content, language="markdown")
    with import_col:
        block_type_choices = st.multiselect(
            "Blocktypen importieren",
            options=BLOCK_TYPE_OPTIONS,
            default=BLOCK_TYPE_OPTIONS,
        )
        st.caption(f"{len(blocks)} extrahierte Bausteine")
        if st.button("Importieren", width="stretch"):
            imported = client.import_source(
                path=str(selected_file),
                import_format="markdown",
                source_name=selected_file.name,
                block_types=block_type_choices,
                rebuild_graph=True,
            )
            st.session_state["last_import_result"] = imported
            mark_recent_file(workspace_state, str(selected_file))
            save_workspace_state(markdown_directory, workspace_state)
            st.rerun()
    with refresh_col:
        if st.button("Neu laden", width="stretch"):
            st.rerun()

    block_counter = Counter(block.block_type for block in blocks)
    summary_cols = st.columns(4)
    summary_cols[0].metric("Bausteine", len(blocks))
    summary_cols[1].metric("Überschriften", block_counter.get("heading", 0))
    summary_cols[2].metric("Absätze", block_counter.get("paragraph", 0))
    summary_cols[3].metric("Listenpunkte", block_counter.get("list_item", 0))

    outline: dict[str, list[str]] = {}
    for block in blocks:
        key = block.heading_path.split(" / ")[0] if block.heading_path else "(root)"
        outline.setdefault(key, []).append(block.block_type)
    with st.expander("Struktur-Überblick", expanded=False):
        for heading, items in sorted(outline.items()):
            st.caption(f"{heading} — {len(items)} Bausteine")
            st.write(", ".join(items[:10]))

    st.markdown("#### Extrahierte Blöcke")
    if blocks:
        block_filter = st.multiselect(
            "Blocktypen filtern",
            options=BLOCK_TYPE_OPTIONS,
            default=BLOCK_TYPE_OPTIONS,
        )
        filtered_blocks = [block for block in blocks if block.block_type in block_filter]
        for block in filtered_blocks:
            with st.expander(f"{block.block_type}: {short_text(block.heading_path or block.content, 80)}", expanded=False):
                st.caption(block.heading_path or "(ohne Überschrift)")
                st.write(block.content)
                st.code(block.id)
    else:
        st.caption("Keine extrahierten Blöcke.")


def _render_markdown_directory_overview(
    client: KnowledgeAPIClient,
    *,
    markdown_directory: str,
    workspace_state: WorkspaceState,
) -> None:
    selected_directory = _selected_markdown_directory()
    if selected_directory is None:
        return

    files = discover_markdown_files(selected_directory)
    st.markdown("### Ordner-Übersicht")
    st.caption(str(selected_directory))
    st.metric("Markdown-Dateien", len(files))
    if not files:
        st.info("In diesem Ordner liegen keine Markdown-Dateien.")
        return

    if st.button("Alle Markdown-Dateien importieren", width="stretch"):
        imported_ids: list[str] = []
        for file_path in files:
            imported = client.import_source(
                path=str(file_path),
                import_format="markdown",
                source_name=file_path.relative_to(selected_directory).as_posix(),
                block_types=BLOCK_TYPE_OPTIONS,
                rebuild_graph=True,
            )
            imported_ids.append(imported.get("source_id", f"markdown:{file_path.resolve()}"))
        st.session_state["last_import_result"] = {"imported": len(files), "source_ids": imported_ids}
        st.session_state["selected_markdown_path"] = str(files[0])
        mark_recent_file(workspace_state, str(files[0]))
        save_workspace_state(markdown_directory, workspace_state)
        st.success(f"{len(files)} Dateien importiert.")
        st.rerun()

    with st.expander("Dateien im Ordner", expanded=True):
        for file_path in files:
            rel_path = file_path.relative_to(selected_directory)
            st.write(str(rel_path))


def _render_ontology_tab(client: KnowledgeAPIClient, *, workspace_root: str) -> None:
    ontology_files = discover_ontology_files(workspace_root)
    st.markdown("### Ontology-Explorer")
    if not ontology_files:
        st.info("Keine OWL/RDF/Turtle-Dateien im Workspace gefunden.")
        return

    selected_file = _selected_ontology_file()
    if selected_file is None:
        selected_file = ontology_files[0]
        _set_selected_ontology(str(selected_file))

    try:
        content = selected_file.read_text(encoding="utf-8")
        document = parse_ontology_text(
            content,
            source_url=str(selected_file),
            title=selected_file.stem.replace("_", " ").title(),
        )
    except Exception as exc:
        st.error(f"Ontologie konnte nicht gelesen werden: {exc}")
        return

    if not document.concepts:
        st.warning("Die Ontologie wurde gelesen, aber es konnten keine Konzepte extrahiert werden.")
        return

    max_default = min(60, max(10, len(document.concepts)))
    top_n = st.slider(
        "Max. Konzepte für Vorschau",
        min_value=10,
        max_value=max(10, min(len(document.concepts), 300)),
        value=max_default,
        step=5,
    )
    selected_concepts = select_high_quality_concepts(document.concepts, top_n=top_n)
    concept_query = st.text_input("Concept-Suche", value=st.session_state.get("ontology_query", ""))
    st.session_state["ontology_query"] = concept_query
    visible_concepts = [
        concept
        for concept in selected_concepts
        if not concept_query.strip()
        or concept_query.lower() in concept.label.lower()
        or concept_query.lower() in concept.definition.lower()
        or concept_query.lower() in concept.concept_id.lower()
    ]

    relation_count = sum(
        1
        for concept in visible_concepts
        for relation in concept.relations
        if relation.partition("->")[2].strip() in {item.concept_id for item in visible_concepts}
    )
    metric_cols = st.columns(4)
    metric_cols[0].metric("Datei", selected_file.name)
    metric_cols[1].metric("Format", document.source_format)
    metric_cols[2].metric("Konzepte", len(visible_concepts))
    metric_cols[3].metric("Relationen", relation_count)
    st.caption(f"Quelle: `{selected_file}`")

    action_col1, action_col2 = st.columns([1, 1])
    with action_col1:
        if st.button("Als Ontology-Source importieren", width="stretch"):
            try:
                imported = client.import_source(
                    path=str(selected_file),
                    import_format="ontology",
                    source_name=selected_file.stem.replace("_", " ").title(),
                    rebuild_graph=True,
                )
                st.session_state["last_ontology_import_result"] = imported
                st.success(f"Ontologie importiert: {imported.get('imported', 0)} Records")
                st.rerun()
            except requests.RequestException as exc:
                st.error(f"Import fehlgeschlagen: {exc}")
    with action_col2:
        with st.expander("Ontologie-Metadaten", expanded=False):
            st.json(
                {
                    "title": document.title,
                    "source_url": document.source_url,
                    "source_format": document.source_format,
                    "concepts_parsed": len(document.concepts),
                }
            )

    if visible_concepts:
        graph = ontology_concepts_to_networkx(visible_concepts)
        stats = graph_statistics(graph)
        left, right = st.columns([3, 1])
        with left:
            network = create_pyvis_network(graph, physics_enabled=True)
            components.html(network.generate_html(), height=720, scrolling=True)
        with right:
            st.markdown("**Graph-Statistik**")
            st.metric("Knoten", stats["total_nodes"])
            st.metric("Kanten", stats["total_edges"])
            st.metric("Dichte", f"{stats['density']:.3f}")
            with st.expander("Relationen", expanded=False):
                st.json(stats["edge_predicates"])

        with st.expander("Konzeptliste", expanded=False):
            st.dataframe(
                [
                    {
                        "label": concept.label,
                        "concept_id": concept.concept_id,
                        "quality_score": concept.quality_score,
                        "relations": len(concept.relations),
                    }
                    for concept in visible_concepts
                ],
                width="stretch",
            )

    last_import = st.session_state.get("last_ontology_import_result") or {}
    source_id = str(last_import.get("source_id", "")).strip()
    if source_id:
        st.markdown("### Importierte Source")
        st.caption(source_id)
        detail_tabs = st.tabs(["Records", "Graph", "Artifacts"])
        with detail_tabs[0]:
            _render_records_tab(client, source_id)
        with detail_tabs[1]:
            _render_graph_tab(client, source_id)
        with detail_tabs[2]:
            _render_artifacts_tab(client, source_id)


def _render_generation_actions(client: KnowledgeAPIClient, source_id: str) -> None:
    st.markdown("### Artefakte generieren")
    col1, col2, col3 = st.columns([2, 1, 1])
    artifact_type = col1.selectbox("Artefakt-Typ", options=ARTIFACT_TYPE_OPTIONS, index=0)
    max_items = col2.number_input("Max. Items", min_value=1, max_value=20, value=6, step=1)
    generate_clicked = col3.button("Generieren", width="stretch")
    batch_clicked = st.button("Lernpaket generieren", width="stretch")

    try:
        if generate_clicked:
            artifact = client.generate_artifact(
                source_id=source_id,
                artifact_type=artifact_type,
                max_items=int(max_items),
            )
            st.success(f"Erzeugt: {artifact['artifact_id']}")
        if batch_clicked:
            created: list[str] = []
            for item_type in ["summary_note", "glossary", "study_guide"]:
                artifact = client.generate_artifact(
                    source_id=source_id,
                    artifact_type=item_type,
                    max_items=int(max_items),
                )
                created.append(artifact["artifact_id"])
            st.success(", ".join(created))
    except requests.RequestException as exc:
        st.error(f"Generierung fehlgeschlagen: {exc}")


def _render_records_tab(client: KnowledgeAPIClient, source_id: str) -> None:
    records = client.list_records(source_id=source_id, limit=200)
    st.caption(f"{len(records)} Records")
    if not records:
        st.info("Keine Records für diese Source.")
        return

    selected_id = st.selectbox(
        "Record wählen",
        options=[record["block_id"] for record in records],
        format_func=lambda block_id: next(
            f"{record['block_type']} — {short_text(record['title'] or record['content'], 80)}"
            for record in records
            if record["block_id"] == block_id
        ),
    )
    record = next(record for record in records if record["block_id"] == selected_id)
    st.markdown(f"**Typ:** `{record['block_type']}`")
    st.markdown(f"**Pfad:** `{record['path']}`")
    st.write(record["content"])
    if record.get("metadata"):
        with st.expander("Record-Metadaten", expanded=False):
            st.json(record["metadata"])

    neighbors = client.list_neighbors(selected_id, limit=20)
    with st.expander("Nachbarn / Relationen", expanded=False):
        if neighbors:
            st.dataframe(neighbors)
        else:
            st.caption("Keine Nachbarn gefunden.")

    query = " ".join(token for token in [record.get("title", ""), record.get("content", "")[:120]] if token).strip()
    if query:
        st.markdown("#### Link-Vorschläge")
        suggestions = [
            item
            for item in client.search_blocks(query, limit=8)
            if item.get("block_id") != selected_id and item.get("source_id") == source_id
        ]
        if suggestions:
            target_options = {f"{item['block_type']} — {short_text(item['content'], 90)}": item["block_id"] for item in suggestions}
            relation_col, target_col = st.columns([1, 2])
            with relation_col:
                relation_type = st.selectbox(
                    "Relation",
                    options=["related_to", "same_as", "supports", "follows_up", "contradicts"],
                )
            with target_col:
                target_label = st.selectbox("Ziel", options=list(target_options.keys()))
            action_col1, action_col2 = st.columns(2)
            if action_col1.button("Relation anlegen", width="stretch"):
                client.add_relation(
                    source_block_id=selected_id,
                    target_block_id=target_options[target_label],
                    relation=relation_type,
                    metadata={"created_by": "streamlit_phase_f"},
                )
                st.success("Relation gespeichert.")
            if action_col2.button("Alle Vorschläge verlinken", width="stretch"):
                for block_id in target_options.values():
                    if block_id == selected_id:
                        continue
                    client.add_relation(
                        source_block_id=selected_id,
                        target_block_id=block_id,
                        relation=relation_type,
                        metadata={"created_by": "streamlit_phase_f_bulk"},
                    )
                st.success("Vorschläge verknüpft.")
        else:
            st.caption("Keine passenden Vorschläge gefunden.")


def _render_artifacts_tab(client: KnowledgeAPIClient, source_id: str) -> None:
    artifacts = client.list_artifacts(source_id=source_id)
    st.caption(f"{len(artifacts)} Artefakte")
    if not artifacts:
        st.info("Noch keine Artefakte erzeugt.")
        return

    selected_id = st.selectbox(
        "Artifact wählen",
        options=[artifact["artifact_id"] for artifact in artifacts],
        format_func=lambda artifact_id: next(
            artifact_title(artifact) for artifact in artifacts if artifact["artifact_id"] == artifact_id
        ),
    )
    artifact = next(artifact for artifact in artifacts if artifact["artifact_id"] == selected_id)
    payload = client.artifact_payload(artifact)

    st.markdown(f"**Typ:** `{artifact['artifact_type']}`")
    if artifact.get("metadata"):
        st.json(artifact["metadata"])

    if artifact["artifact_type"] in {"quiz_module", "generated_quiz_module"}:
        for idx, question in enumerate(payload.get("questions", []), start=1):
            with st.expander(f"Frage {idx}: {short_text(question.get('question', ''), 90)}", expanded=False):
                st.write(question.get("question", ""))
                options = question.get("options", [])
                for option in options:
                    marker = "✅" if option.get("option_id") == question.get("correct_option_id") or option.get("id") == question.get("correct_option_id") else "•"
                    label = option.get("text") or option.get("option_text") or ""
                    option_id = option.get("option_id") or option.get("id") or ""
                    st.write(f"{marker} {option_id}: {label}")
                if question.get("explanation"):
                    st.info(question["explanation"])
    elif artifact["artifact_type"] == "flashcard_set":
        for card in payload.get("cards", []):
            with st.expander(card.get("front", "Karte"), expanded=False):
                st.write(card.get("back", ""))
                st.caption(card.get("source_block_id", ""))
    elif artifact["artifact_type"] in {"summary_note", "glossary", "study_guide"}:
        for item in payload.get("sections", payload.get("terms", payload.get("items", []))):
            title = item.get("title") or item.get("term") or item.get("topic") or "Eintrag"
            with st.expander(title, expanded=False):
                st.write(item.get("summary") or item.get("definition") or item.get("focus") or "")
                if item.get("prompt"):
                    st.info(item["prompt"])
                if item.get("source_block_id"):
                    st.caption(item["source_block_id"])
    else:
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def _render_graph_tab(client: KnowledgeAPIClient, source_id: str) -> None:
    try:
        graph_payload = client.get_source_graph(source_id, limit=400)
    except requests.RequestException as exc:
        st.error(f"Graph konnte nicht geladen werden: {exc}")
        return

    if not graph_payload.get("nodes"):
        st.info("Für diese Source gibt es noch keinen Graphen.")
        return

    base_graph = graph_dict_to_networkx(graph_payload)
    node_map = {node["node_id"]: node for node in graph_payload["nodes"]}
    node_types = sorted({node.get("node_type", "unknown") for node in graph_payload["nodes"]})
    predicates = sorted({edge.get("predicate", "unknown") for edge in graph_payload["edges"]})
    graph_query = st.text_input("Graph-Suche", value=st.session_state.get("graph_query", ""))
    st.session_state["graph_query"] = graph_query

    col1, col2, col3 = st.columns([1.2, 1.2, 1])
    with col1:
        selected_node_types = st.multiselect("Knotentypen", options=node_types, default=node_types)
    with col2:
        selected_predicates = st.multiselect("Relationen", options=predicates, default=predicates)
    with col3:
        physics_enabled = st.checkbox("Physics", value=True)

    matched_nodes = {
        node["node_id"]
        for node in graph_payload["nodes"]
        if not graph_query.strip()
        or graph_query.lower() in node.get("label", "").lower()
        or graph_query.lower() in node.get("path", "").lower()
        or graph_query.lower() in json.dumps(node.get("metadata", {}), ensure_ascii=False).lower()
    }
    neighborhood_nodes = set(matched_nodes)
    if graph_query.strip():
        for edge in graph_payload["edges"]:
            if edge["source"] in matched_nodes or edge["target"] in matched_nodes:
                neighborhood_nodes.add(edge["source"])
                neighborhood_nodes.add(edge["target"])

    filtered_nodes = {
        node["node_id"]
        for node in graph_payload["nodes"]
        if (not selected_node_types or node.get("node_type", "unknown") in selected_node_types)
        and (not graph_query.strip() or node["node_id"] in neighborhood_nodes)
    }
    filtered_edges = [
        edge
        for edge in graph_payload["edges"]
        if (not selected_predicates or edge.get("predicate", "unknown") in selected_predicates)
        and edge["source"] in filtered_nodes
        and edge["target"] in filtered_nodes
    ]

    filtered_graph = nx.DiGraph()
    for node_id in filtered_nodes:
        node_id = str(node_id)
        node = node_map[node_id]
        filtered_graph.add_node(
            node_id,
            label=node.get("label", node_id),
            node_type=node.get("node_type", "unknown"),
            path=node.get("path", ""),
            metadata=node.get("metadata", {}),
        )
    for edge in filtered_edges:
        filtered_graph.add_edge(
            str(edge["source"]),
            str(edge["target"]),
            predicate=edge.get("predicate", ""),
            weight=edge.get("weight", 1.0),
            metadata=edge.get("metadata", {}),
        )

    stats = graph_statistics(filtered_graph)

    left, right = st.columns([3, 1])
    with left:
        network = create_pyvis_network(filtered_graph, physics_enabled=physics_enabled)
        components.html(network.generate_html(), height=720, scrolling=True)

    with right:
        st.markdown("**Graph-Statistik**")
        st.metric("Knoten", stats["total_nodes"])
        st.metric("Kanten", stats["total_edges"])
        st.metric("Dichte", f"{stats['density']:.3f}")
        if graph_query.strip():
            st.caption(f"Treffer: {len(matched_nodes)}")
        with st.expander("Knotentypen", expanded=True):
            st.json(stats["node_types"])
        with st.expander("Relationen", expanded=False):
            st.json(stats["edge_predicates"])

    st.markdown("### Fokus & Pfade")
    focus_col, path_col = st.columns(2)
    node_ids = list(node_map.keys())
    with focus_col:
        focus_node_id = st.selectbox(
            "Knoten inspizieren",
            options=node_ids,
            format_func=lambda node_id: f"{node_map[node_id]['node_type']} — {short_text(node_map[node_id]['label'], 70)}",
        )
    with path_col:
        source_node_id = st.selectbox(
            "Pfad von",
            options=node_ids,
            format_func=lambda node_id: short_text(node_map[node_id]["label"], 60),
            index=0,
            key="graph_path_source",
        )
    target_node_id = st.selectbox(
        "Pfad zu",
        options=node_ids,
        format_func=lambda node_id: short_text(node_map[node_id]["label"], 60),
        index=min(1, max(0, len(node_map) - 1)),
        key="graph_path_target",
    )
    if st.button("Kürzesten Pfad anzeigen", width="stretch"):
        try:
            path_nodes = nx.shortest_path(base_graph, source=source_node_id, target=target_node_id)
            st.success(" -> ".join(path_nodes))
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            st.warning("Kein Pfad gefunden.")

    selected_node = node_map[focus_node_id]
    st.markdown(f"**Knoten:** `{focus_node_id}`")
    st.write(selected_node.get("label", ""))
    st.caption(selected_node.get("path", ""))
    if selected_node.get("metadata"):
        with st.expander("Knoten-Metadaten", expanded=False):
            st.json(selected_node["metadata"])

    incident_edges = [
        edge
        for edge in graph_payload["edges"]
        if edge["source"] == focus_node_id or edge["target"] == focus_node_id
    ]
    with st.expander("Verbundene Kanten", expanded=False):
        if incident_edges:
            st.dataframe(incident_edges)
        else:
            st.caption("Keine Kanten für diesen Knoten.")


def _render_editor_tab(
    client: KnowledgeAPIClient,
    *,
    markdown_directory: str,
    workspace_state: WorkspaceState,
) -> None:
    selected_file = _selected_markdown_file()
    st.markdown("### Editor")
    if selected_file is None:
        st.info("Wähle links eine Markdown-Datei aus.")
        return

    try:
        content = selected_file.read_text(encoding="utf-8")
    except OSError as exc:
        st.error(f"Datei kann nicht gelesen werden: {exc}")
        return

    favorite = is_favorite_file(workspace_state, selected_file)
    top_col, fav_col = st.columns([3, 1])
    with top_col:
        st.caption(str(selected_file))
    with fav_col:
        if st.button("★" if not favorite else "☆", width="stretch", key=f"editor-fav:{selected_file}"):
            set_favorite_file(workspace_state, str(selected_file), not favorite)
            save_workspace_state(markdown_directory, workspace_state)
            st.rerun()

    edited_content = st.text_area(
        "Markdown bearbeiten",
        value=content,
        height=420,
        key=f"editor-content:{selected_file}",
    )
    save_col, import_col = st.columns(2)
    with save_col:
        if st.button("Speichern", width="stretch"):
            add_snapshot(workspace_state, str(selected_file), content, label="before-save")
            selected_file.write_text(edited_content, encoding="utf-8")
            add_snapshot(workspace_state, str(selected_file), edited_content, label="after-save")
            mark_recent_file(workspace_state, str(selected_file))
            save_workspace_state(markdown_directory, workspace_state)
            client.import_source(
                path=str(selected_file),
                import_format="markdown",
                source_name=selected_file.name,
                block_types=BLOCK_TYPE_OPTIONS,
                rebuild_graph=True,
            )
            st.success("Datei gespeichert und neu importiert.")
            st.rerun()
    with import_col:
        if st.button("Als Vorschau merken", width="stretch"):
            st.session_state["markdown_preview_path"] = str(selected_file)

    snapshots = snapshots_for_file(workspace_state, str(selected_file))
    if snapshots:
        st.markdown("#### Versionen")
        version_labels = [
            f"{idx + 1}. {snapshot.get('label', 'snapshot')} — {snapshot.get('timestamp', '')}"
            for idx, snapshot in enumerate(snapshots)
        ]
        selected_version_index = st.selectbox(
            "Version wählen",
            options=list(range(len(version_labels))),
            format_func=lambda idx: version_labels[idx],
            key=f"editor-version:{selected_file}",
        )
        restore_col, compare_col = st.columns(2)
        with restore_col:
            if st.button("Version wiederherstellen", width="stretch"):
                restored = restore_snapshot(workspace_state, str(selected_file), int(selected_version_index))
                if restored is not None:
                    selected_file.write_text(restored, encoding="utf-8")
                    add_snapshot(workspace_state, str(selected_file), restored, label="restore")
                    save_workspace_state(markdown_directory, workspace_state)
                    client.import_source(
                        path=str(selected_file),
                        import_format="markdown",
                        source_name=selected_file.name,
                        block_types=BLOCK_TYPE_OPTIONS,
                        rebuild_graph=True,
                    )
                    st.success("Version wiederhergestellt.")
                    st.rerun()
        with compare_col:
            st.caption(f"{len(snapshots)} gespeicherte Versionen")
            selected_diff = diff_snapshot(
                workspace_state,
                str(selected_file),
                int(selected_version_index),
                current_content=content,
            )
            if selected_diff:
                with st.expander("Diff zur aktuellen Datei", expanded=False):
                    st.code(selected_diff, language="diff")


def _render_export_tab(
    *,
    markdown_directory: str,
    workspace_state: WorkspaceState,
) -> None:
    selected_file = _selected_markdown_file()
    st.markdown("### Export & Historie")
    if selected_file is None:
        st.info("Wähle links eine Markdown-Datei aus.")
        return

    try:
        content = selected_file.read_text(encoding="utf-8")
    except OSError as exc:
        st.error(f"Datei kann nicht gelesen werden: {exc}")
        return

    parser = MarkdownBlockParser()
    blocks = parser.parse_markdown(content, source_path=str(selected_file.resolve()))
    export_bundle = {
        "source_file": str(selected_file),
        "block_count": len(blocks),
        "blocks": [block.to_dict() for block in blocks],
    }
    left, right = st.columns(2)
    with left:
        st.download_button(
            "Markdown exportieren",
            data=content,
            file_name=selected_file.name,
            mime="text/markdown",
            width="stretch",
        )
    with right:
        st.download_button(
            "JSON-Bundle exportieren",
            data=json.dumps(export_bundle, ensure_ascii=False, indent=2),
            file_name=f"{selected_file.stem}.json",
            mime="application/json",
            width="stretch",
        )

    st.markdown("#### Versionen")
    snapshots = snapshots_for_file(workspace_state, str(selected_file))
    if not snapshots:
        st.caption("Noch keine gespeicherten Versionen.")
        return

    for idx, snapshot in enumerate(snapshots, start=1):
        title = f"{idx}. {snapshot.get('label', 'snapshot')} — {snapshot.get('timestamp', '')}"
        with st.expander(title, expanded=False):
            st.code(snapshot.get("content", ""), language="markdown")


def main() -> None:
    st.set_page_config(page_title="Knowledge Explorer", layout="wide")
    st.title("Knowledge Explorer")

    client = KnowledgeAPIClient(default_knowledge_api_url())
    markdown_directory = default_markdown_directory()
    workspace_state = load_workspace_state(markdown_directory)
    if not st.session_state.get("selected_markdown_directory"):
        st.session_state["selected_markdown_directory"] = markdown_directory

    st.markdown("API browser und Health-Check sind jetzt in Django unter [/knowledge-api/](/knowledge-api/).")
    last_import_result = st.session_state.get("last_import_result")
    if last_import_result:
        imported_count = last_import_result.get("imported", last_import_result.get("blocks", 0))
        st.success(f"Import abgeschlossen: {imported_count}")

    _render_sidebar(markdown_directory=markdown_directory, workspace_state=workspace_state)

    section = _render_header_navigation(markdown_directory)
    if section == "Markdown":
        _render_markdown_directory_overview(
            client,
            markdown_directory=markdown_directory,
            workspace_state=workspace_state,
        )
        _render_markdown_explorer(client, markdown_directory=markdown_directory, workspace_state=workspace_state)
    elif section == "Ontologies":
        _render_ontology_tab(client, workspace_root=markdown_directory)
    elif section == "Editor":
        _render_editor_tab(client, markdown_directory=markdown_directory, workspace_state=workspace_state)
    else:
        _render_export_tab(markdown_directory=markdown_directory, workspace_state=workspace_state)


if __name__ == "__main__":
    main()

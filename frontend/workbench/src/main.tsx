import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { apiClient, ApiError } from "./api";
import { SourceEditor } from "./SourceEditor";
import { ConversationPanel } from "./ConversationPanel";
import { ProposalPanel } from "./ProposalPanel";
import type { Anchor, Annotation, Bootstrap, Document, DocumentSummary, ExcludedSource, Metadata, Relation, Revision, Source } from "./types";
import "./style.css";

const categories = [
  ["claim", "Aussage"], ["question", "Frage"], ["observation", "Beobachtung"],
  ["concept", "Begriff"], ["idea", "Idee"],
];
const relationKinds = [
  ["related_to", "bezieht sich auf"], ["supports", "stützt"],
  ["contradicts", "widerspricht"], ["derived_from", "abgeleitet aus"],
];
const emptyMetadata = (): Metadata => ({ title: "", category: "claim", tags: "", note: "" });

function Workbench({ config }: { config: Bootstrap }) {
  const api = useRef(apiClient(config)).current;
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [archivedDocuments, setArchivedDocuments] = useState<DocumentSummary[]>([]);
  const [archivedAnnotations, setArchivedAnnotations] = useState<Annotation[]>([]);
  const [sources, setSources] = useState<Source[]>([]);
  const [excludedSources, setExcludedSources] = useState<ExcludedSource[]>([]);
  const [targets, setTargets] = useState<Annotation[]>([]);
  const [relations, setRelations] = useState<Relation[]>([]);
  const [current, setCurrent] = useState<Document | null>(null);
  const [buffer, setBuffer] = useState("");
  const [history, setHistory] = useState<Revision[]>([]);
  const [conflict, setConflict] = useState<Document | null>(null);
  const [chatDirty, setChatDirty] = useState(false);
  const [proposalDirty, setProposalDirty] = useState(false);
  const [source, setSource] = useState("");
  const [noteTitle, setNoteTitle] = useState("");
  const [selection, setSelection] = useState<Anchor | null>(null);
  const [active, setActive] = useState<Annotation | null>(null);
  const [creating, setCreating] = useState<Anchor | null>(null);
  const [metadata, setMetadata] = useState<Metadata>(emptyMetadata);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [status, setStatus] = useState("");
  const [targetQuery, setTargetQuery] = useState("");
  const [target, setTarget] = useState("");
  const [kind, setKind] = useState("related_to");
  const [rationale, setRationale] = useState("");
  const [relationDirty, setRelationDirty] = useState(false);
  const [ready, setReady] = useState(false);
  const panel = useRef<HTMLElement>(null);
  const textDirty = Boolean(current && buffer !== current.revision.text);
  const hasUnsaved = dirty || relationDirty || textDirty || chatDirty || proposalDirty;
  const isHead = current?.revision.id === current?.head_revision_id;
  const [initialSource] = useState(new URLSearchParams(location.search).get("source_id") || "");

  useEffect(() => {
    const warn = (event: BeforeUnloadEvent) => {
      if (hasUnsaved) { event.preventDefault(); event.returnValue = ""; }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [hasUnsaved]);

  async function loadLists() {
    const [docs, allAnnotations, allRelations, archivedDocs, archivedMarks] = await Promise.all([
      api<{ documents: DocumentSummary[] }>("documents"),
      api<{ annotations: Annotation[] }>("annotations"),
      api<{ relations: Relation[] }>("relations"),
      api<{ documents: DocumentSummary[] }>("documents?archived=1"),
      api<{ annotations: Annotation[] }>("annotations?archived=1"),
    ]);
    setDocuments(docs.documents);
    setTargets(allAnnotations.annotations);
    setRelations(allRelations.relations);
    setArchivedDocuments(archivedDocs.documents);
    setArchivedAnnotations(archivedMarks.annotations);
  }
  function report(cause: unknown) {
    const message = cause instanceof Error ? cause.message : String(cause);
    setError(cause instanceof ApiError && cause.status === 412
      ? `${message} Deine Eingaben bleiben erhalten. Aktuellen Stand prüfen und vergleichen, bevor du erneut speicherst.`
      : message);
    setStatus("");
  }
  async function action(run: () => Promise<void>) {
    setBusy(true); setError(""); setStatus("");
    try { await run(); } catch (cause) { report(cause); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    void action(async () => {
      await loadLists();
      if (config.canCapture) {
        const result = await api<{ sources: Source[]; excluded: ExcludedSource[] }>("sources");
        setSources(result.sources);
        setExcludedSources(result.excluded);
        const canonical = result.excluded.find(item => item.id === initialSource)?.canonical_id;
        if (result.sources.some(item => item.id === initialSource)) setSource(initialSource);
        else if (canonical) setSource(canonical);
        else if (initialSource) setError("Die verlinkte Quelle ist in dieser Domain nicht mehr erfassbar. Bitte Quellenliste und Ausschlussgründe prüfen.");
      }
      setReady(true);
    });
  }, []);

  function mayLeave() {
    return !hasUnsaved || window.confirm("Ungespeicherte Texte, Metadaten, Relationen oder Nachrichten verlassen? Eingaben werden verworfen.");
  }
  function resetInspector() {
    setActive(null); setCreating(null); setSelection(null);
    setDirty(false); setRelationDirty(false); setMetadata(emptyMetadata());
    setTarget(""); setRationale("");
  }
  async function openDocument(id: string) {
    if (!mayLeave()) return;
    await action(async () => {
      const document = await api<Document>(`documents/${id}`);
      await displayDocument(document);
      setStatus("Gespeicherten Textstand geladen. Originaldatei bleibt unverändert.");
    });
  }
  async function displayDocument(document: Document) {
    const revisions = await api<{ revisions: Revision[] }>(`documents/${document.id}/revisions`);
    setCurrent(document); setBuffer(document.revision.text); setHistory(revisions.revisions);
    setConflict(null); setChatDirty(false); setProposalDirty(false); resetInspector();
  }
  async function openRevision(id: string) {
    if (!current || !mayLeave()) return;
    await action(async () => {
      await displayDocument(await api<Document>(`documents/${current.id}/revisions/${id}`));
      setStatus("Historischen Stand geladen; er wird nicht überschrieben.");
    });
  }
  async function createDraft() {
    if (!current || !mayLeave()) return;
    await action(async () => {
      await displayDocument(await api<Document>(`documents/${current.id}/drafts`, "POST", {}));
      await loadLists(); setStatus("Eigene Arbeitskopie angelegt. Die Quelle bleibt unverändert.");
    });
  }
  async function createNote(event: React.FormEvent) {
    event.preventDefault();
    if (!noteTitle.trim() || !mayLeave()) return;
    await action(async () => {
      await displayDocument(await api<Document>("drafts", "POST", { title: noteTitle.trim(), text: "" }));
      setNoteTitle(""); await loadLists(); setStatus("Eigene Notiz angelegt.");
    });
  }
  async function saveDraft() {
    if (!current) return;
    await action(async () => {
      try {
        const saved = await api<Document>(`documents/${current.id}/revisions`, "POST", {
          base_revision_id: current.revision.id, text: buffer,
        }, current.etag);
        await displayDocument(saved); await loadLists();
        setStatus("Neue Textrevision serverseitig gespeichert. Historische Markierungen bleiben erhalten.");
      } catch (cause) {
        if (cause instanceof ApiError && [409, 412].includes(cause.status)) {
          setConflict(await api<Document>(`documents/${current.id}`));
        }
        throw cause;
      }
    });
  }
  async function reanchor(annotation: Annotation) {
    if (!current || !selection || textDirty) return;
    await action(async () => {
      const updated = await api<Annotation>(`annotations/${annotation.id}/anchors`, "POST", {
        revision_id: current.revision.id, ...selection,
      }, annotation.etag);
      setCurrent(await api<Document>(`documents/${current.id}/revisions/${current.revision.id}`));
      setActive(updated); setCreating(null); setDirty(false);
      setMetadata({ title: updated.title, category: updated.category, tags: updated.tags.join(", "), note: updated.note });
      await loadLists(); setStatus("Neue Zuordnung ausdrücklich bestätigt. Historischer Anker bleibt erhalten.");
    });
  }
  function inspect(annotation: Annotation) {
    if (!mayLeave()) return;
    setActive(annotation); setCreating(null);
    setMetadata({ title: annotation.title, category: annotation.category, tags: annotation.tags.join(", "), note: annotation.note });
    setDirty(false); setRelationDirty(false); setTarget(""); setRationale("");
    panel.current?.focus();
  }
  function beginAnnotation() {
    if (!selection || !mayLeave()) return;
    setActive(null); setCreating(selection);
    setMetadata(emptyMetadata()); setDirty(true); setRelationDirty(false);
    panel.current?.focus();
  }
  async function saveMetadata(event: React.FormEvent) {
    event.preventDefault();
    if (!current || (!creating && !active)) return;
    await action(async () => {
      const data = { ...metadata, tags: metadata.tags.split(",").map(tag => tag.trim()).filter(Boolean) };
      const saved = active
        ? await api<Annotation>(`annotations/${active.id}`, "PATCH", data, active.etag)
        : await api<Annotation>(`documents/${current.id}/annotations`, "POST", {
          revision_id: current.revision.id, ...creating, ...data,
        });
      setCurrent(await api<Document>(`documents/${current.id}/revisions/${current.revision.id}`));
      setActive(saved); setCreating(null); setDirty(false);
      setMetadata({ title: saved.title, category: saved.category, tags: saved.tags.join(", "), note: saved.note });
      await loadLists();
      setStatus("Markierung und Metadaten serverseitig gespeichert.");
    });
  }
  async function capture(event: React.FormEvent) {
    event.preventDefault();
    if (!source || !mayLeave()) return;
    await action(async () => {
      const document = await api<Document>("documents", "POST", { source_id: source });
      await displayDocument(document); await loadLists();
      setStatus("Unveränderlichen Snapshot erfasst. Deine Quelldatei wurde nicht verändert.");
    });
  }
  async function saveRelation(event: React.FormEvent) {
    event.preventDefault();
    if (!active || !target) return;
    await action(async () => {
      await api<Relation>("relations", "POST", {
        source_id: active.id, target_id: target, type: kind, rationale,
      });
      setTarget(""); setRationale(""); setRelationDirty(false);
      await loadLists(); setStatus("Relation serverseitig gespeichert.");
    });
  }
  async function archive(item: DocumentSummary | Annotation, annotation: boolean, archived: boolean) {
    if (!mayLeave()) return;
    if (archived && !window.confirm(`„${item.title || "Ohne Titel"}“ archivieren? Verlauf und Verweise bleiben erhalten.`)) return;
    await action(async () => {
      await api(`${annotation ? "annotations" : "documents"}/${item.id}/archive`, "POST", { archived }, item.etag);
      if (!annotation && current?.id === item.id) {
        setCurrent(null); setBuffer(""); setHistory([]); setConflict(null);
        setChatDirty(false); setProposalDirty(false); resetInspector();
      } else if (annotation && current) {
        await displayDocument(await api<Document>(`documents/${current.id}/revisions/${current.revision.id}`));
      }
      await loadLists();
      setStatus(archived ? "Archiviert. Im Archiv wiederherstellbar." : "Wiederhergestellt.");
    });
  }
  const excludedGroups = new Map<string, ExcludedSource[]>();
  for (const item of excludedSources) {
    excludedGroups.set(item.reason, [...(excludedGroups.get(item.reason) || []), item]);
  }
  const relevantRelations = active ? relations.filter(relation =>
    relation.source_id === active.id || relation.target_id === active.id) : [];
  const availableTargets = targets.filter(item => item.id !== active?.id &&
    `${item.title} ${item.document_title}`.toLocaleLowerCase().includes(targetQuery.toLocaleLowerCase()));
  const targetItem = targets.find(item => item.id === target);

  return <div className="wb">
    {error && <div role="alert" className="wb-error">{error}</div>}
    {(busy || status || !ready) && <p role="status" aria-live="polite" className="wb-status">{busy ? "Anfrage läuft …" : status || "Lade Werkstatt …"}</p>}
    <div className="wb-layout" aria-busy={busy}>
      <aside className="wb-panel">
        <h2>Material</h2>
        {config.canCapture ? <form onSubmit={capture}>
          <label htmlFor="wb-source">Markdown-Quelle aus Data Sources</label>
          <select id="wb-source" value={source} onChange={event => setSource(event.target.value)} disabled={busy}>
            <option value="">Quelle wählen</option>
            {sources.map(item => <option key={item.id} value={item.id}>{item.title} · {item.folder}/{item.relative} · {item.registered ? "registriert" : "noch nicht importiert"}</option>)}
          </select>
          <button disabled={busy || !source}>Snapshot ausdrücklich erfassen</button>
          {ready && !sources.length && <p>Keine erfassbare Markdown-Datei im Data-Sources-Inventar dieser Domain vorhanden. Ein InfoSite-Projekt ist nicht erforderlich.</p>}
          {excludedSources.length > 0 && <details>
            <summary>Nicht erfassbare Quellen ({excludedSources.length})</summary>
            {[...excludedGroups].map(([reason, items]) => <div key={reason}>
              <p>{reason}</p><ul>{items.map(item => <li key={item.id}>{item.title}</li>)}</ul>
            </div>)}
          </details>}
        </form> : <p>Neue Quellsnapshots dürfen in E1 nur angemeldete Staff-Benutzer erfassen.</p>}
        <form onSubmit={createNote}>
          <label htmlFor="wb-new-note">Neue eigene Notiz</label>
          <input id="wb-new-note" value={noteTitle} maxLength={255} required disabled={busy}
            onChange={event => setNoteTitle(event.target.value)} />
          <button disabled={busy || !noteTitle.trim()}>Leere Notiz anlegen</button>
        </form>
        <h3>Meine Texte</h3>
        <ul className="wb-items">{documents.map(item =>
          <li key={item.id} className="wb-item-row">
            <button type="button" className="wb-remove" aria-label={`Text archivieren: ${item.title}`} title="Archivieren (wiederherstellbar)" disabled={busy}
              onClick={() => void archive(item, false, true)}>[x]</button>
            <button data-testid={`document-${item.id}`} className={current?.id === item.id ? "wb-selected" : ""} disabled={busy}
            onClick={() => void openDocument(item.id)}>{item.title}{item.kind === "draft" ? " · Arbeitskopie" : ""}</button></li>)}</ul>
        {ready && !documents.length && <p>Noch kein Snapshot gespeichert.</p>}
        <h3>Markierungen im Dokument</h3>
        <ul className="wb-items">{current?.annotations.map(item =>
          <li key={item.id} className="wb-item-row">
            <button type="button" className="wb-remove" aria-label={`Markierung archivieren: ${item.title}`} title="Archivieren (wiederherstellbar)" disabled={busy}
              onClick={() => void archive(item, true, true)}>[x]</button>
            <button disabled={busy} className={active?.id === item.id ? "wb-selected" : ""}
            onClick={() => inspect(item)}>{item.title || "Ohne Titel"}</button></li>)}</ul>
        <details className="wb-archive">
          <summary>Archiv ({archivedDocuments.length + archivedAnnotations.length})</summary>
          <p>Archivierte Texte enthalten weiterhin ihre Markierungen und ihren Verlauf. Quelldateien bleiben unverändert.</p>
          {archivedDocuments.map(item => <div key={item.id}>
            <button disabled={busy} onClick={() => void archive(item, false, false)}>Text wiederherstellen: {item.title}</button>
          </div>)}
          {archivedAnnotations.map(item => <div key={item.id}>
            <button disabled={busy} onClick={() => void archive(item, true, false)}>Markierung wiederherstellen: {item.title} · {item.document_title}</button>
          </div>)}
        </details>
        {Boolean(current?.historical_annotations.length) && <>
          <h3>Historische Markierungen</h3>
          <p>Auf diesem Textstand noch nicht zugeordnet. Neue Stelle wählen und bewusst zuordnen oder den historischen Stand öffnen.</p>
          {current!.historical_annotations.map(item => <div key={item.id} className="wb-historical">
            <strong>{item.title}</strong><blockquote>{item.exact}</blockquote>
            <button type="button" className="wb-remove" aria-label={`Markierung archivieren: ${item.title}`} title="Archivieren (wiederherstellbar)" disabled={busy}
              onClick={() => void archive(item, true, true)}>[x]</button>
            <button type="button" disabled={busy || hasUnsaved} onClick={() => void openRevision(item.revision_id)}>Ursprünglichen Stand öffnen</button>
            <button type="button" disabled={busy || !selection || hasUnsaved || !isHead}
              onClick={() => void reanchor(item)}>Dieser Auswahl zuordnen</button>
          </div>)}
        </>}
      </aside>
      <section className="wb-panel wb-text">
        <h2>{current?.title || "Dokument auswählen"}</h2>
        {current ? <>
          <p className="wb-muted">{current.kind === "draft" ? "Eigene Arbeitskopie" : "Unveränderlicher Markdown-Snapshot"} · Revision <code>{current.revision.id.slice(0, 8)}</code>
            {!isHead && " · historischer Stand, nur lesbar"}</p>
          <label htmlFor="wb-revision">Revision anzeigen</label>
          <select id="wb-revision" value={current.revision.id} disabled={busy} onChange={event => void openRevision(event.target.value)}>
            {history.map(item => <option key={item.id} value={item.id}>{item.id.slice(0, 8)} · {item.cause} · {item.created_at}</option>)}
          </select>
          <div className="wb-selection">
            {current.kind === "reference" && <button type="button" disabled={busy} onClick={() => void createDraft()}>Eigene Arbeitskopie anlegen</button>}
            {current.kind === "draft" && <button type="button" disabled={busy || !textDirty || !isHead || dirty || relationDirty || chatDirty || proposalDirty}
              onClick={() => void saveDraft()}>Textrevision speichern</button>}
            <span>{textDirty ? "Text noch nicht gespeichert." : "Angezeigter Textstand gespeichert."}</span>
          </div>
          {conflict && <div role="alert" className="wb-error">
            <strong>Konflikt: Deine Textänderung wurde nicht überschrieben.</strong>
            <details open><summary>Aktueller Serverstand · {conflict.revision.id.slice(0, 8)}</summary><pre>{conflict.revision.text}</pre></details>
            <p>Deine Fassung bleibt im Editor. Vor dem Neuladen kopieren oder herunterladen, anschließend bewusst zusammenführen.</p>
            <a download="arbeitskopie-konflikt.md" href={`data:text/markdown;charset=utf-8,${encodeURIComponent(buffer)}`}>Eigene Fassung herunterladen</a>
            <button type="button" onClick={() => void openDocument(current.id)}>Serverstand nach Bestätigung laden</button>
          </div>}
          <SourceEditor key={`${current.id}:${current.revision.id}`} text={buffer}
            readOnly={current.kind !== "draft" || !isHead || busy}
            onChange={setBuffer} annotations={textDirty ? [] : current.annotations}
            selected={textDirty ? null : active} onSelection={setSelection} onError={setError} />
          {textDirty && <p className="wb-warning">Markierungen werden erst nach dem Speichern auf diesen Textstand zugeordnet. Vorhandene historische Bezüge bleiben erhalten.</p>}
          <div className="wb-selection">
            <button type="button" onClick={beginAnnotation} disabled={busy || !selection || textDirty}>Als Block markieren</button>
            <span>{selection ? `${selection.end - selection.start} Codepoints ausgewählt` : "Wähle eine Textpassage im Editor aus."}</span>
          </div>
          <details><summary>Text ohne Editor lesen</summary><pre tabIndex={0}>{buffer}</pre></details>
          {current.kind === "draft" && <ProposalPanel key={`proposals:${current.id}:${current.revision.id}`} config={config}
            document={current} selection={selection} documents={documents}
            blocked={busy || textDirty || dirty || relationDirty || chatDirty}
            onDirty={setProposalDirty} onBusy={setBusy}
            onAccepted={async document => {
              await displayDocument(document); await loadLists();
              setStatus("Überarbeitung als neue Revision übernommen. Original und frühere Markierungen bleiben erhalten.");
            }} />}
        </> : <p>Wähle links einen bestehenden Snapshot oder erfasse ausdrücklich eine registrierte Quelle.</p>}
      </section>
      <section className="wb-panel wb-inspector" tabIndex={-1} ref={panel} aria-label="Blockinspektor">
        <h2>{creating ? "Neue Markierung" : active ? "Block-Metadaten" : "Kontext"}</h2>
        {creating || active ? <>
          <blockquote>{(creating || active)?.exact}</blockquote>
          <form onSubmit={saveMetadata}>
            <label htmlFor="wb-title">Titel</label>
            <input id="wb-title" maxLength={255} required value={metadata.title} disabled={busy}
              onChange={event => { setMetadata({ ...metadata, title: event.target.value }); setDirty(true); }} />
            <label htmlFor="wb-category">Typ</label>
            <select id="wb-category" value={metadata.category} disabled={busy}
              onChange={event => { setMetadata({ ...metadata, category: event.target.value }); setDirty(true); }}>
              {categories.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <label htmlFor="wb-tags">Tags (kommagetrennt)</label>
            <input id="wb-tags" value={metadata.tags} disabled={busy}
              onChange={event => { setMetadata({ ...metadata, tags: event.target.value }); setDirty(true); }} />
            <label htmlFor="wb-note">Eigene Notiz</label>
            <textarea id="wb-note" rows={4} maxLength={10000} value={metadata.note} disabled={busy}
              onChange={event => { setMetadata({ ...metadata, note: event.target.value }); setDirty(true); }} />
            <button disabled={busy || !dirty}>Metadaten speichern</button>
            <p className="wb-muted">{dirty ? "Noch nicht gespeichert." : `Stand ${active?.version || ""} gespeichert.`}</p>
          </form>
          {active && <button type="button" disabled={busy} onClick={() => void openDocument(current!.id)}>Aktuellen Stand neu laden</button>}
        </> : <p>Eine bestehende Markierung öffnen oder eine neue Textauswahl als Block markieren.</p>}
        {active && <>
          <h3>Relation hinzufügen</h3>
          <form onSubmit={saveRelation}>
            <label htmlFor="wb-kind">Beziehung (dieser Block → Ziel)</label>
            <select id="wb-kind" value={kind} disabled={busy || dirty}
              onChange={event => { setKind(event.target.value); setRelationDirty(true); }}>
              {relationKinds.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            <label htmlFor="wb-search">Ziel suchen (eigene Domain)</label>
            <input id="wb-search" type="search" value={targetQuery} disabled={busy || dirty}
              onChange={event => setTargetQuery(event.target.value)} />
            <label htmlFor="wb-target">Zielblock</label>
            <select id="wb-target" required value={target} disabled={busy || dirty}
              onChange={event => { setTarget(event.target.value); setRelationDirty(true); }}>
              <option value="">Ziel wählen</option>
              {availableTargets.map(item => <option key={item.id} value={item.id}>{item.title} · {item.document_title}</option>)}
            </select>
            {targetItem && <blockquote>{targetItem.exact}</blockquote>}
            <label htmlFor="wb-rationale">Begründung</label>
            <textarea id="wb-rationale" rows={2} maxLength={10000} value={rationale} disabled={busy || dirty}
              onChange={event => { setRationale(event.target.value); setRelationDirty(true); }} />
            <button disabled={busy || dirty || !target}>Relation speichern</button>
            {dirty && <p>Metadaten zuerst speichern.</p>}
          </form>
          <h3>Bestehende Verbindungen</h3>
          <ul className="wb-relations">{relevantRelations.map(relation => {
            const outgoing = relation.source_id === active.id;
            const peer = targets.find(item => item.id === (outgoing ? relation.target_id : relation.source_id));
            const label = relationKinds.find(([value]) => value === relation.type)?.[1] || relation.type;
            return <li key={relation.id}>
              <strong>{outgoing ? `Dieser Block → ${label} →` : `← ${label} ←`}</strong>
              {peer ? <button type="button" disabled={busy} onClick={async () => {
                if (!mayLeave()) return;
                await action(async () => {
                  const document = await api<Document>(`documents/${peer.document_id}/revisions/${peer.revision_id}`);
                  await displayDocument(document);
                  setActive(peer);
                  setMetadata({ title: peer.title, category: peer.category, tags: peer.tags.join(", "), note: peer.note });
                });
              }}>{peer.title} · {peer.document_title}</button> : <span>Ziel nicht verfügbar</span>}
              <p>{relation.rationale}</p>
            </li>;
          })}</ul>
          {!relevantRelations.length && <p>Noch keine Relation.</p>}
        </>}
        {current && <ConversationPanel key={`${current.id}:${current.revision.id}`} config={config}
          document={current} buffer={buffer} active={active} documents={documents} onDirty={setChatDirty} />}
      </section>
    </div>
  </div>;
}

const bootstrap = document.getElementById("workbench-bootstrap");
const root = document.getElementById("workbench-root");
if (!bootstrap?.textContent || !root) throw new Error("Workbench-Konfiguration fehlt.");
createRoot(root).render(<Workbench config={JSON.parse(bootstrap.textContent)} />);

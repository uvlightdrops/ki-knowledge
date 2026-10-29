import { useEffect, useRef, useState } from "react";
import { apiClient, ApiError } from "./api";
import { ChangeComparison } from "./ChangeComparison";
import type { Anchor, Bootstrap, Document, DocumentSummary } from "./types";

type ContextSource = { document_title: string; revision_id: string; text: string };
type Proposal = {
  id: string; request_id: string; document_id: string; base_revision_id: string;
  start: number; end: number; exact: string; replacement_markdown: string;
  accepted_replacement: string | null; rationale: string; instruction: string;
  status: "generating" | "pending" | "failed" | "accepted" | "rejected";
  error: string; provider: string; model: string; prompt_version: string;
  context: { sources?: ContextSource[] }; accepted_revision_id: string | null;
};
type Provider = { provider: string; model: string; max_message_chars: number };
type Props = {
  config: Bootstrap; document: Document; selection: Anchor | null;
  documents: DocumentSummary[]; blocked: boolean;
  onDirty: (dirty: boolean) => void; onBusy: (busy: boolean) => void;
  onAccepted: (document: Document) => Promise<void>;
};
const labels = {
  generating: "Wird erzeugt", pending: "Zur Prüfung", failed: "Fehlgeschlagen",
  accepted: "Übernommen", rejected: "Verworfen",
};
const defaultInstruction = "Formuliere die Passage verständlicher. Bewahre Fachbegriffe und die Perspektive des Autors. Füge keine unbelegten Aussagen oder Zuschreibungen hinzu.";

export function ProposalPanel({ config, document, selection, documents, blocked, onDirty, onBusy, onAccepted }: Props) {
  const api = useRef(apiClient(config)).current;
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [replacement, setReplacement] = useState("");
  const [instruction, setInstruction] = useState(defaultInstruction);
  const [instructionDirty, setInstructionDirty] = useState(false);
  const [references, setReferences] = useState<string[]>([]);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [frozen, setFrozen] = useState<{ payload: object; etag: string } | null>(null);
  const [acceptance, setAcceptance] = useState<{ id: string; text: string; etag: string } | null>(null);
  const [serverConflict, setServerConflict] = useState(false);
  const proposal = proposals.find(item => item.id === selectedId);
  const replacementDirty = Boolean(proposal?.status === "pending" && replacement !== proposal.replacement_markdown);
  const isCurrent = document.revision.id === document.head_revision_id;
  const canGenerate = document.kind === "draft" && isCurrent && !blocked && Boolean(selection);
  const stale = Boolean(proposal && proposal.base_revision_id !== document.head_revision_id);

  useEffect(() => {
    let disposed = false;
    Promise.all([
      api<Provider>("provider"),
      api<{ proposals: Proposal[] }>(`documents/${document.id}/proposals`),
    ]).then(([info, result]) => {
      if (!disposed) { setProvider(info); setProposals(result.proposals); }
    }).catch(cause => { if (!disposed) setError(String(cause)); });
    return () => { disposed = true; };
  }, []);
  useEffect(() => {
    onDirty(instructionDirty || replacementDirty || Boolean(frozen) || Boolean(acceptance) || busy);
  }, [instructionDirty, replacementDirty, frozen, acceptance, busy]);

  async function run(operation: () => Promise<void>) {
    setBusy(true); onBusy(true); setError(""); setNotice("");
    try { await operation(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); onBusy(false); }
  }
  function show(item: Proposal) {
    setSelectedId(item.id);
    setServerConflict(false);
    setReplacement(item.status === "accepted" ? item.accepted_replacement ?? item.replacement_markdown : item.replacement_markdown);
  }
  async function refresh() {
    const result = await api<{ proposals: Proposal[] }>(`documents/${document.id}/proposals`);
    setProposals(result.proposals);
    return result.proposals;
  }
  async function generate(event: React.FormEvent) {
    event.preventDefault();
    if ((!canGenerate && !frozen) || !instruction.trim() || replacementDirty || acceptance) return;
    await run(async () => {
      const request = frozen || {
        etag: document.etag,
        payload: {
          request_id: crypto.randomUUID(), base_revision_id: document.revision.id,
          start: selection!.start, end: selection!.end, exact: selection!.exact,
          prefix: selection!.prefix, suffix: selection!.suffix,
          instruction, reference_revision_ids: references,
        },
      };
      setFrozen(request);
      try {
        const result = await api<Proposal>(`documents/${document.id}/proposals`, "POST", request.payload, request.etag);
        show(result);
        if (result.status === "generating") {
          throw new Error("Die Anfrage läuft noch. Später dieselbe Anfrage erneut prüfen; es wird kein zweiter Auftrag gestartet.");
        }
        setFrozen(null); setInstructionDirty(false);
        setNotice("Vorschlag gespeichert. Der Dokumenttext ist unverändert.");
      } finally {
        await refresh();
      }
    });
  }
  async function accept() {
    if (!proposal || blocked || stale || serverConflict || instructionDirty || frozen || proposal.status !== "pending") return;
    if (!replacement && !window.confirm("Die ausgewählte Passage vollständig löschen?")) return;
    await run(async () => {
      const request = acceptance || { id: proposal.id, text: replacement, etag: document.etag };
      setAcceptance(request);
      try {
        const result = await api<{ proposal: Proposal; document: Document }>(
          `proposals/${request.id}/accept`, "POST", { replacement_markdown: request.text }, request.etag,
        );
        setAcceptance(null); setInstructionDirty(false); setFrozen(null);
        await onAccepted(result.document);
      } catch (cause) {
        if (cause instanceof ApiError && [403, 404, 409, 412, 422, 428].includes(cause.status)) {
          setAcceptance(null);
          if ([409, 412].includes(cause.status)) setServerConflict(true);
        }
        throw cause;
      }
    });
  }
  async function reject() {
    if (!proposal || acceptance) return;
    if (replacementDirty && !window.confirm("Eigene Änderungen am Vorschlag verwerfen?")) return;
    await run(async () => {
      const result = await api<Proposal>(`proposals/${proposal.id}/reject`, "POST", {});
      show(result); await refresh();
      setNotice("Vorschlag verworfen. Der Dokumenttext ist unverändert.");
    });
  }
  return <section className="wb-proposals" aria-label="KI-Überarbeitung">
    <h3>Überarbeitung vorschlagen</h3>
    <p>Die KI erstellt einen Vorschlag für eine gespeicherte Passage. Erst deine Übernahme erzeugt eine neue Textrevision.</p>
    {provider && <p className="wb-muted">Provider: <strong>{provider.provider}</strong> · Modell: <strong>{provider.model}</strong></p>}
    {document.kind !== "draft" && <p className="wb-warning">Zum Überarbeiten zuerst eine eigene Arbeitskopie anlegen.</p>}
    {document.kind === "draft" && !busy && (!isCurrent || blocked) && <p className="wb-warning">Zum Erzeugen und Übernehmen den aktuellen Textstand öffnen und offene Texteingaben, Metadaten oder Nachrichten zuerst speichern bzw. abschließen.</p>}
    {error && <p className="wb-error" role="alert">{error}</p>}
    {notice && <p className="wb-muted">{notice}</p>}
    <form onSubmit={generate}>
      <label htmlFor="wb-proposal-instruction">Überarbeitungsauftrag</label>
      <textarea id="wb-proposal-instruction" rows={3} value={instruction} maxLength={provider?.max_message_chars || 8000}
        disabled={busy || Boolean(frozen)} onChange={event => {
          setInstruction(event.target.value); setInstructionDirty(true);
        }} />
      {instructionDirty && !frozen && <button type="button" disabled={busy} onClick={() => {
        setInstruction(defaultInstruction); setInstructionDirty(false); setReferences([]);
      }}>Auftrag zurücksetzen</button>}
      <details>
        <summary>Zusätzliche gespeicherte Referenzen auswählen</summary>
        <fieldset disabled={busy || Boolean(frozen)}>
          <legend>Nur ausdrücklich gewählte Texte werden mitgesendet</legend>
          {documents.filter(item => item.id !== document.id).map(item =>
            <label key={item.id} className="wb-checkbox">
              <input type="checkbox" checked={references.includes(item.revision.id)} onChange={event => {
                setReferences(previous => event.target.checked ? [...previous, item.revision.id] : previous.filter(id => id !== item.revision.id));
                setInstructionDirty(true);
              }} />{item.title} · {item.revision.id.slice(0, 8)}
            </label>)}
        </fieldset>
      </details>
      {selection && !frozen && <details><summary>Ausgewählte Passage ({selection.end - selection.start} Codepoints)</summary><pre>{selection.exact}</pre></details>}
      <button disabled={busy || !provider || (!canGenerate && !frozen) || !instruction.trim() || replacementDirty || Boolean(acceptance)}>
        {busy ? "Bearbeitung läuft …" : frozen ? "Vorschlagsanfrage erneut prüfen" : "KI-Vorschlag erzeugen"}
      </button>
      {frozen && <button type="button" disabled={busy} onClick={() => {
        setFrozen(null); setNotice("Anfrage lokal freigegeben, nicht serverseitig abgebrochen. Gespeicherte Vorschläge vor einem neuen Auftrag prüfen.");
      }}>Anfrage lokal freigeben</button>}
    </form>
    <label htmlFor="wb-proposal-existing">Gespeicherte Überarbeitungsvorschläge</label>
    <select id="wb-proposal-existing" value={selectedId} disabled={busy || Boolean(acceptance)} onChange={event => {
      if (replacementDirty && !window.confirm("Ungespeicherte Änderungen am Vorschlag verwerfen?")) return;
      const item = proposals.find(value => value.id === event.target.value);
      if (item) show(item); else { setSelectedId(""); setReplacement(""); }
    }}>
      <option value="">Vorschlag wählen</option>
      {proposals.map((item, index) => <option key={item.id} value={item.id}>
        {index + 1} · {labels[item.status]} · {item.instruction.slice(0, 60)} · {item.base_revision_id.slice(0, 8)}
      </option>)}
    </select>
    <button type="button" disabled={busy} onClick={() => void run(async () => {
      const items = await refresh();
      const updated = items.find(item => item.id === selectedId);
      if (updated && !replacementDirty && !acceptance) show(updated);
    })}>Vorschlagsliste aktualisieren</button>
    {proposal && <article>
      <p><strong>{labels[proposal.status]}</strong> · {proposal.provider} / {proposal.model} · Basis {proposal.base_revision_id.slice(0, 8)}</p>
      {stale && proposal.status === "pending" && <p className="wb-warning">Veraltete Basis: Dieser Vorschlag kann nicht mehr übernommen werden. Auf aktuellem Textstand einen neuen Vorschlag erzeugen.</p>}
      {serverConflict && <p className="wb-warning">Der Serverstand hat sich geändert. Dein Ersatztext bleibt erhalten; vor dem Öffnen des aktuellen Dokuments gegebenenfalls herunterladen. Keine automatische Zusammenführung.</p>}
      {proposal.error && <p className="wb-error">{proposal.error}</p>}
      {["pending", "accepted", "rejected"].includes(proposal.status) && <>
        <p>Auftrag: {proposal.instruction}</p>
        <p className="wb-answer">Begründung der KI (kein Beleg): {proposal.rationale}</p>
        <p className="wb-muted">Vergleich: entfernte Stellen rot, hinzugefügte Stellen grün. Darunter sind beide Fassungen auch als reiner Text zugänglich.</p>
        <ChangeComparison original={proposal.exact} replacement={replacement} />
        <details><summary>Original und KI-Fassung als Text</summary>
          <h4>Original</h4><pre>{proposal.exact}</pre>
          <h4>Unveränderter KI-Vorschlag</h4><pre>{proposal.replacement_markdown}</pre>
        </details>
        <label htmlFor="wb-proposal-replacement">Ersatztext vor Übernahme bearbeiten</label>
        <textarea id="wb-proposal-replacement" rows={6} value={replacement}
          disabled={busy || proposal.status !== "pending" || Boolean(acceptance)}
          onChange={event => setReplacement(event.target.value)} />
        {!replacement && proposal.status === "pending" && <p className="wb-warning">Leerer Ersatztext löscht die gesamte ausgewählte Passage.</p>}
        {acceptance && <p className="wb-warning">Übernahme noch nicht bestätigt. Erneut prüfen verwendet denselben eingefrorenen Ersatztext.</p>}
        {proposal.status === "pending" && <>
          <a download="ueberarbeitung-vorschlag.md" href={`data:text/markdown;charset=utf-8,${encodeURIComponent(replacement)}`}>Ersatztext herunterladen</a>{" "}
          <button type="button" disabled={busy || blocked || stale || serverConflict || instructionDirty || Boolean(frozen) || !isCurrent || document.kind !== "draft"} onClick={() => void accept()}>
            {acceptance ? "Dieselbe Übernahme erneut prüfen" : "Vorschlag übernehmen"}
          </button>{" "}
          <button type="button" disabled={busy || Boolean(acceptance)} onClick={() => void reject()}>Vorschlag verwerfen</button>
        </>}
        {proposal.accepted_revision_id && <p>Übernommen als Revision {proposal.accepted_revision_id.slice(0, 8)}.</p>}
      </>}
      <details><summary>Herkunft und tatsächlich übermittelter Kontext</summary>
        <p>Prompt: {proposal.prompt_version}. Kontextnachweise sind keine verifizierten Antwortzitate.</p>
        {proposal.context.sources?.map((source, index) => <div key={index}>
          <strong>{source.document_title} · {source.revision_id}</strong><pre>{source.text}</pre>
        </div>)}
      </details>
    </article>}
  </section>;
}

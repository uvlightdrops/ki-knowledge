import { useEffect, useRef, useState } from "react";
import { apiClient } from "./api";
import type { Annotation, Bootstrap, Document, DocumentSummary } from "./types";

type Provider = { provider: string; model: string; max_context_chars: number; max_message_chars: number; timeout_seconds: number };
type ContextSource = {
  document_id: string; document_title: string; revision_id: string;
  annotation_id?: string; text: string; unsaved: boolean;
};
type Turn = {
  id: string; message: string; answer: string; status: string; error: string;
  provider: string; model: string; context: { unsaved: boolean; sources: ContextSource[] };
};
type Conversation = {
  id: string; document_id: string; revision_id: string; annotation_id: string | null;
  messages: Turn[]; pending: boolean;
};
type Summary = { id: string; revision_id: string; annotation_id: string | null };
type Props = {
  config: Bootstrap; document: Document; buffer: string;
  active: Annotation | null; documents: DocumentSummary[];
  onDirty: (dirty: boolean) => void;
};

export function ConversationPanel({ config, document, buffer, active, documents, onDirty }: Props) {
  const api = useRef(apiClient(config)).current;
  const [provider, setProvider] = useState<Provider | null>(null);
  const [conversations, setConversations] = useState<Summary[]>([]);
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [scope, setScope] = useState("document");
  const [references, setReferences] = useState<string[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [frozenRequest, setFrozenRequest] = useState<object | null>(null);
  const unsaved = buffer !== document.revision.text;

  useEffect(() => {
    let disposed = false;
    Promise.allSettled([
      api<Provider>("provider"),
      api<{ conversations: Summary[] }>(`conversations?document_id=${document.id}`),
    ]).then(([info, list]) => {
      if (disposed) return;
      const failures = [];
      if (info.status === "fulfilled") setProvider(info.value);
      else failures.push(String(info.reason));
      if (list.status === "fulfilled") setConversations(list.value.conversations);
      else failures.push(String(list.reason));
      if (failures.length) setError(failures.join("\n"));
    });
    return () => { disposed = true; };
  }, []);
  useEffect(() => { onDirty(Boolean(message) || busy || Boolean(frozenRequest)); }, [message, busy, frozenRequest]);

  async function run(operation: () => Promise<void>) {
    setBusy(true); setError("");
    try { await operation(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : String(cause)); }
    finally { setBusy(false); }
  }
  async function createConversation() {
    if (scope === "annotation" && (!active || unsaved)) return;
    await run(async () => {
      const result = await api<Conversation>("conversations", "POST", {
        document_id: document.id, revision_id: document.revision.id,
        ...(scope === "annotation" && active ? { annotation_id: active.id } : {}),
      });
      setConversation(result);
      setConversations(previous => [...previous, result]);
      setRequestId(null); setFrozenRequest(null);
    });
  }
  async function send(event: React.FormEvent) {
    event.preventDefault();
    if (!conversation || !message.trim() || (unsaved && conversation.annotation_id)) return;
    await run(async () => {
      const id = requestId || crypto.randomUUID();
      const payload = frozenRequest || {
        request_id: id,
        message,
        context: {
          reference_revision_ids: references,
          ...(unsaved ? { buffer_text: buffer, base_revision_id: document.revision.id } : {}),
        },
      };
      setRequestId(id); setFrozenRequest(payload);
      try {
        const result = await api<Turn>(`conversations/${conversation.id}/messages`, "POST", payload);
        if (result.status !== "complete") {
          throw new Error(result.error || "Die Anfrage läuft noch. Später dieselbe Anfrage erneut prüfen.");
        }
        setMessage(""); setRequestId(null); setFrozenRequest(null);
      } finally {
        setConversation(await api<Conversation>(`conversations/${conversation.id}`));
      }
    });
  }
  const currentSummaries = conversations.filter(item => item.revision_id === document.revision.id);
  return <section className="wb-chat" aria-label="KI-Gespräch">
    <h3>Mit der KI über Text sprechen</h3>
    <p>Antworten verändern weder Text noch Markierungen. Kein automatischer Zugriff auf weitere Domain-Inhalte.</p>
    {provider && <p className="wb-muted">
      Provider: <strong>{provider.provider}</strong> · Modell: <strong>{provider.model}</strong><br />
      Kontextlimit: {provider.max_context_chars} Zeichen · Anfragefrist: {provider.timeout_seconds} s
    </p>}
    {error && <p className="wb-error" role="alert">{error}</p>}
    <label htmlFor="wb-chat-existing">Gespeichertes Gespräch (diese Revision)</label>
    <select id="wb-chat-existing" value={conversation?.id || ""} disabled={busy || Boolean(message) || Boolean(frozenRequest)}
      onChange={event => {
        const id = event.target.value;
        if (!id) { setConversation(null); return; }
        void run(async () => setConversation(await api<Conversation>(`conversations/${id}`)));
      }}>
      <option value="">Gespräch wählen</option>
      {currentSummaries.map((item, index) => <option key={item.id} value={item.id}>
        Gespräch {index + 1} · {item.annotation_id ? "Markierung" : "Dokument"}
      </option>)}
    </select>
    <label htmlFor="wb-chat-scope">Basis für ein neues Gespräch</label>
    <select id="wb-chat-scope" value={scope} disabled={busy || Boolean(message) || Boolean(frozenRequest)}
      onChange={event => setScope(event.target.value)}>
      <option value="document">Angezeigtes Dokument / Revision {document.revision.id.slice(0, 8)}</option>
      <option value="annotation" disabled={!active || unsaved}>Ausgewählte gespeicherte Markierung</option>
    </select>
    <button type="button" disabled={busy || !provider || Boolean(message) || Boolean(frozenRequest) ||
      (scope === "annotation" && (!active || unsaved))} onClick={() => void createConversation()}>Neues Gespräch starten</button>
    {conversation && <>
      <p className="wb-muted">Festgelegte Basis: {conversation.annotation_id ? "gespeicherte Markierung" : "angezeigtes Dokument"} ·
        Revision {conversation.revision_id.slice(0, 8)}. Eine andere Markierung erfordert ein neues Gespräch.</p>
      {conversation.pending && <p className="wb-warning">Eine Anfrage ist noch offen.
        Erneutes Senden prüft serverseitig den offenen Zustand; eine abgebrochene
        Reservierung wird erst nach ihrer Ablaufzeit freigegeben.</p>}
      {unsaved && <p className="wb-warning">{conversation.annotation_id
        ? "Die Markierung gehört zum gespeicherten Stand. Für den ungespeicherten Puffer bitte ein neues Dokumentgespräch starten."
        : "Die nächste Anfrage überträgt und speichert den ungespeicherten Puffer als Gesprächskontext. Er wird dabei nicht als Dokumentrevision gespeichert."}</p>}
      <fieldset disabled={busy || Boolean(frozenRequest)}>
        <legend>Zusätzlich ausgewählte Referenzen</legend>
        {documents.filter(item => item.id !== document.id).map(item =>
          <label key={item.id} className="wb-checkbox">
            <input type="checkbox" checked={references.includes(item.revision.id)} onChange={event =>
              setReferences(previous => event.target.checked ? [...previous, item.revision.id] : previous.filter(id => id !== item.revision.id))} />
            {item.title} · Revision {item.revision.id.slice(0, 8)}
          </label>)}
      </fieldset>
      <div className="wb-messages" aria-live="polite">
        {conversation.messages.map(turn => <article key={turn.id}>
          <strong>Du</strong><p>{turn.message}</p>
          <strong>KI · {turn.provider} / {turn.model} · {turn.status}</strong>
          {turn.answer && <p className="wb-answer">{turn.answer}</p>}
          {turn.error && <p className="wb-error">{turn.error}</p>}
          <details>
            <summary>Tatsächlich übermittelter Kontext {turn.context.unsaved ? "(mit ungespeichertem Text)" : ""}</summary>
            <p>Dies sind Kontextnachweise, keine automatisch verifizierten Antwortzitate.</p>
            {turn.context.sources.map((source, index) => <div key={index}>
              <a href={`${config.apiBase}documents/${source.document_id}/revisions/${source.revision_id}?domain=${encodeURIComponent(config.domain)}`}
                target="_blank" rel="noreferrer">{source.document_title} · {source.revision_id.slice(0, 8)}</a>
              {source.unsaved && <strong> · Ungespeicherter Puffer</strong>}
              <pre>{source.text}</pre>
            </div>)}
          </details>
        </article>)}
      </div>
      <form onSubmit={send}>
        <p className="wb-muted">Nachrichten und übermittelter Textkontext werden beim Gespräch dauerhaft gespeichert.</p>
        <label htmlFor="wb-chat-message">Nachricht</label>
        <textarea id="wb-chat-message" rows={4} value={message} maxLength={provider?.max_message_chars || 8000}
          required disabled={busy || Boolean(frozenRequest)} onChange={event => setMessage(event.target.value)} />
        <button disabled={busy || !message.trim() || (unsaved && Boolean(conversation.annotation_id))}>
          {busy ? "KI-Anfrage läuft …" : frozenRequest ? "Dieselbe Anfrage erneut prüfen" : "Fragen"}
        </button>
        {frozenRequest && <button type="button" disabled={busy} onClick={() => {
          setRequestId(null); setFrozenRequest(null);
        }}>Anfrage freigeben, danach bewusst neu senden</button>}
      </form>
    </>}
  </section>;
}

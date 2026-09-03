# Content-Modell-Matrix

> Voraussetzung: [`content-model-matrix-intro.md`](./content-model-matrix-intro.md)
> (Zweck, Dimensionen, "Spiegeln statt Duplizieren"-Prinzip).
>
> Diese Matrix bildet jedes bestehende Feld der Legacy-/Kern-Modelle auf sein
> kanonisches und sein Wagtail-Äquivalent ab, markiert den Migrationsstatus
> und die "Owning System"-Zuständigkeit, solange beide Welten parallel
> laufen (Strangler-Pattern, siehe `AGENTS.md` / Schritte 1–5 dieser Phase).

**Migrationsstatus-Legende:**
- 🟢 `gespiegelt` — Wagtail liest live vom Legacy-Modell (kein Duplikat, keine Sync-Lücke)
- 🟡 `nur-legacy` — existiert nur im Legacy-Modell, noch keine Wagtail-Repräsentation
- 🔵 `nur-wagtail` — existiert nur in Wagtail, hat keine Legacy-Entsprechung (typischerweise Editorial-/Workflow-Felder)
- ⚪ `betriebsintern` — bewusst nicht migrationsrelevant (Betriebsdaten, siehe Abschnitt 5)

---

## 1. `InfoSiteProject` → `DataSourceDescriptor` → `DataSourceIndexPage`/`DataSourceDetailPage`

| Legacy-Feld (`InfoSiteProject`) | Kanonisches Äquivalent (`DataSourceDescriptor`) | Wagtail-Äquivalent | Status | Owning System |
|---|---|---|---|---|
| `title` | `title` | gelesen zur Laufzeit via Adapter (nicht dupliziert in `DataSourceDetailPage`) | 🟢 gespiegelt | Legacy (`InfoSiteProject`) |
| `domain` | `metadata["domain"]` | gelesen zur Laufzeit | 🟢 gespiegelt | Legacy |
| `working_title` | `metadata["working_title"]` | gelesen zur Laufzeit | 🟢 gespiegelt | Legacy |
| `description` | — (nicht gemappt) | — | 🟡 nur-legacy | Legacy |
| `source_directory` | `uri` (falls gesetzt, sonst Fallback via `resolve_markdown_root`) | gelesen zur Laufzeit (`descriptor.uri`) | 🟢 gespiegelt | Legacy |
| `enabled` | — (nur als Filter in `DataSourceIndexPage.get_context`: `filter(enabled=True)`) | implizit (nicht gelistet, wenn `False`) | 🟢 gespiegelt (implizit) | Legacy |
| `auto_discover` | — | — | 🟡 nur-legacy | Legacy |
| `sync_status` | `status` | gelesen zur Laufzeit (`descriptor.status`) | 🟢 gespiegelt | Legacy |
| `last_sync_at` / `last_sync_error` | — | — | 🟡 nur-legacy | Legacy |
| `generation_status` / `generation_error` | — | — | 🟡 nur-legacy | Legacy |
| `output_dir` | — (siehe `resolve_markdown_root`-Fallback-Logik, verwendet nicht `output_dir`) | — | 🟡 nur-legacy | Legacy |
| `version_count` | `metadata` (in `create_knowledge_source`, `block_storage.py`) | — | 🟢 gespiegelt (teilweise) | Legacy |
| `id` | `metadata["project_id"]` | `DataSourceDetailPage.infosite_project_id` (FK-Ersatz per Konvention) | 🟢 gespiegelt | Legacy |
| — | — | `slug`, `live`, `first_published_at`, `last_published_at`, Revisions, Moderations-Workflow (geerbt von `wagtail.models.Page`) | 🔵 nur-wagtail | Wagtail |
| — | — | `intro` (RichText, nur auf `DataSourceIndexPage`) | 🔵 nur-wagtail | Wagtail |
| — | — | `editorial_notes` (RichText, nur auf `DataSourceDetailPage`) | 🔵 nur-wagtail | Wagtail |

**Beobachtung:** `description`, `auto_discover`, `last_sync_*`, `generation_*`
und `output_dir` haben aktuell **keine** Wagtail-Repräsentation. Das ist für
die reine Katalog-Browsing-Funktion (Schritt 3/5) unkritisch, wäre aber eine
Lücke, sobald Wagtail-Editoren diese Betriebsfelder einsehen oder gar
bearbeiten sollen sollen (offene Frage, siehe Abschnitt 6).

---

## 2. `SourceDocument` → `SourceDocumentRecord` → (Wagtail-Kontext, kein eigenes Page-Modell)

| Legacy-Feld (`SourceDocument`) | Kanonisches Äquivalent (`SourceDocumentRecord`) | Wagtail-Äquivalent | Status | Owning System |
|---|---|---|---|---|
| `project` (FK) | `source_id` | `DataSourceDetailPage.infosite_project_id` (indirekt, über die Elternseite) | 🟢 gespiegelt | Legacy |
| `file_path` | `uri` | `documents` Kontextliste in `data_source_detail_page.html` | 🟢 gespiegelt | Legacy |
| `file_type` | `document_type` | angezeigt als `doc.document_type` | 🟢 gespiegelt | Legacy |
| `title` | `title` | angezeigt als `doc.title` | 🟢 gespiegelt | Legacy |
| `file_size` | `metadata["file_size"]` | nicht angezeigt (Template zeigt nur Titel/Typ/Status) | 🟡 nur-legacy (im Kanon vorhanden, in Wagtail-Template ungenutzt) | Legacy |
| `modified_at` | `metadata["modified_at"]` | nicht angezeigt | 🟡 nur-legacy (im Kanon vorhanden, in Wagtail-Template ungenutzt) | Legacy |
| `import_status` | `status` | angezeigt als `doc.status` | 🟢 gespiegelt | Legacy |
| `imported` | `metadata["imported"]` | nicht angezeigt | 🟡 nur-legacy | Legacy |
| `imported_at` / `import_error` | — | — | 🟡 nur-legacy | Legacy |
| *(kein Feld — `checksum` existiert nicht auf `SourceDocument`)* | `checksum` (immer `None`, via `getattr(document, "checksum", None)`) | nicht angezeigt | ⚪ betriebsintern (totes Feld im Kanon, kein Legacy-Gegenstück) | — |

**Wichtig:** Es gibt **kein eigenes Wagtail-Page-Modell pro Dokument** — anders
als bei Projekten (`DataSourceDetailPage`), werden Dokumente nur als
Kontextliste innerhalb der Projekt-Detailseite gerendert (`context["documents"]`
in `DataSourceDetailPage.get_context`, begrenzt auf die ersten 50). Das ist
eine bewusste Design-Entscheidung aus Schritt 3 (keine 1:1-Page-Explosion
für potenziell hunderte Dokumente pro Projekt), sollte aber in der Matrix
festgehalten werden, damit ein künftiger Cutover nicht fälschlich ein
fehlendes `DataSourceDocumentPage`-Modell als Bug interpretiert.

---

## 3. `KnowledgeSource` / `KnowledgeBlockRecord` (Wissens-Ebene) → Wagtail

| Legacy/Kanonisches Modell | Feld | Wagtail-Äquivalent | Status | Owning System |
|---|---|---|---|---|
| `KnowledgeSource` | `source_id`, `source_type`, `title`, `location`, `metadata` | `KnowledgeBlockDetailPage` (read-only Spiegel, kein Duplikat) | 🟢 gespiegelt | `KnowledgeStore` |
| `KnowledgeBlockRecord` | `block_id`, `source_id`, `block_type`, `title`, `content`, `parent_block_id`, `path`, `order_index`, `tags`, `metadata` | `KnowledgeBlockDetailPage.blocks` (Kontext, live gelesen) | 🟢 gespiegelt | `KnowledgeStore` |

**Update (Wagtail-Cutover Schritt 6):** `KnowledgeBlockIndexPage`/
`KnowledgeBlockDetailPage` (`ki_knowledge/wagtail_cms/models.py`) schließen
diese Lücke inzwischen — nach exakt demselben Muster wie
`DataSourceIndexPage`/`DataSourceDetailPage`: eine editorierbare Katalog-
/Detailseite in Wagtail, deren `get_context()` die Blöcke live über
`InfoSiteBlockStorage(project).get_stored_blocks()`/`.get_statistics()`
liest. Es gibt weiterhin **keine** Datenduplikation — `KnowledgeStore`
(SQLite) bleibt alleinige Quelle der Wahrheit, Wagtail besitzt nur die
Editorial-Katalogseite drumherum (Titel, `editorial_notes`,
Projekt-Verknüpfung via `infosite_project_id`). Einzelne Blöcke sind
weiterhin **nicht** individuell in Wagtail editierbar — das bleibt
bewusst so (siehe Abschnitt 6, Frage 4).

---

## 4. `DataSourceDescriptor.status` / `SourceDocumentRecord.status` vs. Wagtail-Workflow-States

Ein Spezialfall, der eigene Aufmerksamkeit verdient: Die kanonischen
Status-Werte (`discovered`, `synced`, `imported`, `failed`, je nach
Kontext) sind **freie Strings**, die von den jeweiligen Legacy-Modellen
(`sync_status`, `import_status`) übernommen werden. Wagtail dagegen hat ein
eigenes, strukturiertes Workflow-Modell (`draft` → `in_review` →
`approved`/`rejected` → `published`, verwaltet über `wagtail.models.Page.live`,
`Revision`, `WorkflowState`).

| Kanonischer Status-Wert | Wagtail-Workflow-Zustand | Mapping-Qualität |
|---|---|---|
| `discovered` | *(kein Äquivalent — Wagtail kennt nur "existiert als Page" oder nicht)* | ❌ keine Entsprechung |
| `synced` | *(kein Äquivalent)* | ❌ keine Entsprechung |
| `imported` | am ehesten `live=True` (veröffentlicht) | ⚠️ grobe Näherung |
| `failed` | *(kein Äquivalent — Wagtail-Pages kennen keinen Fehlerzustand)* | ❌ keine Entsprechung |

**Diese Tabelle zeigte ursprünglich eine offene Lücke** (Abschnitt 6, Frage
2). **Update (Wagtail-Cutover Schritt 6):**
`ki_knowledge/knowledge/wagtail_status_mapping.py` formalisiert diese
Tabelle jetzt im Code (`describe_wagtail_equivalent(status)`,
`all_mappings()`) und wird auf `DataSourceDetailPage` als Hinweis-Panel
neben dem kanonischen Status angezeigt ("Wagtail-Workflow-Äquivalent: …").
Das ist bewusst **nur eine informative/advisory Anzeige** — es findet
weiterhin **keine** automatische Zustandsübertragung statt (kein
Auto-Publish bei `imported`, kein Auto-Draft bei `discovered`). Die beiden
Statusmodelle laufen also nach wie vor unabhängig nebeneinander; das
Mapping macht die Diskrepanz nur sichtbar/nachvollziehbar, statt sie
aufzulösen. Ein echter Cutover (Wagtail wird primäre Statusquelle) bliebe
weiterhin eine offene Design-Entscheidung.

---

## 5. Bewusst nicht migrationsrelevante Daten (⚪ betriebsintern)

Diese Modelle/Tabellen sind **absichtlich außerhalb** der Content-Modell-
Matrix, weil sie Betriebsdaten und keine editorierbaren Inhalte sind:

- `KnowledgeExtractionJobStore` (SQLite-Tabelle `knowledge_extraction_jobs`,
  Schritt 4) — Job-Historie der Pipeline-Ausführung.
- `PDFBatchProcessor`/`PDFImportJob` (`pdf_batch.py`) — analoge Job-Tabelle
  für PDF-Importe.
- Wagtail-interne Tabellen (`wagtailcore_pagerevision`, `wagtailsearch_*`,
  Task-/Workflow-Log-Tabellen) — Wagtail-Betriebsdaten, kein Content im
  fachlichen Sinn.

---

## 6. Offene Fragen (aus der Matrix abgeleitet)

1. **Betriebsfelder ohne Wagtail-Sicht**: Sollen `sync_status`,
   `last_sync_error`, `generation_status`, `generation_error` jemals in der
   Wagtail-Oberfläche sichtbar sein (z. B. als schreibgeschützte Panels),
   oder bleiben sie dauerhaft "nur-legacy"? Aktuell: bleiben nur-legacy,
   solange kein Editorial-Bedarf dafür besteht.
2. **Statusmodell-Mapping**: ✅ **Erledigt** (Wagtail-Cutover Schritt 6) —
   `wagtail_status_mapping.py` liefert jetzt ein explizites, advisory
   Mapping, sichtbar auf `DataSourceDetailPage`. Ein echter Cutover
   (Wagtail wird primäre Statusquelle mit eigenem Custom-Workflow) bleibt
   weiterhin eine separate, nicht getroffene Design-Entscheidung.
3. **Dokument-Granularität**: Sollen einzelne `SourceDocument`s je einen
   eigenen Wagtail-Page-Typ bekommen (z. B. für granulare Freigabe-
   Workflows pro Dokument), oder bleibt die Projekt-Ebene (`DataSourceDetailPage`)
   die einzige editorierbare Einheit? Aktuell: Projekt-Ebene, siehe
   Abschnitt 2.
4. **Wissensblöcke in Wagtail?**: ✅ **Teilweise erledigt** (Wagtail-Cutover
   Schritt 6) — `KnowledgeBlockIndexPage`/`KnowledgeBlockDetailPage`
   bilden jetzt eine editorierbare Katalog-/Detailseite pro Projekt.
   Weiterhin offen: einzelne `KnowledgeBlockRecord`-Einträge sind **nicht**
   individuell editierbar (kein Wagtail-Snippet pro Block) — sie bleiben
   reine Anzeige-Artefakte der Pipeline, wie ursprünglich entschieden.
5. **Totes `checksum`-Feld**: `SourceDocumentRecord.checksum` wird von
   beiden Adapter-Pfaden (`InfoSiteSourceAdapter.to_document`,
   `CanonicalDataSourceService.from_document`) per `getattr(..., None)`
   befüllt, weil `SourceDocument` gar kein `checksum`-Attribut besitzt —
   das Feld ist im Kanon vorgesehen (z. B. für künftige Change-Detection),
   aber aktuell für InfoSite immer `None`. Entweder `SourceDocument` um ein
   echtes Checksum-Feld ergänzen (z. B. für Re-Sync-Erkennung), oder das
   Feld im Kanon als "optional, providerabhängig" dokumentieren.

---

## 7. Zusammenfassung

Der aktuelle Stand ist **bewusst asymmetrisch**: Wagtail bildet nur einen
schmalen, editorialen Ausschnitt (Projekt-Titel, -Status, -Notizen,
Dokumentliste) des viel breiteren Legacy-Datenmodells ab, und dupliziert
dabei nichts — es referenziert und liest live. Die größten Lücken
(Betriebsfelder, Statusmodell-Inkompatibilität, fehlende Dokument- und
Wissensblock-Granularität) sind alle bewusste, dokumentierte
Entscheidungen für die aktuelle Phase, keine übersehenen Bugs. Sie bilden
die Grundlage für die in Abschnitt 6 aufgeführten offenen Fragen, über die
vor einem weiteren Cutover-Schritt entschieden werden sollte.

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

## 2. `SourceDocument` → Wagtail-Snippet (`SourceDocumentViewSet`) + `SourceDocumentRecord` (Kanon)

**Update (Wagtail-Workflow Schritt 1):** `SourceDocument` ist inzwischen
selbst ein Wagtail-Snippet mit echtem Workflow-Unterbau
(`WorkflowMixin`/`DraftStateMixin`/`RevisionMixin`, registriert als
`SourceDocumentViewSet` in `wagtail_cms/wagtail_hooks.py`) — nicht mehr nur
eine Kontextliste innerhalb der Projekt-Detailseite. Die Pipeline-Felder
(`file_path`, `file_type`, `import_status`, …) bleiben unverändert die
"Quelle der Wahrheit"; das Snippet fügt zusätzliche, rein editoriale Felder
hinzu, die es vorher nicht gab.

| Feld | Herkunft | Wagtail-Darstellung | Status | Owning System |
|---|---|---|---|---|
| `project` (FK) | Pipeline | `FieldPanel("project")`, editierbar | 🟢 gespiegelt | Legacy |
| `file_path`, `file_type`, `import_status` | Pipeline | `FieldPanel(..., read_only=True)` in der Snippet-Maske; zusätzlich Spalten in `list_display` | 🟢 gespiegelt | Legacy |
| `title` | Pipeline | editierbar (`FieldPanel("title")`) | 🟢 gespiegelt | Legacy |
| `review_status` | **neu** (Schritt 1) | editierbar, Choices `none`/`in_review`/`approved`/`rejected` | 🔵 nur-wagtail | Wagtail (additiv) |
| `editor_notes` | **neu** (Schritt 1) | Freitext, editierbar | 🔵 nur-wagtail | Wagtail (additiv) |
| `tags` | **neu** (Schritt 1, django-taggit) | editierbar | 🔵 nur-wagtail | Wagtail (additiv) |
| `workflow_status_display` | **neu** (Schritt 6) | schreibgeschützte Anzeige-Property, zeigt den zuletzt bekannten Wagtail-Moderations-Workflow-Zustand (inkl. abgeschlossener Läufe) neben `review_status` | 🔵 nur-wagtail | Wagtail |
| — | — | `slug`-freie Snippet-Ebene: Draft/Live-Status, Revisions, aktiver Moderations-Workflow (`GroupApprovalTask`, Schritt 6) | 🔵 nur-wagtail | Wagtail |

`DataSourceDetailPage` (die Projekt-Ebene) embeddet seit Schritt 5 eine
echte, gefilterte `SourceDocument`-Tabelle (`project.documents.all()[:50]`,
mit Bearbeiten-Link zum Snippet-Editor) statt der früheren, nicht
editierbaren Descriptor-Liste (`context["documents"]`/`InfoSiteSourceAdapter.to_documents`).
Diese Adapter-Konvertierung existiert weiterhin (für andere Konsumenten,
z. B. `knowledge/adapters.py`), wird aber von der Wagtail-Detailseite nicht
mehr benutzt.

**Weiterhin unverändert:** Es gibt **kein eigenes Wagtail-Page-Modell pro
Dokument** — die Granularität bleibt "Projekt-Detailseite embeddet
Dokumenten-Tabelle", nicht "1 Page pro Dokument" (siehe Abschnitt 6, Frage
3 — inzwischen indirekt durch das Snippet-Modell gelöst: jedes Dokument
_hat_ jetzt eine eigene editierbare Einheit, nur eben als Snippet statt als
Page).

---

## 2a. `GeneratedDocument` — neues Modell für die Output-Seite (Wagtail-Workflow Schritt 2)

Anders als `SourceDocument` (Input-Seite) hatte die Output-Seite
(generierte/verfeinerte InfoSite-Markdown-Dateien unter `data_out/`) vor
Schritt 2 **überhaupt keine** Datenbank-Repräsentation — Dateien existierten
nur auf der Festplatte. `GeneratedDocument` (`infosite_models.py`) schließt
diese Lücke, mit demselben Wagtail-Mixin-Aufbau wie `SourceDocument`
(`WorkflowMixin`/`DraftStateMixin`/`RevisionMixin`, Snippet
`GeneratedDocumentViewSet`).

| Feld | Zweck | Status |
|---|---|---|
| `project` (FK), `file_path`, `generated_at`, `ai_refinement_mode`, `content_hash` | Pipeline-Metadaten, automatisch befüllt von `services/output_registry.py` bei jeder Generierung/Verfeinerung | 🟢 gespiegelt (aber: dieses Modell selbst *ist* die einzige DB-Repräsentation — kein separates Legacy-Modell dahinter) |
| `used_sources` (M2M → `SourceDocument`) | Traceability: welche Input-Dateien in dieses Output-Dokument eingeflossen sind | 🔵 nur-wagtail (neu) |
| `review_status`, `editor_notes`, `tags`, `workflow_status_display` | Editorial-Layer, identisch zum Muster bei `SourceDocument` | 🔵 nur-wagtail |

**Bewusste Trennung:** `SourceDocument` (Input) und `GeneratedDocument`
(Output) sind zwei **getrennte** Modelle mit getrennten Snippet-Listen und
getrennten Landingpages (`/data-sources/` vs. `/output/`) — sie werden
**nicht** in einer gemeinsamen Tabelle/Oberfläche zusammengeführt. Die
einzige Brücke ist die `used_sources`-M2M-Relation für Traceability-Anzeige
(Projekt-Detailseite: "🔗 Input ↔ Output"-Panel, Output-Landingpage:
`used_sources_summary`-Spalte).

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

**Update (Wagtail-Workflow Schritt 6 — echter Freigabe-Workflow):** Zusätzlich
zu diesem *advisory* Mapping (Legacy-Status ↔ Wagtail-Page-Konzepte) gibt es
jetzt einen **echten, aktiven** Wagtail-Moderations-Workflow auf den
Snippet-Modellen selbst: Migration `0008_editorial_workflow.py` legt einen
`Workflow` ("Redaktionelle Freigabe") mit einer `GroupApprovalTask`
(genehmigt von der Gruppe "Editors") an und verknüpft ihn per
`WorkflowContentType` mit sowohl `SourceDocument` als auch
`GeneratedDocument`. Editoren können im Snippet-Editor "Submit for
moderation" auslegen; Mitglieder der Gruppe "Editors" sehen die
Aufgabe im Moderations-Dashboard und können genehmigen/ablehnen. Dieser
Workflow-Zustand ist **komplett unabhängig** vom einfachen `review_status`-
Feld (Schritt 1/2) — beide existieren nebeneinander und werden auch
nebeneinander angezeigt (`workflow_status_display`-Property, sichtbar in
den Snippet-Listen, auf `DataSourceDetailPage` und der Output-Landingpage).
Es gibt (bewusst) **keine** automatische Synchronisation zwischen
`review_status` und dem Wagtail-Workflow-Ergebnis — ein Redakteur kann
`review_status="approved"` setzen, ohne den Workflow zu durchlaufen, und
umgekehrt. Diese Entkopplung war eine bewusste Entscheidung, um den
einfachen Statuswechsel (schneller Alltagsgebrauch) nicht an den
schwergewichtigeren, gruppen-basierten Moderationsprozess zu koppeln.

---

## 4a. Domain-Registry: gemeinsame Klammer, getrennte Speicher

Mit der gemeinsamen `Domain`-Registry (`infosite_models.Domain`, siehe
Commit "Gemeinsame Domain-Registry für beide Pipelines") referenzieren
sowohl die ältere Jira/OWL/Markdown-Workspace-Pipeline (session-basierter
String-Domain in `views.py`) als auch die InfoSite-Pipeline
(`InfoSiteProject.domain`) dieselbe Liste bekannter Domain-Slugs. **Wichtig:**
Dies ist **keine** Zusammenführung der beiden Pipelines/Speicher — beide
bleiben komplett getrennt (unterschiedliche Modelle, unterschiedliche
Scan-/Importlogik, unterschiedliche Landingpages `/data-sources/` vs.
`/output/infosite/`). Die Registry ist rein additiv: `ensure_domain_registered()`
wird von beiden Systemen aufgerufen (immer wenn eine Domain neu entsteht),
sodass eine gemeinsame Domain-Tabelle mit kombinierten Kennzahlen beider
Pipelines angezeigt werden kann (`/data-sources/`-Landingpage), ohne dass
eine Pipeline die Daten der anderen lesen oder schreiben muss.

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
2. **Statusmodell-Mapping**: ✅ **Erledigt** (Wagtail-Cutover Schritt 6,
   erweitert im Wagtail-Workflow Schritt 6) — es gibt jetzt sowohl das
   advisory Mapping (`wagtail_status_mapping.py`) als auch einen **echten**
   aktiven Wagtail-Moderations-Workflow (`GroupApprovalTask`, Abschnitt 4).
   Beide Statusquellen (`review_status` und der Wagtail-Workflow-Zustand)
   laufen bewusst unabhängig nebeneinander, werden aber nebeneinander
   angezeigt (`workflow_status_display`). Ein Cutover, bei dem Wagtail zur
   *einzigen* Statusquelle würde, ist weiterhin keine getroffene
   Design-Entscheidung.
3. **Dokument-Granularität**: ✅ **Erledigt** (Wagtail-Workflow Schritt 1) —
   `SourceDocument` ist jetzt selbst ein Wagtail-Snippet mit eigenem
   Workflow/Revisions, also eine individuell editierbare/genehmigbare
   Einheit pro Dokument (nicht als Page, sondern als Snippet). Die
   Projekt-Detailseite (`DataSourceDetailPage`) bleibt der Einstiegspunkt,
   embeddet seit Schritt 5 aber eine echte gefilterte Snippet-Tabelle statt
   einer reinen Anzeigeliste.
4. **Wissensblöcke in Wagtail?**: ✅ **Teilweise erledigt** (Wagtail-Cutover
   Schritt 6) — `KnowledgeBlockIndexPage`/`KnowledgeBlockDetailPage`
   bilden jetzt eine editierbare Katalog-/Detailseite pro Projekt.
   Weiterhin offen: einzelne `KnowledgeBlockRecord`-Einträge sind **nicht**
   individuell editierbar (kein Wagtail-Snippet pro Block) — sie bleiben
   reine Anzeige-Artefakte der Pipeline, wie ursprünglich entschieden. Das
   ist eine bewusste Abgrenzung zur Output-Seite: Anders als
   `SourceDocument`/`GeneratedDocument` (Wagtail-Workflow Schritt 1/2)
   wurde für die Wissensblock-Ebene (Session-basierte Jira/OWL/Markdown-
   Workspace-Pipeline) bewusst **kein** eigenes Snippet-Modell eingeführt —
   siehe Abschnitt 4a zur Domain-Registry-Abgrenzung.
5. **Totes `checksum`-Feld**: `SourceDocumentRecord.checksum` wird von
   beiden Adapter-Pfaden (`InfoSiteSourceAdapter.to_document`,
   `CanonicalDataSourceService.from_document`) per `getattr(..., None)`
   befüllt, weil `SourceDocument` gar kein `checksum`-Attribut besitzt —
   das Feld ist im Kanon vorgesehen (z. B. für künftige Change-Detection),
   aber aktuell für InfoSite immer `None`. Entweder `SourceDocument` um ein
   echtes Checksum-Feld ergänzen (z. B. für Re-Sync-Erkennung), oder das
   Feld im Kanon als "optional, providerabhängig" dokumentieren.
   Anmerkung: `GeneratedDocument.content_hash` (Wagtail-Workflow Schritt 2)
   löst dieses Bedürfnis bereits auf der Output-Seite; ein analoges Feld
   für `SourceDocument` bliebe weiterhin offen.

---

## 7. Zusammenfassung

Der Stand hat sich seit der ursprünglichen Fassung dieser Matrix deutlich
verschoben: Wagtail ist nicht mehr nur eine **read-only Spiegelschicht**
über Projekt-Titel/-Status/-Notizen, sondern besitzt inzwischen (Wagtail-
Workflow Schritte 1–6) echte, editierbare Snippet-Modelle für sowohl die
Input-Seite (`SourceDocument`) als auch die Output-Seite
(`GeneratedDocument`, komplett neu eingeführt — vorher gab es dafür gar
keine DB-Repräsentation), inklusive eines aktiven Gruppen-Moderations-
Workflows. Beide Snippet-Modelle bleiben bewusst getrennt (keine
Input/Output-Vermischung); eine gemeinsame `Domain`-Registry (Abschnitt 4a)
verbindet nur die *Übersicht*, nicht den Speicher, der älteren
Jira/OWL/Markdown-Workspace-Pipeline mit der InfoSite-Pipeline.

Die verbleibenden Lücken (Betriebsfelder ohne Wagtail-Sicht, fehlende
Wissensblock-Granularität, totes `checksum`-Feld) sind weiterhin bewusste,
dokumentierte Entscheidungen für die aktuelle Phase, keine übersehenen
Bugs. Sie bilden die Grundlage für die in Abschnitt 6 aufgeführten offenen
Fragen, über die vor einem weiteren Cutover-Schritt entschieden werden
sollte.

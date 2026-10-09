# PDF Batch Import System

> Leading UI/workflow document:
> [Source Workspace and Workflow Concept](source-workspace-and-workflow-concept.md).
> PDF-specific inventory and jobs are views/stages of the shared source workflow.

## Quick Start

```bash
# Import all PDFs from a directory (recursive)
python examples/batch_import_pdfs.py ~/dev_data/ki-knowledge/pdf/books
```

## Overview

The ki-knowledge PDF Batch Import system is designed for processing **large volumes of PDFs** (100MB+) with:

- **Job Tracking**: Each PDF import is tracked as a job with status (pending, processing, done, failed)
- **Progress Updates**: Per-page progress tracking with percentage completion
- **Dashboard Monitoring**: Real-time status display in Django UI
- **API Endpoints**: RESTful API for job management and monitoring
- **Scalable Architecture**: Ready for parallel processing with worker queues

See **`doc/knowledge_blocks.md`** for the related import and storage basics.


## Architecture

### Components

1. **`ki_knowledge/integrations/pdf_batch.py`** – Core job management
   - `PDFBatchProcessor`: Manages job creation, status tracking, and processing
   - `PDFImportJob`: Dataclass representing a single job

2. **`ki_knowledge/api/knowledge_app.py`** – FastAPI endpoints for job management
   - `POST /api/pdf/import/enqueue` – Create a new job
   - `GET /api/pdf/import/jobs` – List all jobs with filtering
   - `GET /api/pdf/import/jobs/{job_id}` – Get single job status
   - `POST /api/pdf/import/jobs/{job_id}/process` – Process a job

3. **`ki_knowledge/django_site/`** – Django integration
   - `services.py`: High-level functions for PDF job management
   - `views.py`: Django views for dashboard display
   - `templates/kicli_django/pdf_import_jobs.html`: Job status dashboard

4. **Database Storage**
   - SQLite database at `~/.ki_cache.sqlite` (or custom location)
   - Table: `pdf_import_jobs` with job metadata and progress

## Usage

### Command Line (Batch Processing)

```bash
# Import all PDFs from a directory
python examples/batch_import_pdfs.py ~/dev_data/ki-knowledge/pdf/default

# Import to a specific domain
python examples/batch_import_pdfs.py ~/dev_data/ki-knowledge/pdf/my-domain "my-domain"
```

### Django Dashboard

1. Navigate to: http://localhost:8000/pdf-import/
2. View all PDF import jobs with status and progress
3. Auto-refreshes every 3 seconds while jobs are processing
4. Filter by domain and status

### PDF Inventory (read-only, active domain)

Before importing, `/data-sources/pdf/inventory/` lists every `*.pdf` (case-insensitive,
recursive, following symlinked directories with a cycle guard) in the active domain's
source and output directories. Source-root overrides are respected; other domains
and files outside domain directories are not scanned.
Scanning starts only via the explicit "scan" button and never imports, OCRs or writes.

- Title comes from PDF metadata (`metadata`); otherwise the file name is shown as a labeled
  `filename` fallback. Scanned books usually have no metadata title, so their real title
  needs OCR/manual review.
- Optional: first text line of page 1 as an unverified hint (only if a text layer exists).
- Encrypted/corrupt/unreadable files, unreadable directories, symlink cycles and
  duplicate physical files are listed explicitly.
- Backend: `ki_knowledge/integrations/pdf_inventory.py` (`scan_configured_pdf_inventory`).

### API Usage (FastAPI)

**Create a job:**
```bash
curl -X POST "http://localhost:8090/api/pdf/import/enqueue?pdf_path=~/dev_data/ki-knowledge/pdf/default/book.pdf&domain=default"
```

**List jobs:**
```bash
curl "http://localhost:8090/api/pdf/import/jobs?domain=default&status=processing"
```

**Get single job status:**
```bash
curl "http://localhost:8090/api/pdf/import/jobs/{job_id}"
```

**Process a job (run immediately):**
```bash
curl -X POST "http://localhost:8090/api/pdf/import/jobs/{job_id}/process"
```

### Python API

```python
from ki_knowledge.integrations.pdf_batch import PDFBatchProcessor

processor = PDFBatchProcessor("~/.ki_cache.sqlite")

# Create a job
job_id = processor.create_job("~/book.pdf", domain="default")

# Check status
job = processor.get_job(job_id)
print(f"Progress: {job.pages_processed}/{job.pages_total}")

# Process the job
result = processor.process_job(job_id)
print(result)  # {"job_id": "...", "status": "done", "pages": 500, ...}
```

## Job Lifecycle

```
pending
   ↓
[enqueue via API/Django/CLI]
   ↓
processing
   ↓ (with page-by-page progress updates)
   ↓
done ✓  or  failed ✗
   ↓
[archived in database]
```

## For 100MB+ PDF Collections

**Recommended workflow:**

1. **Organize**: Place all PDFs in `~/dev_data/ki-knowledge/pdf/{domain}/`
2. **Create jobs**: Use `batch_import_pdfs.py` or API to enqueue all PDFs
3. **Monitor**: Watch dashboard at `/pdf-import/` for progress
4. **Background processing**: Jobs run in background, accessible via API/dashboard
5. **Handle failures**: Failed jobs show error messages; can be reprocessed

**Performance Notes:**

- Each PDF is processed sequentially (pages extracted one-by-one)
- Large PDFs (500+ pages) may take 10-30 seconds to process
- Database queries are fast; no blocking on other operations
- Multiple workers can be added in future for true parallelism

## Buch-Pipeline (Verarbeitungsstand pro Buch)

Übersicht: `/knowledge/pipeline/` (Navigation *Knowledge → Buch-Pipeline*).

Jedes Buch durchläuft feste Stufen. Pro Buch und Stufe steht eine Zeile in
`knowledge.document_stage_status` (Status, Stufen-Version, Kennzahlen als JSON, Fehler):

| Stufe | Quelle des Status |
|---|---|
| `ingest` – Text importiert | Import-Job + Blöcke im KnowledgeStore |
| `quality` – Textqualität | Zeichen/Seite, leere Seiten, wiederkehrende Kopfzeilen → Hinweise *OCR nötig*, *Viele leere Seiten*, *Viele Kopfzeilen* |
| `structure` – Gliederung | `evaluate_structure` (siehe unten) |
| `segments` – Abschnitte | künftige semantische Segmentierung |
| `embeddings` | Anteil der Blöcke mit Eintrag in `knowledge_embeddings` (`embed_blocks`) |
| `terms` – Begriffe | Anteil der Blöcke mit `semantic_record_term_links` |
| `review` – Geprüft | redaktionelle Prüfung pro Buch (später über Wagtail-Workflow) |

Status: `pending`, `partial`, `warning`, `done`, `failed`; `stale` (veraltet) wird
abgeleitet, wenn die gespeicherte Version kleiner als die aktuelle Stufen-Version ist –
so lässt sich nach Verbesserungen gezielt neu verarbeiten.

- Nach jedem PDF-Job aktualisiert der Worker die Stufen dieses Buchs automatisch.
- Neu berechnen für die ganze Domain: Button *Status neu berechnen* oder
  `python manage.py sync_book_pipeline --domain anthro` (liest Quellen/Blöcke nur).
- Ergebnisse künftiger Worker (`structure`, `segments`, `review`) werden beim
  Neuberechnen nicht überschrieben; Worker schreiben sie mit
  `DocumentStageStore.record(source_id, stage, domain=..., status=..., metrics=...)`.

### Gliederung erkennen und prüfen

`python manage.py evaluate_structure --domain corpus [--misses] [--dry-run]`
(`ki_knowledge/integrations/structure_eval.py`, `django_site/book_structure.py`):

- Verfahren `heading` (kurze Überschriften-Absätze: `§. 3.`, `Erster Abschnitt`, römische
  Ziffern, `Einleitung` …), `toc` (gedrucktes Inhaltsverzeichnis parsen und die Titel im
  Text suchen) und `combined` (Standard: TOC + zusätzliche Überschriften).
  Wiederkehrende Zeilen (Kolumnentitel, Copyright-Fußzeilen) werden verworfen.
- Ergebnis: Artefakt `detected_structure` und Stufe `structure`. Ansicht pro Buch:
  `/knowledge/pipeline/structure/<source_id>/` (Klick auf den Gliederungs-Punkt).
- Bücher mit Referenz (TEI-Import, Artefakt `reference_structure`) bekommen Präzision,
  Recall und *Kapitel-Recall* (nur Abschnitte mit Worttitel, ohne reine `§. 12.`).
  Treffer = Titelähnlichkeit ≥ 0,8 auf derselben Seite ± 1; unterschiedliche
  Abschnittsnummern passen nie. Status: `done` ab Kapitel-Recall 0,8 und Präzision 0,7,
  `warning` ab Kapitel-Recall 0,5, sonst `partial`; ohne Referenz `warning` (ungeprüft).
- Zusätzlich wird eine *PDF-ähnliche* Variante bewertet (alle Absätze einer Seite
  zusammengefügt) – so verhielt sich der PDF-Import bis 2026-10-09 (ein Block pro Seite).

Referenzkorpus: Domain `corpus`, 10 DTA-Werke als TEI-P5 unter `corpus/mix/dta/`
(Herkunft/Lizenz: `corpus/QUELLEN-DTA.md`, CC BY-SA 4.0). TEI-Dateien werden am Inhalt
erkannt (Typ `tei`); der Import übernimmt Text seitenweise (ohne Fußnoten, Kolumnentitel,
Bogensignaturen; Silbentrennung zusammengeführt, ſ → s) und speichert die
`div`/`head`-Gliederung als Referenz – Überschriften stehen im Text als normale Absätze,
damit die Erkennung sie selbst finden muss.

Stand 2026-10-08 (`combined`): Präzision Ø 0,67, Kapitel-Recall Ø 0,90; PDF-ähnlich nur
dort gut, wo ein gedrucktes Inhaltsverzeichnis existiert (Goethe, Schelling, Carus).
Für die PDF-Bücher heißt das: Zeilenumbrüche beim PDF-Import erhalten, dann greift auch
die Überschriften-Erkennung (siehe *PDF-Absätze*).

### PDF-Absätze

pypdf liefert den Text zeilenweise. Seit 2026-10-09 baut `extract_text_from_pdf`
(`pdf_ingest.reflow_page_text`) daraus Absätze: Ein Absatz (oder eine Überschrift) endet
an einer Leerzeile oder an einer Zeile, die deutlich kürzer ist als die übliche
Zeilenbreite der Seite (< 75 % des Medians) und nicht auf `-` oder `,` endet;
Silbentrennungen am Zeilenende werden zusammengeführt. Jeder Absatz wird ein eigener
Block mit `metadata.page`. Ein erneuter PDF-Import ersetzt die Blöcke der Quelle
(veraltete Seitenblöcke samt Embeddings werden entfernt).

Probe GA009 (PDF-Lesezeichen als Referenz, 18 Kapitel): Kapitel-Recall 0,00 mit
Seitenblöcken → 0,83 mit Absätzen.

Bestand: `anthro` ist noch seitenweise importiert (Embeddings laufen darauf); Umstellung
per erneutem Import, wenn gewünscht.

### Embeddings (Ollama)

`python manage.py embed_blocks --domain anthro [--batch 32] [--limit N] [--status]`

- Modell `knowledge.embed_model` (Standard `nomic-embed-text`) über
  `providers.ollama.base_url`; Dokumente mit Präfix `search_document:`, Anfragen mit
  `search_query:`; Texte über ~6000 Zeichen werden gekürzt.
- Fortsetzbar: verarbeitet nur Blöcke ohne aktuellen Vektor dieses Modells (fehlend,
  anderes Modell oder Block seit dem Embedding geändert). Fehlerhafte Batches werden
  blockweise wiederholt; einzelne Ausfälle werden gemeldet und übersprungen.
- Aktualisiert die Stufe `embeddings` der Buch-Pipeline unterwegs und am Ende.
- Suche: `/knowledge/search/` (pgvector `<=>`, Kosinus-Ähnlichkeit, aktive Domain).
- Durchsatz hier ~7 Blöcke/s (Ollama teils auf CPU); `anthro` (~125 000 Seitenblöcke)
  braucht damit mehrere Stunden.

## Database Schema

```sql
CREATE TABLE pdf_import_jobs (
    job_id TEXT PRIMARY KEY,
    pdf_path TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT NOT NULL,  -- pending, processing, done, failed
    pages_total INTEGER DEFAULT 0,
    pages_processed INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT
);
```

## Future Enhancements

- [ ] Parallel processing with worker queue (celery/rq)
- [ ] Automatic retry on failure
- [ ] Webhook notifications on job completion
- [ ] Batch processing from web UI (upload + auto-enqueue)
- [ ] S3/cloud storage integration
- [ ] OCR support for scanned PDFs
- [ ] Selective page range import
- [ ] PDF metadata extraction (title, author, creation date)

# PDF Batch Import System

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

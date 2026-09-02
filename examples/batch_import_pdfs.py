#!/usr/bin/env python3
"""Example: Batch import PDFs with job tracking and progress updates."""

import time
from pathlib import Path

from ki_knowledge.django_site.services import (
    create_pdf_import_job,
    pdf_import_jobs,
    process_pdf_import_job,
)


def batch_import_pdfs(pdf_directory: str | Path, domain: str = "default", max_parallel: int = 1):
    """
    Batch import all PDFs from a directory with progress tracking.
    
    Args:
        pdf_directory: Directory containing PDF files
        domain: Knowledge domain to import into
        max_parallel: Number of jobs to process in parallel (future: currently serial)
    
    Example:
        batch_import_pdfs("~/dev_data/ki-knowledge/pdf/default", domain="default")
    """
    pdf_dir = Path(pdf_directory).expanduser()
    if not pdf_dir.exists():
        print(f"❌ Directory not found: {pdf_dir}")
        return
    
    pdf_files = sorted(pdf_dir.glob("**/*.pdf"))
    if not pdf_files:
        print(f"⚠️  No PDF files found in {pdf_dir}")
        return
    
    print(f"📚 Found {len(pdf_files)} PDF files to import")
    print(f"📦 Domain: {domain}")
    print()
    
    # Create jobs for all files
    job_ids = []
    for pdf_file in pdf_files:
        try:
            job_id = create_pdf_import_job(str(pdf_file), domain=domain)
            job_ids.append(job_id)
            print(f"  ✓ Created job: {job_id}")
        except Exception as e:
            print(f"  ✗ Failed to create job for {pdf_file.name}: {e}")
    
    print()
    print(f"🚀 Processing {len(job_ids)} jobs...")
    print()
    
    # Process each job and show progress
    completed = 0
    failed = 0
    
    for i, job_id in enumerate(job_ids, 1):
        job = pdf_import_jobs(domain=domain)
        matching = [j for j in job if j["job_id"] == job_id]
        if not matching:
            continue
        
        job_info = matching[0]
        print(f"[{i}/{len(job_ids)}] Processing: {Path(job_info['pdf_path']).name}")
        print(f"        Job ID: {job_id}")
        print(f"        Pages: {job_info['pages_total']}")
        
        # Process the job
        result = process_pdf_import_job(job_id)
        
        if result["status"] == "done":
            print(f"        ✓ Success: {result['pages']} pages, {result['text_length']} chars")
            completed += 1
        else:
            print(f"        ✗ Failed: {result.get('error', 'Unknown error')}")
            failed += 1
        print()
    
    # Summary
    print("=" * 60)
    print(f"📊 Import Complete")
    print(f"   Total:     {len(job_ids)}")
    print(f"   Completed: {completed} ✓")
    print(f"   Failed:    {failed} ✗")
    print("=" * 60)


if __name__ == "__main__":
    import sys
    
    pdf_dir = sys.argv[1] if len(sys.argv) > 1 else "~/dev_data/ki-knowledge/pdf/default"
    domain = sys.argv[2] if len(sys.argv) > 2 else "default"
    
    batch_import_pdfs(pdf_dir, domain=domain)

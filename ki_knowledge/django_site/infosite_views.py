"""Views for Infosite management interface."""

from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Count, Q
from ki_core.config import Config

from .infosite_models import InfoSiteProject, SourceDocument
from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator
from ki_knowledge.infosite.importer import DocumentImporterRegistry


# ============================================================================
# PROJECT LIST & DASHBOARD
# ============================================================================

@login_required
def infosite_project_list(request: HttpRequest):
    """List all infosite projects with stats."""
    projects = InfoSiteProject.objects.annotate(
        doc_count=Count('documents'),
        imported_count=Count('documents', filter=Q(documents__imported=True)),
    )
    
    # Filter by status if requested
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        projects = projects.filter(sync_status=status_filter)
    
    # Filter by enabled if requested
    show_disabled = request.GET.get('show_disabled', 'false').lower() == 'true'
    if not show_disabled:
        projects = projects.filter(enabled=True)
    
    projects = projects.order_by('-updated_at')
    
    context = {
        'projects': projects,
        'status_filter': status_filter,
        'show_disabled': show_disabled,
        'status_choices': [
            ('all', 'All'),
            ('pending', 'Pending'),
            ('completed', 'Completed'),
            ('syncing', 'Syncing'),
            ('failed', 'Failed'),
        ],
    }
    return render(request, 'infosite/project_list.html', context)


@login_required
def infosite_dashboard(request: HttpRequest):
    """Dashboard for infosite management."""
    projects = InfoSiteProject.objects.all()
    stats = {
        "total_projects": projects.count(),
        "enabled_projects": projects.filter(enabled=True).count(),
        "total_documents": SourceDocument.objects.count(),
        "imported_documents": SourceDocument.objects.filter(imported=True).count(),
    }

    context = {
        "projects": projects,
        "stats": stats,
    }
    return render(request, "infosite/dashboard.html", context)


# ============================================================================
# PROJECT MANAGEMENT (CREATE, EDIT, DELETE)
# ============================================================================

@login_required
@permission_required('django_site.add_infositeproject', raise_exception=True)
def infosite_project_create(request: HttpRequest):
    """Create new infosite project."""
    if request.method == 'POST':
        # Get form data
        title = request.POST.get('title')
        domain = request.POST.get('domain')
        working_title = request.POST.get('working_title')
        description = request.POST.get('description', '')
        auto_discover = request.POST.get('auto_discover', 'on') == 'on'
        
        if not title or not domain:
            messages.error(request, 'Title and domain are required')
            return render(request, 'infosite/project_form.html', {
                'action': 'Create',
                'is_create': True,
            })
        
        project = InfoSiteProject.objects.create(
            title=title,
            domain=domain,
            working_title=working_title or domain,
            description=description,
            auto_discover=auto_discover,
        )
        
        messages.success(request, f'Project "{title}" created')
        return redirect('infosite:project_detail', project_id=project.id)
    
    return render(request, 'infosite/project_form.html', {
        'action': 'Create',
        'is_create': True,
    })


@login_required
def infosite_project_detail(request: HttpRequest, project_id: int):
    """Show project details and management interface."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    documents = project.documents.all().order_by('file_path')
    
    # Filter by status if requested
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        documents = documents.filter(import_status=status_filter)
    
    # Pagination
    page = int(request.GET.get('page', 1))
    per_page = 25
    total = documents.count()
    pages = (total + per_page - 1) // per_page
    start = (page - 1) * per_page
    end = start + per_page
    
    docs_page = documents[start:end]
    
    context = {
        'project': project,
        'documents': docs_page,
        'total_documents': total,
        'current_page': page,
        'total_pages': pages,
        'range': range(1, pages + 1),
        'status_filter': status_filter,
        'status_choices': [
            ('all', 'All'),
            ('discovered', 'Discovered'),
            ('pending', 'Pending'),
            ('imported', 'Imported'),
            ('failed', 'Failed'),
        ],
        'stats': {
            'total': total,
            'discovered': documents.filter(import_status='discovered').count(),
            'pending': documents.filter(import_status='pending').count(),
            'imported': documents.filter(import_status='imported').count(),
            'failed': documents.filter(import_status='failed').count(),
        },
    }
    return render(request, 'infosite/project_detail.html', context)


@login_required
@permission_required('django_site.change_infositeproject', raise_exception=True)
def infosite_project_edit(request: HttpRequest, project_id: int):
    """Edit project settings."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    if request.method == 'POST':
        # Update project
        project.title = request.POST.get('title', project.title)
        project.domain = request.POST.get('domain', project.domain)
        project.working_title = request.POST.get('working_title', project.working_title)
        project.description = request.POST.get('description', '')
        project.auto_discover = request.POST.get('auto_discover', 'off') == 'on'
        project.enabled = request.POST.get('enabled', 'off') == 'on'
        project.save()
        
        messages.success(request, f'Project "{project.title}" updated')
        return redirect('infosite:project_detail', project_id=project.id)
    
    context = {
        'project': project,
        'action': 'Edit',
        'is_create': False,
    }
    return render(request, 'infosite/project_form.html', context)


@login_required
@permission_required('django_site.delete_infositeproject', raise_exception=True)
@require_http_methods(['POST'])
def infosite_project_delete(request: HttpRequest, project_id: int):
    """Delete project and its documents."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    title = project.title
    project.delete()
    messages.success(request, f'Project "{title}" deleted')
    return redirect('infosite:project_list')


# ============================================================================
# DOCUMENT SYNCHRONIZATION & DISCOVERY
# ============================================================================

@login_required
@permission_required('django_site.add_infositeproject', raise_exception=True)
@require_http_methods(['POST'])
def infosite_sync_documents(request: HttpRequest, project_id: int):
    """Manually sync documents for a project."""
    from django.conf import settings
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    if not project.working_title:
        messages.error(request, 'working_title must be configured first')
        return redirect('infosite:project_edit', project_id=project.id)
    
    # Use DocumentSyncService for unified discovery
    from ki_knowledge.services.sync import DocumentSyncService
    
    project.sync_status = 'syncing'
    project.save()
    
    sync_service = DocumentSyncService(settings.KI_CONFIG)
    discovered, updated, error = sync_service.sync_project_documents(project)
    
    if error:
        messages.error(request, f'Sync failed: {error}')
    else:
        if discovered > 0:
            messages.success(
                request,
                f'Sync complete: {discovered} documents ({updated} new)'
            )
        else:
            messages.info(request, 'Sync complete: No new documents found')
    
    return redirect('infosite:project_detail', project_id=project.id)


@login_required
@permission_required("django_site.add_infositeproject")
@require_http_methods(["POST"])
def infosite_discover_documents(request: HttpRequest, project_id: int):
    """Discover documents in source directory using DocumentDiscoveryService."""
    from django.conf import settings
    project = get_object_or_404(InfoSiteProject, id=project_id)

    # Use new DocumentSyncService for unified discovery
    from ki_knowledge.services.sync import DocumentSyncService
    
    sync_service = DocumentSyncService(settings.KI_CONFIG)
    discovered, updated, error = sync_service.sync_project_documents(project)
    
    if error:
        messages.error(request, f"Discovery failed: {error}")
    else:
        messages.success(
            request,
            f"Discovered {discovered} documents ({updated} new)"
        )
    
    return redirect("infosite:project_detail", project_id=project.id)


# ============================================================================
# GENERATION & PREVIEW
# ============================================================================

@login_required
@permission_required("django_site.change_infositeproject")
@require_http_methods(["POST"])
def infosite_generate(request: HttpRequest, project_id: int):
    """Generate infosite for project using InfoSiteGeneratorService."""
    from django.conf import settings
    from ki_knowledge.services.generator import InfoSiteGeneratorService
    
    project = get_object_or_404(InfoSiteProject, id=project_id)

    try:
        # Check prerequisites
        if not project.working_title:
            messages.error(request, "working_title must be configured first")
            return redirect("infosite:project_edit", project_id=project.id)
        
        if project.sync_status != "completed":
            messages.warning(
                request,
                "Please sync documents first before generating"
            )
            return redirect("infosite:project_detail", project_id=project.id)
        
        # Get all synced documents
        docs = project.documents.all()
        if not docs.exists():
            messages.warning(request, "No documents to generate from")
            return redirect("infosite:project_detail", project_id=project.id)
        
        # Convert Django models to FileInfo objects for generator
        from ki_knowledge.services.discovery import FileInfo
        file_infos = [
            FileInfo(
                path=Path(doc.file_path),
                file_type=doc.file_type,
                file_size=doc.file_size,
                modified_at=doc.modified_at,
            )
            for doc in docs
        ]
        
        # Update status to generating
        project.generation_status = "generating"
        project.save(update_fields=["generation_status"])
        
        # Generate using service
        generator = InfoSiteGeneratorService(settings.KI_CONFIG.knowledge_data_root)
        result = generator.generate_infosite(
            domain=project.domain,
            working_title=project.working_title,
            source_docs=file_infos,
        )
        
        if result.success:
            # Update project with generation results
            project.generation_status = "completed"
            project.output_dir = str(result.output_dir)
            project.generated_at = timezone.now()
            project.generation_error = ""
            project.version_count = len(generator.list_versions(project.domain, project.working_title))
            project.save()
            
            messages.success(
                request,
                f"Generated infosite: {result.files_created} files created"
            )
        else:
            # Generation failed
            project.generation_status = "failed"
            project.generation_error = result.message
            project.save(update_fields=["generation_status", "generation_error"])
            
            messages.error(request, f"Generation failed: {result.message}")
        
        return redirect("infosite:project_detail", project_id=project.id)

    except Exception as e:
        # Handle unexpected errors
        project.generation_status = "failed"
        project.generation_error = str(e)
        project.save(update_fields=["generation_status", "generation_error"])
        
        messages.error(request, f"Error generating infosite: {str(e)}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
def infosite_preview(request: HttpRequest, project_id: int):
    """Preview generated infosite."""
    from django.conf import settings
    from ki_knowledge.services.generator import InfoSiteGeneratorService
    
    project = get_object_or_404(InfoSiteProject, id=project_id)

    try:
        if not project.output_dir:
            messages.warning(request, "No output generated yet. Please generate infosite first.")
            return redirect("infosite:project_detail", project_id=project.id)
        
        output_dir = Path(project.output_dir)
        
        if not output_dir.exists():
            messages.warning(request, "Output directory not found")
            return redirect("infosite:project_detail", project_id=project.id)

        # List generated files (excluding _originals)
        files = []
        for md_file in sorted(output_dir.glob("**/*.md")):
            if "_originals" not in md_file.parts:
                rel_path = md_file.relative_to(output_dir)
                files.append(
                    {
                        "path": str(rel_path),
                        "size": md_file.stat().st_size,
                        "mtime": md_file.stat().st_mtime,
                    }
                )

        context = {
            "project": project,
            "output_dir": str(output_dir),
            "files": files,
        }
        return render(request, "infosite/preview.html", context)

    except Exception as e:
        messages.error(request, f"Error loading preview: {e}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
def infosite_download(request: HttpRequest, project_id: int):
    """Download generated infosite as ZIP."""
    import zipfile
    import io
    from django.http import FileResponse
    
    project = get_object_or_404(InfoSiteProject, id=project_id)

    try:
        if not project.output_dir:
            messages.error(request, "No output generated yet")
            return redirect("infosite:project_detail", project_id=project.id)
        
        output_dir = Path(project.output_dir)
        
        if not output_dir.exists():
            messages.error(request, "Output directory not found")
            return redirect("infosite:project_detail", project_id=project.id)

        # Create ZIP file in memory
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Add all files except _originals
            for file_path in output_dir.rglob("*"):
                if file_path.is_file() and "_originals" not in file_path.parts:
                    arcname = file_path.relative_to(output_dir)
                    zip_file.write(file_path, arcname)

        zip_buffer.seek(0)
        
        # Return as downloadable file
        filename = f"{project.domain}_{project.working_title}_infosite.zip"
        response = FileResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        messages.error(request, f"Error creating download: {e}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
def infosite_versions(request: HttpRequest, project_id: int):
    """List available versions of the infosite."""
    from django.conf import settings
    from ki_knowledge.services.generator import InfoSiteGeneratorService
    
    project = get_object_or_404(InfoSiteProject, id=project_id)

    try:
        if not project.output_dir:
            versions = []
        else:
            generator = InfoSiteGeneratorService(settings.KI_CONFIG)
            version_names = generator.list_versions(project.domain, project.working_title)
            
            # Get metadata for each version
            versions = []
            for version_name in version_names:
                version_dir = Path(project.output_dir) / "_originals" / version_name
                if version_dir.exists():
                    # Count files
                    file_count = len(list(version_dir.rglob("*")))
                    # Get size
                    total_size = sum(f.stat().st_size for f in version_dir.rglob("*") if f.is_file())
                    
                    # Get creation time from directory
                    mtime = version_dir.stat().st_mtime
                    from datetime import datetime
                    created_at = datetime.fromtimestamp(mtime)
                    
                    versions.append({
                        "name": version_name,
                        "file_count": file_count,
                        "size_bytes": total_size,
                        "size_mb": round(total_size / 1024 / 1024, 2),
                        "created_at": created_at,
                    })

        context = {
            "project": project,
            "versions": sorted(versions, key=lambda v: v["created_at"], reverse=True),
        }
        return render(request, "infosite/versions.html", context)

    except Exception as e:
        messages.error(request, f"Error loading versions: {e}")
        return redirect("infosite:project_detail", project_id=project.id)


# ============================================================================
# IMPORT CONTROL
# ============================================================================

@login_required
def infosite_import_control(request: HttpRequest, project_id: int):
    """Import control panel for documents with import status tracking."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    # Get all discovered and imported documents
    discovered = project.documents.filter(import_status="discovered").count()
    pending = project.documents.filter(import_status="pending").count()
    imported = project.documents.filter(import_status="imported").count()
    failed = project.documents.filter(import_status="failed").count()
    
    # Get documents that are NOT yet marked as imported
    importable_docs = project.documents.filter(
        import_status__in=["discovered", "pending", "failed"]
    ).order_by("file_path")
    
    context = {
        "project": project,
        "documents": project.documents.all(),
        "importable_docs": importable_docs,
        "stats": {
            "discovered": discovered,
            "pending": pending,
            "imported": imported,
            "failed": failed,
            "total": project.documents.count(),
        },
    }
    return render(request, "infosite/import_control.html", context)


@login_required
@require_http_methods(["POST"])
def infosite_import_selected(request: HttpRequest, project_id: int):
    """Import selected documents by marking them as imported."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    # Get selected document IDs from POST
    selected_doc_ids = request.POST.getlist("selected_files[]")
    
    if not selected_doc_ids:
        messages.warning(request, "No documents selected")
        return redirect("infosite:import_control", project_id=project.id)
    
    # Update selected documents
    imported_count = 0
    try:
        # Convert strings to integers and update documents
        for doc_id in selected_doc_ids:
            try:
                doc = SourceDocument.objects.get(id=int(doc_id), project=project)
                if doc.import_status != "imported":
                    doc.import_status = "imported"
                    doc.imported = True
                    doc.imported_at = timezone.now()
                    doc.save()
                    imported_count += 1
            except (ValueError, SourceDocument.DoesNotExist):
                continue
        
        if imported_count > 0:
            messages.success(request, f"✅ Marked {imported_count} document(s) as imported")
        else:
            messages.info(request, "No documents needed updating")
            
    except Exception as e:
        messages.error(request, f"Error updating documents: {str(e)}")
    
    return redirect("infosite:import_control", project_id=project.id)


# ============================================================================
# AI REFINEMENT
# ============================================================================

@login_required
def infosite_ai_refine(request: HttpRequest, project_id: int):
    """AI refinement control for markdown files."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    try:
        config = Config.from_yaml()
        infosite_config = InfoSiteConfig(
            enabled=True,
            title=project.title,
            domain=project.domain,
            output_base_dir=config.infosite_output_base_dir,
        )
        
        output_dir = infosite_config.get_output_dir()
        
        # List markdown files available for refinement
        markdown_files = []
        if output_dir.exists():
            for md_file in sorted(output_dir.glob("**/*.md")):
                if "_originals" not in md_file.parts:
                    rel_path = md_file.relative_to(output_dir)
                    with open(md_file, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    markdown_files.append({
                        "path": str(rel_path),
                        "file_path": str(md_file),
                        "size": md_file.stat().st_size,
                        "lines": len(content.split("\n")),
                        "preview": content[:200] + "..." if len(content) > 200 else content,
                    })
        
        context = {
            "project": project,
            "markdown_files": markdown_files,
            "refinement_modes": [
                {"id": "improve", "label": "Improve Content", "description": "Enhance text quality and clarity"},
                {"id": "structure", "label": "Restructure", "description": "Better organization and hierarchy"},
                {"id": "summarize", "label": "Summarize", "description": "Create concise summaries"},
                {"id": "all", "label": "All Refinements", "description": "Apply all improvements"},
            ],
        }
        return render(request, "infosite/ai_refine.html", context)
    
    except Exception as e:
        messages.error(request, f"Error loading refinement interface: {e}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
@require_http_methods(["POST"])
def infosite_ai_refine_apply(request: HttpRequest, project_id: int):
    """Apply AI refinements to markdown files."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    # Get parameters
    selected_files = request.POST.getlist("selected_files[]")
    refinement_mode = request.POST.get("refinement_mode", "all")
    
    if not selected_files:
        messages.warning(request, "No files selected")
        return redirect("infosite:ai_refine", project_id=project.id)
    
    try:
        from ki_core.client import AIClient
        from ki_core.config import Config as CoreConfig
        
        core_config = CoreConfig.from_yaml()
        client = AIClient(core_config)
        
        refined_count = 0
        for file_path in selected_files:
            # Load markdown file
            md_path = Path(file_path)
            if not md_path.exists():
                continue
            
            with open(md_path, "r", encoding="utf-8") as f:
                original_content = f.read()
            
            # Prepare prompt based on refinement mode
            if refinement_mode == "improve":
                prompt = f"Improve the following markdown content for clarity and quality:\n\n{original_content}"
            elif refinement_mode == "structure":
                prompt = f"Restructure and reorganize the following markdown for better hierarchy and flow:\n\n{original_content}"
            elif refinement_mode == "summarize":
                prompt = f"Create a concise summary of the following markdown content:\n\n{original_content}"
            else:  # all
                prompt = f"Improve, restructure, and enhance the following markdown content:\n\n{original_content}"
            
            # Call AI service
            response = client.complete(prompt)
            refined_content = response.get("text", original_content)
            
            # Save refined version
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(refined_content)
            
            refined_count += 1
        
        messages.success(request, f"Refined {refined_count} file(s) with AI")
        return redirect("infosite:ai_refine", project_id=project.id)
    
    except Exception as e:
        messages.error(request, f"Error during AI refinement: {e}")
        return redirect("infosite:ai_refine", project_id=project.id)


# ============================================================================
# DOCUMENT PREVIEW
# ============================================================================

@login_required
def infosite_document_preview(request: HttpRequest, project_id: int):
    """Document preview browser with flying preview."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    try:
        # Try to get config, but use sensible defaults
        try:
            config = Config.from_yaml()
            base_dir = config.infosite_output_base_dir or "data_out"
        except:
            base_dir = "data_out"
        
        infosite_config = InfoSiteConfig(
            enabled=True,
            title=project.title,
            domain=project.domain,
            output_base_dir=base_dir,
        )
        
        output_dir = infosite_config.get_output_dir()
        
        # Collect all documents from synced SourceDocuments
        documents = []
        for doc in project.documents.filter(imported=True).order_by("file_path"):
            documents.append({
                "id": str(doc.id),
                "name": doc.file_path.split("/")[-1] if "/" in doc.file_path else doc.file_path,
                "path": doc.file_path,
                "type": "pdf" if doc.file_path.endswith(".pdf") else "markdown",
                "size": doc.file_size or 0,
                "size_display": doc.file_size_display,
                "url": f"/api/document/{project_id}/{doc.id}/",
            })
        
        if not documents and output_dir.exists():
            # Fallback: scan output directory
            for file_path in sorted(output_dir.rglob("*")):
                if file_path.is_file() and "_originals" not in file_path.parts:
                    file_type = _get_file_type(file_path)
                    rel_path = file_path.relative_to(output_dir)
                    
                    documents.append({
                        "id": str(rel_path),
                        "name": file_path.name,
                        "path": str(rel_path),
                        "type": file_type,
                        "size": file_path.stat().st_size,
                        "size_display": _format_file_size(file_path.stat().st_size),
                        "url": f"/api/document/{project_id}/{str(rel_path)}/",
                    })
        
        # Convert to JSON for JavaScript
        import json
        documents_json = json.dumps(documents)
        
        context = {
            "project": project,
            "document_count": len(documents),
            "documents": documents,
            "documents_json": documents_json,
        }
        return render(request, "document_preview.html", context)
        
    except Exception as e:
        messages.error(request, f"Error loading documents: {str(e)}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
def infosite_document_preview_api(request: HttpRequest, project_id: int, doc_path: str):
    """API endpoint to get document preview content."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    try:
        config = Config.from_yaml()
        infosite_config = InfoSiteConfig(
            enabled=True,
            title=project.title,
            domain=project.domain,
            output_base_dir=config.infosite_output_base_dir,
        )
        
        output_dir = infosite_config.get_output_dir()
        file_path = output_dir / doc_path
        
        # Security: prevent directory traversal
        if not file_path.exists() or not file_path.is_file():
            return JsonResponse({"error": "File not found"}, status=404)
        
        if "_originals" in file_path.parts or not file_path.is_relative_to(output_dir):
            return JsonResponse({"error": "Access denied"}, status=403)
        
        file_type = _get_file_type(file_path)
        
        if file_type in ["markdown", "text"]:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            
            return JsonResponse({
                "id": str(doc_path),
                "name": file_path.name,
                "type": file_type,
                "content": content,
                "size": file_path.stat().st_size,
                "lines": len(content.split("\n")),
            })
        
        elif file_type == "pdf":
            # For PDF, return base64 encoded or a download URL
            return JsonResponse({
                "id": str(doc_path),
                "name": file_path.name,
                "type": "pdf",
                "size": file_path.stat().st_size,
                "url": f"/media/{project_id}/{doc_path}",
            })
        
        else:
            return JsonResponse({"error": "Unsupported file type"}, status=400)
    
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# ============================================================================
# UTILITIES
# ============================================================================

def _get_file_type(file_path: Path) -> str:
    """Get file type from extension."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    elif suffix in {".md", ".markdown"}:
        return "markdown"
    elif suffix == ".txt":
        return "text"
    return "other"


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ============================================================================
# KNOWLEDGE BLOCK EXTRACTION
# ============================================================================

@login_required
def infosite_extract_knowledge_blocks(request: HttpRequest, project_id: int):
    """Extract knowledge blocks from imported documents and display them."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    from ki_knowledge.services.block_extractor import InfoSiteBlockExtractor
    
    try:
        # Extract blocks
        extractor = InfoSiteBlockExtractor(project)
        blocks_by_file = extractor.extract_from_directory()
        stats = extractor.get_statistics()
        
        context = {
            "project": project,
            "stats": stats,
            "blocks_by_file": blocks_by_file,
        }
        
        return render(request, "infosite/knowledge_blocks.html", context)
        
    except Exception as e:
        messages.error(request, f"Error extracting blocks: {str(e)}")
        return redirect("infosite:project_detail", project_id=project.id)


@login_required
def infosite_publish_knowledge_blocks(request: HttpRequest, project_id: int):
    """Publish extracted blocks to knowledge store.

    This view no longer performs extraction/storage logic inline. It only
    enqueues an idempotent pipeline job (ki_knowledge.integrations.knowledge_pipeline_jobs)
    and delegates execution to ki_knowledge.services.pipeline_runner, which is the
    same code path used by the `run_knowledge_extraction` management command
    and (in the future) an async worker. This decouples the pipeline from the
    Django request/response cycle.
    """
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=400)
    
    from ki_knowledge.services.pipeline_runner import enqueue_and_run
    
    try:
        results = enqueue_and_run(project)
        
        messages.success(
            request,
            f"Published {results['blocks_stored']} blocks from {results['files_processed']} files "
            f"to knowledge store '{results['source_id']}' (job {results['job_id']})",
        )
        
        return JsonResponse(results)
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


@login_required
@require_http_methods(["GET"])
def infosite_knowledge_extraction_jobs(request: HttpRequest, project_id: int):
    """List extraction job history for a project (read-only status view)."""
    project = get_object_or_404(InfoSiteProject, id=project_id)

    from ki_knowledge.services.pipeline_runner import get_job_store

    store = get_job_store()
    jobs = store.list_jobs(project_id=project.id, limit=50)

    return render(
        request,
        "infosite/knowledge_extraction_jobs.html",
        {"project": project, "jobs": jobs},
    )


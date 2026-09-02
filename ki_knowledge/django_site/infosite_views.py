"""Views for Infosite management interface."""

from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from ki_core.config import Config

from .infosite_models import InfoSiteProject, SourceDocument
from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator
from ki_knowledge.infosite.importer import DocumentImporterRegistry



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


@login_required
def infosite_project_detail(request: HttpRequest, project_id: int):
    """Show project details and management interface."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    documents = project.documents.all()

    context = {
        "project": project,
        "documents": documents,
        "stats": {
            "total": documents.count(),
            "imported": documents.filter(imported=True).count(),
            "pending": documents.filter(imported=False).count(),
        },
    }
    return render(request, "infosite/project_detail.html", context)


@login_required
@permission_required("django_site.add_infositeproject")
@require_http_methods(["POST"])
def infosite_discover_documents(request: HttpRequest, project_id: int):
    """Discover documents in source directory."""
    project = get_object_or_404(InfoSiteProject, id=project_id)

    if not project.source_directory:
        messages.error(request, "Source directory not configured")
        return redirect("infosite_project_detail", project_id=project.id)

    source_path = Path(project.source_directory)
    if not source_path.exists():
        messages.error(request, f"Source directory not found: {source_path}")
        return redirect("infosite_project_detail", project_id=project.id)

    # Discover documents
    registry = DocumentImporterRegistry()
    found = 0

    for file_path in source_path.rglob("*"):
        if file_path.is_file():
            if registry.find_importer(file_path):
                rel_path = str(file_path.relative_to(source_path))
                doc, created = SourceDocument.objects.get_or_create(
                    project=project,
                    file_path=rel_path,
                    defaults={
                        "title": file_path.stem,
                        "file_type": _get_file_type(file_path),
                    },
                )
                if created:
                    found += 1

    messages.success(request, f"Discovered {found} document(s)")
    return redirect("infosite_project_detail", project_id=project.id)


@login_required
@permission_required("django_site.change_infositeproject")
@require_http_methods(["POST"])
def infosite_generate(request: HttpRequest, project_id: int):
    """Generate infosite for project."""
    project = get_object_or_404(InfoSiteProject, id=project_id)

    try:
        # Load configuration
        config = Config.from_yaml()

        # Get output directory
        if not config.infosite_output_base_dir:
            messages.error(request, "infosite_output_base_dir not configured in ki.yaml")
            return redirect("infosite_project_detail", project_id=project.id)

        # Create infosite config
        infosite_config = InfoSiteConfig(
            enabled=True,
            title=project.title,
            domain=project.domain,
            output_base_dir=config.infosite_output_base_dir,
        )

        # Create generator
        generator = InfoSiteGenerator(infosite_config)

        # Generate from source documents if available
        if project.source_directory:
            source_path = Path(project.source_directory)
            if source_path.exists():
                output_dir = generator.generate_from_documents(source_path)
            else:
                messages.warning(request, f"Source directory not found: {source_path}")
                output_dir = generator.generate(
                    generator.create_default_pages(project.title)
                )
        else:
            output_dir = generator.generate(generator.create_default_pages(project.title))

        # Update project
        from django.utils import timezone

        project.last_generated = timezone.now()
        project.save()

        # Mark documents as imported
        project.documents.all().update(imported=True, imported_at=timezone.now())

        messages.success(request, f"Infosite generated: {output_dir}")
        return redirect("infosite_project_detail", project_id=project.id)

    except Exception as e:
        messages.error(request, f"Error generating infosite: {e}")
        return redirect("infosite_project_detail", project_id=project.id)


@login_required
def infosite_preview(request: HttpRequest, project_id: int):
    """Preview generated infosite."""
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

        # List generated files
        files = []
        if output_dir.exists():
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
        return redirect("infosite_project_detail", project_id=project.id)


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


@login_required
def infosite_import_control(request: HttpRequest, project_id: int):
    """Import control panel for documents."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    # Get all potential documents from source directory
    available_files = []
    if project.source_directory:
        source_path = Path(project.source_directory)
        if source_path.exists():
            registry = DocumentImporterRegistry()
            for file_path in sorted(source_path.rglob("*")):
                if file_path.is_file() and registry.find_importer(file_path):
                    rel_path = str(file_path.relative_to(source_path))
                    doc = project.documents.filter(file_path=rel_path).first()
                    available_files.append({
                        "path": rel_path,
                        "file_type": _get_file_type(file_path),
                        "size": file_path.stat().st_size,
                        "imported": doc.imported if doc else False,
                        "doc_id": doc.id if doc else None,
                    })
    
    context = {
        "project": project,
        "available_files": available_files,
        "documents": project.documents.all(),
    }
    return render(request, "infosite/import_control.html", context)


@login_required
@require_http_methods(["POST"])
def infosite_import_selected(request: HttpRequest, project_id: int):
    """Import selected documents."""
    project = get_object_or_404(InfoSiteProject, id=project_id)
    
    # Get selected files from POST
    selected_files = request.POST.getlist("selected_files[]")
    
    if not selected_files:
        messages.warning(request, "No files selected")
        return redirect("infosite_import_control", project_id=project.id)
    
    # Create/update documents
    source_path = Path(project.source_directory) if project.source_directory else None
    imported_count = 0
    
    for file_path in selected_files:
        if not source_path:
            continue
            
        full_path = source_path / file_path
        if not full_path.exists():
            continue
        
        doc, created = SourceDocument.objects.get_or_create(
            project=project,
            file_path=file_path,
            defaults={
                "title": full_path.stem,
                "file_type": _get_file_type(full_path),
            }
        )
        
        if not doc.imported:
            doc.imported = True
            doc.imported_at = timezone.now()
            doc.save()
            imported_count += 1
    
    messages.success(request, f"Imported {imported_count} document(s)")
    return redirect("infosite_import_control", project_id=project.id)


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
        return redirect("infosite_project_detail", project_id=project.id)


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
        return redirect("infosite_ai_refine", project_id=project.id)
    
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
        return redirect("infosite_ai_refine", project_id=project.id)
    
    except Exception as e:
        messages.error(request, f"Error during AI refinement: {e}")
        return redirect("infosite_ai_refine", project_id=project.id)


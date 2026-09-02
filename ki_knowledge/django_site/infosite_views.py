"""Views for Infosite management interface."""

from pathlib import Path
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
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

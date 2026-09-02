"""Document importers for infosite generation from various file formats."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader


class DocumentImporter(ABC):
    """Base class for document importers."""

    @abstractmethod
    def import_file(self, file_path: Path) -> str:
        """Import content from a file.

        Args:
            file_path: Path to the file

        Returns:
            Extracted content as string
        """
        pass

    @abstractmethod
    def supports(self, file_path: Path) -> bool:
        """Check if this importer supports the file type.

        Args:
            file_path: Path to check

        Returns:
            True if the importer can handle this file
        """
        pass


class MarkdownImporter(DocumentImporter):
    """Import markdown files."""

    def supports(self, file_path: Path) -> bool:
        """Support .md files."""
        return file_path.suffix.lower() in {".md", ".markdown"}

    def import_file(self, file_path: Path) -> str:
        """Read markdown file."""
        return file_path.read_text(encoding="utf-8")


class TextImporter(DocumentImporter):
    """Import plain text files."""

    def supports(self, file_path: Path) -> bool:
        """Support .txt files."""
        return file_path.suffix.lower() == ".txt"

    def import_file(self, file_path: Path) -> str:
        """Read text file."""
        return file_path.read_text(encoding="utf-8")


class PDFImporter(DocumentImporter):
    """Import PDF files."""

    def supports(self, file_path: Path) -> bool:
        """Support .pdf files."""
        return file_path.suffix.lower() == ".pdf"

    def import_file(self, file_path: Path) -> str:
        """Extract text from PDF."""
        try:
            pdf = PdfReader(str(file_path))
            text_parts = []
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text.strip():
                    text_parts.append(f"# Page {page_num}\n\n{text}")
            return "\n\n---\n\n".join(text_parts)
        except Exception as e:
            return f"Error reading PDF: {e}"


class DocumentImporterRegistry:
    """Registry of available document importers."""

    def __init__(self):
        """Initialize with default importers."""
        self.importers: List[DocumentImporter] = [
            MarkdownImporter(),
            PDFImporter(),
            TextImporter(),
        ]

    def register(self, importer: DocumentImporter) -> None:
        """Register a new importer."""
        self.importers.insert(0, importer)

    def find_importer(self, file_path: Path) -> Optional[DocumentImporter]:
        """Find an importer for the given file.

        Args:
            file_path: Path to the file

        Returns:
            Importer or None if no suitable importer found
        """
        for importer in self.importers:
            if importer.supports(file_path):
                return importer
        return None

    def import_file(self, file_path: Path) -> Optional[str]:
        """Import a file using a suitable importer.

        Args:
            file_path: Path to the file

        Returns:
            Extracted content or None if no importer found
        """
        importer = self.find_importer(file_path)
        if importer is None:
            return None
        return importer.import_file(file_path)

    def import_directory(self, dir_path: Path) -> dict[str, str]:
        """Import all files from a directory.

        Args:
            dir_path: Path to the directory

        Returns:
            Dictionary mapping file paths to extracted content
        """
        results = {}
        for file_path in dir_path.rglob("*"):
            if file_path.is_file():
                content = self.import_file(file_path)
                if content is not None:
                    rel_path = str(file_path.relative_to(dir_path))
                    results[rel_path] = content
        return results


# Global registry instance
_default_registry = DocumentImporterRegistry()


def import_file(file_path: Path) -> Optional[str]:
    """Import a file using the default registry.

    Args:
        file_path: Path to the file

    Returns:
        Extracted content or None
    """
    return _default_registry.import_file(file_path)


def import_directory(dir_path: Path) -> dict[str, str]:
    """Import all files from a directory using the default registry.

    Args:
        dir_path: Path to the directory

    Returns:
        Dictionary mapping file paths to extracted content
    """
    return _default_registry.import_directory(dir_path)


def get_registry() -> DocumentImporterRegistry:
    """Get the default importer registry."""
    return _default_registry

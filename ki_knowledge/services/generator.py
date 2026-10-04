"""
InfoSite Generator Service

Generates structured markdown output from discovered documents.
Creates versioning baseline and metadata for tracking.
"""

import os
import re
import shutil
from html import escape
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import markdown
import yaml

from ki_knowledge.data_layout import MARKDOWN, DataLayout

from .discovery import DocumentDiscoveryService, FileInfo


@dataclass
class GenerationResult:
    """Result of generation operation"""
    success: bool
    message: str
    output_dir: Optional[Path] = None
    files_created: int = 0
    version: str = "v1-original"


class InfoSiteGeneratorService:
    """
    Generates structured markdown output and versioning baseline.
    
    Output structure:
        data_out/<domain>/<working_title>/
        ├── index.md
        ├── overview.md
        ├── metadata.yml
        ├── _originals/
        │   └── v1-original/
        │       ├── topic1/
        │       ├── topic2/
        │       └── ...
        └── topics/
            ├── topic1.md
            ├── topic2.md
            └── ...
    """

    def __init__(self, data_root_or_config):
        """
        Initialize generator service.
        
        Args:
            data_root_or_config: Either a Path/str to data root or a Config object
        """
        from ki_knowledge.app_config import AppConfig as Config
        
        if isinstance(data_root_or_config, (str, Path)):
            self.data_root = Path(data_root_or_config)
            # Create a minimal config-like object
            class MinimalConfig:
                def __init__(self, root):
                    self.knowledge_data_root = str(root)
            self.config = MinimalConfig(self.data_root)
        else:
            # Assume it's a Config object
            self.config = data_root_or_config
            self.data_root = Path(self.config.knowledge_data_root)
        
        self.discovery = DocumentDiscoveryService(self.config)
        self.layout = DataLayout(self.data_root)

    def generate_infosite(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        site_structure: object | None = None,
        mapping_rules: list[dict] | None = None,
    ) -> GenerationResult:
        """
        Generate complete infosite output from discovered documents.
        
        Args:
            domain: Domain name (e.g., 'anthro')
            working_title: Project working title (e.g., 'sstk')
            source_docs: List of discovered source documents
            site_structure: Optional project-defined ordering for generated sections.
        
        Returns:
            GenerationResult with success status and output directory
        """
        try:
            # Create output directory structure
            output_dir = self._create_output_structure(domain, working_title)
            
            # Copy source documents to versioning baseline
            originals_dir = self._copy_originals(
                domain, working_title, source_docs, output_dir
            )

            self._copy_hierarchical_output_tree(
                domain,
                working_title,
                source_docs,
                output_dir,
                site_structure=site_structure,
            )
            
            # Generate index and overview files
            self._generate_index(
                domain,
                working_title,
                source_docs,
                output_dir,
                site_structure=site_structure,
                mapping_rules=mapping_rules,
            )
            self._generate_overview(
                domain,
                working_title,
                source_docs,
                output_dir,
                site_structure=site_structure,
                mapping_rules=mapping_rules,
            )

            # Create metadata
            metadata = self._generate_metadata(
                domain,
                working_title,
                source_docs,
                output_dir,
                mapping_rules=mapping_rules,
            )
            self._write_metadata(output_dir, metadata)
            
            return GenerationResult(
                success=True,
                message=f"Generated infosite {domain}/{working_title} ({len(source_docs)} documents)",
                output_dir=output_dir,
                files_created=len(source_docs) + 3,  # docs + index + overview + metadata
                version="v1-original",
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                message=f"Generation failed: {str(e)}",
            )

    def generate_admin_metadata_pages(self, output_dir: Path | str) -> GenerationResult:
        """Generate the internal admin metadata pages (index, overview, metadata) as HTML."""
        try:
            base_dir = Path(output_dir)
            admin_dir = base_dir / "html" / "admin"
            admin_dir.mkdir(parents=True, exist_ok=True)

            generated: list[Path] = []
            for md_name in ("index.md", "overview.md"):
                md_path = base_dir / md_name
                if not md_path.exists():
                    continue
                source = md_path.read_text(encoding="utf-8")
                title = self._extract_title(source, md_path.stem)
                body_html = markdown.markdown(
                    source,
                    extensions=["extra", "toc", "sane_lists", "tables", "fenced_code", "attr_list"],
                )
                out_path = admin_dir / f"{md_path.stem}.html"
                out_path.write_text(
                    self._render_html_page(title, body_html, []),
                    encoding="utf-8",
                )
                generated.append(out_path)

            metadata_path = base_dir / "metadata.yml"
            if metadata_path.exists():
                metadata = yaml.safe_load(metadata_path.read_text(encoding="utf-8")) or {}
                body_html = self._render_metadata_html(metadata)
                out_path = admin_dir / "metadata.html"
                out_path.write_text(self._render_html_page("Metadata", body_html, []), encoding="utf-8")
                generated.append(out_path)

            return GenerationResult(
                success=True,
                message=f"Generated admin metadata pages in {admin_dir}",
                output_dir=admin_dir,
                files_created=len(generated),
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            return GenerationResult(
                success=False,
                message=f"Admin metadata page generation failed: {exc}",
            )

    def generate_html_site(self, output_dir: Path | str) -> GenerationResult:
        """Create a browsable static HTML website alongside the markdown output."""
        try:
            site_dir = Path(output_dir) / "html"
            site_dir.mkdir(parents=True, exist_ok=True)

            md_files = sorted(
                [p for p in Path(output_dir).glob("**/*.md") if "_originals" not in p.parts and p.name != "metadata.yml"],
                key=lambda p: str(p.relative_to(output_dir)),
            )

            links: list[tuple[str, str]] = []
            html_pages: list[tuple[Path, str, str, list[tuple[str, str]]]] = []

            for md_file in md_files:
                rel_path = md_file.relative_to(output_dir)
                html_path = site_dir / rel_path.with_suffix(".html")
                html_path.parent.mkdir(parents=True, exist_ok=True)

                source = md_file.read_text(encoding="utf-8")
                title = self._extract_title(source, rel_path.stem)
                markdown_page = markdown.Markdown(
                    extensions=["extra", "toc", "sane_lists", "tables", "fenced_code", "attr_list"],
                )
                body_html = markdown_page.convert(source)
                page_sections = self._page_section_links(markdown_page.toc_tokens)

                href = rel_path.with_suffix(".html").as_posix()
                links.append((title, href))
                html_pages.append((html_path, title, body_html, page_sections))

            sorted_links = sorted(links, key=lambda item: item[0].casefold())

            for html_path, title, body_html, page_sections in html_pages:
                rel_html_path = html_path.relative_to(site_dir)
                nav_links = []
                for page_label, page_href in sorted_links:
                    page_target = Path(page_href)
                    rel_href = os.path.relpath(page_target, start=rel_html_path.parent)
                    nav_links.append((page_label, rel_href.replace('\\', '/')))
                html = self._render_html_page(title, body_html, nav_links, page_sections)
                html_path.write_text(html, encoding="utf-8")

            index_html = self._render_html_index(
                sorted_links,
                title=f"{Path(output_dir).name} - HTML",
            )
            (site_dir / "index.html").write_text(index_html, encoding="utf-8")

            return GenerationResult(
                success=True,
                message=f"Generated static HTML website at {site_dir}",
                output_dir=site_dir,
                files_created=len(md_files) + 1,
            )
        except Exception as exc:  # pragma: no cover - defensive guard
            return GenerationResult(
                success=False,
                message=f"HTML generation failed: {exc}",
            )

    @staticmethod
    def _extract_title(markdown_text: str, fallback: str) -> str:
        match = re.search(r"^#\s+(.+)$", markdown_text, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return fallback.replace("-", " ").title()

    @staticmethod
    def _page_section_links(toc_tokens: list[dict]) -> list[tuple[str, str]]:
        """Return links for PDF-style Page N headings in the current document."""
        sections: list[tuple[str, str]] = []

        def visit(items: list[dict]) -> None:
            for item in items:
                title = str(item.get("name", "")).strip()
                page_match = re.search(r"((?:page|seite)\s+\d+)$", title, re.IGNORECASE)
                if page_match:
                    sections.append((page_match.group(1), str(item.get("id", ""))))
                visit(item.get("children", []))

        visit(toc_tokens)
        return sections

    @staticmethod
    def _render_html_page(
        title: str,
        body_html: str,
        nav_links: list[tuple[str, str]],
        page_sections: list[tuple[str, str]] | None = None,
    ) -> str:
        page_sections = page_sections or []
        nav_html = "\n".join(
            f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>'
            for label, href in nav_links
        )
        section_nav_html = "\n".join(
            f'<li><a class="page-section-link" href="#{escape(anchor, quote=True)}">{escape(label)}</a></li>'
            for label, anchor in page_sections
            if anchor
        )
        return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #020617;
      --panel: rgba(15, 23, 42, 0.96);
      --panel-strong: rgba(17, 24, 39, 0.98);
      --panel-soft: rgba(30, 41, 59, 0.55);
      --border: rgba(148, 163, 184, 0.22);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #7dd3fc;
      --accent-strong: #60a5fa;
      --shadow: 0 20px 45px rgba(2, 6, 23, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.7;
      color: var(--text);
      background:
        radial-gradient(circle at top, rgba(96, 165, 250, 0.14), transparent 28%),
        linear-gradient(180deg, #020617 0%, #0f172a 100%);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{
      max-width: 1440px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .hero {{
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 20px;
      padding: 22px 24px;
      border: 1px solid rgba(125, 211, 252, 0.16);
      border-radius: 18px;
      background:
        radial-gradient(circle at top right, rgba(96, 165, 250, 0.18), transparent 28%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(2, 6, 23, 0.98));
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }}
    .hero h1 {{ margin: 0; font-size: clamp(2rem, 4vw, 2.8rem); line-height: 1.05; }}
    .hero p {{ margin: 8px 0 0; color: var(--muted); }}
    .surface {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .content {{ padding: 20px 24px 26px; }}
    .content h1:first-child {{ margin-top: 0; }}
    .page-layout {{
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      align-items: start;
      gap: 18px;
    }}
    .sidebar {{
      position: sticky;
      top: 16px;
      max-height: calc(100vh - 32px);
      overflow-y: auto;
      padding: 16px;
    }}
    .sidebar h2 {{
      margin: 0 0 8px;
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .sidebar ul {{
      list-style: none;
      padding: 0;
      margin: 0 0 20px;
    }}
    .sidebar li a {{
      display: block;
      padding: 5px 8px;
      border-radius: 7px;
      color: var(--muted);
      font-size: 0.88rem;
      transition: color 0.2s ease;
    }}
    .sidebar li a:hover {{
      background: var(--panel-soft);
      color: var(--accent);
    }}
    .sidebar li a.page-section-link {{ padding-left: 18px; font-size: 0.82rem; }}
    pre {{ background: #020617; padding: 1rem; overflow-x: auto; border-radius: 12px; border: 1px solid var(--border); }}
    code {{ background: rgba(30, 41, 59, 0.82); padding: 0.12rem 0.35rem; border-radius: 6px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid var(--border); padding: 0.65rem; text-align: left; }}
    th {{ background: rgba(30, 41, 59, 0.6); }}
    blockquote {{
      margin: 1.25rem 0;
      padding: 0.1rem 0 0.1rem 1rem;
      border-left: 3px solid var(--accent-strong);
      color: #cbd5e1;
    }}
    @media (max-width: 820px) {{
      .shell {{ padding: 18px 14px 32px; }}
      .hero {{ flex-direction: column; align-items: stretch; }}
      .content {{ padding: 18px; }}
      .page-layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; max-height: 40vh; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <div>
        <h1>{escape(title)}</h1>
        <p>Generated InfoSite</p>
      </div>
    </header>
    <div class="page-layout">
      <aside class="surface sidebar" aria-label="InfoSite navigation">
        <h2>Alle Inhalte</h2>
        <ul>{nav_html}</ul>
        {"<h2>Seiten in diesem Dokument</h2><ul>" + section_nav_html + "</ul>" if section_nav_html else ""}
      </aside>
      <main class="surface content">
        {body_html}
      </main>
    </div>
  </div>
</body>
</html>
"""

    @staticmethod
    def _render_metadata_html(metadata: dict) -> str:
        rows = []
        if isinstance(metadata, dict):
            for key, value in metadata.items():
                if isinstance(value, dict):
                    nested = "<ul>" + "".join(
                        f"<li><strong>{k}</strong>: {v}</li>" for k, v in value.items()
                    ) + "</ul>"
                    rows.append(f"<tr><th>{key}</th><td>{nested}</td></tr>")
                elif isinstance(value, list):
                    rows.append(f"<tr><th>{key}</th><td>{' '.join(str(item) for item in value)}</td></tr>")
                else:
                    rows.append(f"<tr><th>{key}</th><td>{value}</td></tr>")
        if not rows:
            return "<p>No metadata available.</p>"
        return "<table><tbody>" + "".join(rows) + "</tbody></table>"

    @staticmethod
    def _render_html_index(links: list[tuple[str, str]], title: str) -> str:
        list_html = "\n".join(
            f'<li><a href="{escape(href, quote=True)}">{escape(label)}</a></li>'
            for label, href in links
        )
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #020617;
      --panel: rgba(15, 23, 42, 0.96);
      --panel-soft: rgba(30, 41, 59, 0.55);
      --border: rgba(148, 163, 184, 0.22);
      --text: #e2e8f0;
      --muted: #94a3b8;
      --accent: #7dd3fc;
      --shadow: 0 20px 45px rgba(2, 6, 23, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.7;
      color: var(--text);
      background:
        radial-gradient(circle at top, rgba(96, 165, 250, 0.14), transparent 28%),
        linear-gradient(180deg, #020617 0%, #0f172a 100%);
    }}
    a {{ color: var(--accent); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .shell {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 28px 20px 48px;
    }}
    .hero {{
      padding: 22px 24px;
      border: 1px solid rgba(125, 211, 252, 0.16);
      border-radius: 18px;
      background:
        radial-gradient(circle at top right, rgba(96, 165, 250, 0.18), transparent 28%),
        linear-gradient(180deg, rgba(15, 23, 42, 0.96), rgba(2, 6, 23, 0.98));
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }}
    .hero h1 {{ margin: 0; font-size: clamp(2rem, 4vw, 2.8rem); }}
    .hero p {{ margin: 8px 0 0; color: var(--muted); }}
    .surface {{
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 18px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .page-layout {{
      display: grid;
      grid-template-columns: minmax(220px, 280px) minmax(0, 1fr);
      align-items: start;
      gap: 18px;
    }}
    .sidebar {{
      position: sticky;
      top: 16px;
      max-height: calc(100vh - 32px);
      overflow-y: auto;
      padding: 16px;
    }}
    .sidebar h2 {{
      margin: 0 0 8px;
      font-size: 0.75rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--muted);
    }}
    .sidebar ul {{
      list-style: none;
      padding: 0;
      margin: 0;
    }}
    .sidebar li a {{
      display: block;
      padding: 5px 8px;
      border-radius: 7px;
      color: var(--muted);
      font-size: 0.88rem;
    }}
    .sidebar li a:hover {{ background: var(--panel-soft); color: var(--accent); }}
    .content {{ padding: 20px 24px 26px; }}
    @media (max-width: 820px) {{
      .shell {{ padding: 18px 14px 32px; }}
      .page-layout {{ grid-template-columns: 1fr; }}
      .sidebar {{ position: static; max-height: 40vh; }}
      .content {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <header class="hero">
      <h1>{escape(title)}</h1>
      <p>Generated InfoSite</p>
    </header>
    <div class="page-layout">
      <aside class="surface sidebar" aria-label="InfoSite navigation">
        <h2>Alle Inhalte</h2>
        <ul>{list_html}</ul>
      </aside>
      <main class="surface content">
        <h2>InfoSite</h2>
        <p>{len(links)} Inhalte sind verfügbar. Wähle einen Eintrag in der Navigation.</p>
      </main>
    </div>
  </div>
</body>
</html>
"""

    def _create_output_structure(self, domain: str, working_title: str) -> Path:
        """Create output directory structure with required subdirectories."""
        output_dir = self.layout.output_dir(domain, working_title)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (output_dir / "_originals" / "v1-original").mkdir(parents=True, exist_ok=True)
        (output_dir / "topics").mkdir(parents=True, exist_ok=True)
        
        return output_dir

    def _copy_originals(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
    ) -> Path:
        """
        Copy source documents to _originals/v1-original as immutable baseline.
        Preserves directory structure from source.
        """
        originals_dir = output_dir / "_originals" / "v1-original"
        
        for doc in source_docs:
            # Reconstruct relative path structure
            rel_path = doc.path.relative_to(
                self.layout.source_dir(MARKDOWN, domain, working_title)
            )
            dest_path = originals_dir / rel_path
            
            # Create parent directory
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(doc.path, dest_path)
        
        return originals_dir

    @staticmethod
    def _node_title(node: object) -> str:
        if not isinstance(node, dict):
            return ""
        for key in ("title", "name", "slug"):
            value = node.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    @classmethod
    def _find_hierarchy_path_for_title(cls, node: object, target_title: str, current_path: list[str] | None = None) -> list[str] | None:
        current_path = current_path or []
        if not isinstance(node, dict):
            return None

        title = cls._node_title(node)
        next_path = current_path + ([title] if title else [])

        if title == target_title:
            return next_path

        children = node.get("children") or node.get("items") or []
        if isinstance(children, list):
            for child in children:
                result = cls._find_hierarchy_path_for_title(child, target_title, next_path)
                if result is not None:
                    return result
        return None

    def _map_doc_to_hierarchy_path(self, rel_path: Path, site_structure: object | None) -> Path:
        """Resolve a source document's output path using the edited hierarchy when available."""
        if site_structure in (None, {}, []):
            return rel_path

        folder_parts = list(rel_path.parts[:-1])
        if not folder_parts:
            return rel_path

        for depth in range(len(folder_parts), 0, -1):
            target_folder = folder_parts[depth - 1]
            hierarchy_path = self._find_hierarchy_path_by_folder(site_structure, target_folder)
            if hierarchy_path is not None:
                return Path(*hierarchy_path, rel_path.name)

        return rel_path

    def _find_hierarchy_path_by_folder(self, site_structure: object | None, folder_name: str) -> list[str] | None:
        if site_structure is None:
            return None

        if isinstance(site_structure, dict):
            candidates = [site_structure]
        elif isinstance(site_structure, list):
            candidates = site_structure
        else:
            candidates = []

        for candidate in candidates:
            result = self._find_hierarchy_path_for_title(candidate, folder_name)
            if result is not None:
                return result
        return None

    def _copy_hierarchical_output_tree(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
        site_structure: object | None = None,
    ) -> None:
        """Mirror the edited hierarchy into the generated output directory."""
        if not source_docs:
            return

        source_root = self.layout.source_dir(MARKDOWN, domain, working_title)
        for doc in source_docs:
            try:
                rel_path = doc.path.relative_to(source_root)
            except ValueError:
                rel_path = Path(doc.path.name)

            target_rel = self._map_doc_to_hierarchy_path(rel_path, site_structure)
            dest_path = output_dir / target_rel
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(doc.path, dest_path)
    
    @staticmethod
    def _normalize_topic_order_token(value: object) -> str:
        """Normalize a user-defined section name into a sortable identifier."""
        if value is None:
            return ""
        if isinstance(value, dict):
            for key in ("slug", "title", "name"):
                if key in value and value.get(key):
                    value = value[key]
                    break
        text = str(value).strip().lower()
        return text.replace("_", "-").replace(" ", "-")

    @classmethod
    def _flatten_site_structure(cls, value: object, *, results: list[str] | None = None) -> list[str]:
        """Flatten nested site_structure trees into a list of label strings."""
        results = results if results is not None else []
        if isinstance(value, dict):
            if "title" in value or "name" in value or "slug" in value:
                results.append(str(value.get("title") or value.get("name") or value.get("slug") or ""))
            for child_key in ("children", "items"):
                if child_key in value:
                    cls._flatten_site_structure(value[child_key], results=results)
            return results
        if isinstance(value, list):
            for item in value:
                cls._flatten_site_structure(item, results=results)
            return results
        if value is not None:
            label = str(value).strip()
            if label:
                results.append(label)
        return results

    def _mapping_rules_by_source(self, mapping_rules: list[dict] | None = None) -> dict[str, dict]:
        """Normalize mapping rules so they can be matched to source files reliably."""
        result: dict[str, dict] = {}
        if not mapping_rules:
            return result
        for index, rule in enumerate(mapping_rules):
            if not isinstance(rule, dict):
                continue
            if rule.get("active") is False:
                continue
            source_path = str(rule.get("source_path") or rule.get("source") or "").strip()
            if not source_path:
                continue
            result[source_path] = {
                "source_path": source_path,
                "target_parent": str(rule.get("target_parent") or "").strip(),
                "target_section": str(rule.get("target_section") or rule.get("section") or "").strip(),
                "target_title": str(rule.get("target_title") or rule.get("title") or "").strip(),
                "target_slug": str(rule.get("target_slug") or "").strip(),
                "order_index": int(rule.get("order_index", index)),
                "mode": str(rule.get("mode") or "manual").strip() or "manual",
            }
        return result

    def _resolve_topic_for_doc(
        self,
        doc: FileInfo,
        domain: str,
        working_title: str,
        mapping_rules: list[dict] | None = None,
    ) -> str:
        """Resolve the logical section name for a document after applying mapping rules."""
        try:
            source_root = self.layout.source_dir(MARKDOWN, domain, working_title)
            relative = doc.path.relative_to(source_root)
            relative_key = relative.as_posix()
        except ValueError:
            relative_key = doc.path.name

        rules = self._mapping_rules_by_source(mapping_rules)
        direct_rule = rules.get(relative_key)
        if direct_rule:
            section = direct_rule.get("target_section") or direct_rule.get("target_parent") or doc.path.parent.name
            if direct_rule.get("target_parent") and direct_rule.get("target_section"):
                return f"{direct_rule['target_parent']}/{direct_rule['target_section']}"
            return section

        for rule in rules.values():
            source_path = rule["source_path"]
            if source_path == relative_key or relative_key.endswith(source_path) or source_path.endswith(relative_key):
                section = rule.get("target_section") or rule.get("target_parent") or doc.path.parent.name
                if rule.get("target_parent") and rule.get("target_section"):
                    return f"{rule['target_parent']}/{rule['target_section']}"
                return section

        return doc.path.parent.name

    def _topic_order(
        self,
        topic: str,
        site_structure: object | None = None,
        mapping_rules: list[dict] | None = None,
    ) -> tuple[int, str]:
        """Return a priority tuple so project-defined ordering wins over default sorting."""
        normalized = self._normalize_topic_order_token(topic)
        order_map: dict[str, int] = {}

        for index, rule in enumerate(mapping_rules or []):
            if not isinstance(rule, dict):
                continue
            if rule.get("active") is False:
                continue
            section = str(rule.get("target_section") or rule.get("section") or rule.get("target_parent") or "").strip()
            if not section:
                continue
            order_map[self._normalize_topic_order_token(section)] = int(rule.get("order_index", index))

        if isinstance(site_structure, dict):
            for key, value in site_structure.items():
                if key in {"title", "name", "slug"}:
                    order_map[self._normalize_topic_order_token(value)] = 0
                    continue
                if isinstance(value, list):
                    for idx, item in enumerate(value):
                        order_map[self._normalize_topic_order_token(item)] = idx

        elif isinstance(site_structure, list):
            for idx, item in enumerate(site_structure):
                order_map[self._normalize_topic_order_token(item)] = idx

        for idx, label in enumerate(self._flatten_site_structure(site_structure)):
            order_map[self._normalize_topic_order_token(label)] = idx

        if not site_structure and not mapping_rules:
            return (1_000_000, normalized)
        return (order_map.get(normalized, 1_000_000), normalized)

    def _generate_index(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
        site_structure: object | None = None,
        mapping_rules: list[dict] | None = None,
    ) -> None:
        """Generate main index.md with all topics and documents."""
        # Group documents by mapped topic
        topics = {}
        for doc in source_docs:
            topic = self._resolve_topic_for_doc(doc, domain, working_title, mapping_rules)
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(doc)

        ordered_topics = sorted(topics.keys(), key=lambda t: self._topic_order(t, site_structure, mapping_rules))
        
        # Build index content
        lines = [
            f"# {working_title.upper()} - Complete Index",
            "",
            f"**Domain:** {domain}  ",
            f"**Generated:** {datetime.now().isoformat()}  ",
            f"**Total Documents:** {len(source_docs)}  ",
            f"**Topics:** {len(topics)}  ",
            "",
            "---",
            "",
            "## Table of Contents",
            "",
        ]
        
        # Add topics to TOC
        for topic in ordered_topics:
            lines.append(f"- [{topic}](#{topic.lower().replace(' ', '-')})")
        
        lines.extend(["", "---", ""])
        
        # Add topic sections
        for topic in ordered_topics:
            lines.extend([
                f"## {topic}",
                "",
                f"**Documents:** {len(topics[topic])}",
                "",
            ])
            
            for doc in sorted(topics[topic], key=lambda d: d.path.name):
                rel_path = doc.path.relative_to(
                    self.layout.source_dir(MARKDOWN, domain, working_title)
                )
                lines.append(f"- {doc.path.stem}")
            
            lines.append("")
        
        # Write index
        index_path = output_dir / "index.md"
        index_path.write_text("\n".join(lines), encoding="utf-8")

    def _generate_overview(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
        site_structure: object | None = None,
        mapping_rules: list[dict] | None = None,
    ) -> None:
        """Generate overview.md with summary and statistics."""
        # Group by mapped topic
        topics = {}
        total_size = 0

        for doc in source_docs:
            topic = self._resolve_topic_for_doc(doc, domain, working_title, mapping_rules)
            if topic not in topics:
                topics[topic] = {"count": 0, "size": 0}
            topics[topic]["count"] += 1
            topics[topic]["size"] += doc.size or 0
            total_size += doc.size or 0

        ordered_topics = sorted(topics.keys(), key=lambda t: self._topic_order(t, site_structure, mapping_rules))

        lines = [
            f"# {working_title} - Overview",
            "",
            "## Summary",
            "",
            f"- **Domain:** {domain}",
            f"- **Working Title:** {working_title}",
            f"- **Total Documents:** {len(source_docs)}",
            f"- **Topics:** {len(topics)}",
            f"- **Total Size:** {total_size:,} bytes ({total_size / 1024 / 1024:.2f} MB)",
            f"- **Generated:** {datetime.now().isoformat()}",
            "",
            "## Topics Breakdown",
            "",
        ]
        
        # Add topic statistics
        for topic in ordered_topics:
            stats = topics[topic]
            lines.append(f"### {topic}")
            lines.extend([
                f"- Documents: {stats['count']}",
                f"- Size: {stats['size']:,} bytes",
                "",
            ])
        
        # Write overview
        overview_path = output_dir / "overview.md"
        overview_path.write_text("\n".join(lines), encoding="utf-8")

    def _generate_metadata(
        self,
        domain: str,
        working_title: str,
        source_docs: list[FileInfo],
        output_dir: Path,
        mapping_rules: list[dict] | None = None,
    ) -> dict:
        """Generate metadata dictionary for YAML export."""
        topics = {}
        for doc in source_docs:
            topic = self._resolve_topic_for_doc(doc, domain, working_title, mapping_rules)
            if topic not in topics:
                topics[topic] = []
            topics[topic].append(str(doc.path.name))

        total_size = sum(doc.size or 0 for doc in source_docs)

        return {
            "generation": {
                "timestamp": datetime.now().isoformat(),
                "version": "v1-original",
            },
            "project": {
                "domain": domain,
                "working_title": working_title,
                "description": f"InfoSite project for {domain}/{working_title}",
            },
            "statistics": {
                "total_documents": len(source_docs),
                "total_topics": len(topics),
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / 1024 / 1024, 2),
            },
            "topics": topics,
            "mapping_rules": mapping_rules or [],
            "output_structure": {
                "_originals": "Immutable baseline of original source documents",
                "topics": "Placeholder for refined/generated content (Phase 3)",
                "index.md": "Complete index of all documents",
                "overview.md": "Summary statistics and breakdown by topic",
                "metadata.yml": "This file - generation metadata",
            },
        }

    def _write_metadata(self, output_dir: Path, metadata: dict) -> None:
        """Write metadata to YAML file."""
        metadata_path = output_dir / "metadata.yml"
        with open(metadata_path, "w") as f:
            yaml.dump(metadata, f, default_flow_style=False, allow_unicode=True)

    def get_output_directory(self, domain: str, working_title: str) -> Path:
        """Get output directory path for a project."""
        return self.layout.output_dir(domain, working_title)

    def list_versions(self, domain: str, working_title: str) -> list[str]:
        """List all available versions in _originals directory."""
        originals_dir = self.layout.output_dir(domain, working_title, "_originals")
        
        if not originals_dir.exists():
            return []
        
        return sorted([d.name for d in originals_dir.iterdir() if d.is_dir()])

    def get_version_metadata(self, domain: str, working_title: str, version: str) -> Optional[dict]:
        """Get metadata for a specific version."""
        metadata_path = self.layout.output_dir(domain, working_title, "metadata.yml")
        
        if not metadata_path.exists():
            return None
        
        with open(metadata_path) as f:
            return yaml.safe_load(f)

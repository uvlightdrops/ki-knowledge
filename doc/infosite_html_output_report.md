# InfoSite HTML Output Report

## Goal

The InfoSite workflow needed a way to preview the generated project as a simple static website, not only as markdown artifacts. The objective was to keep the canonical markdown pipeline intact while adding an optional HTML export for quick review, testing, and publishing.

## What was added

- `InfoSiteProject.generate_html_site` boolean field
- Checkbox in the project form for "Generate static HTML website"
- Checkbox in the project detail page action panel for one-click HTML generation
- `InfoSiteGeneratorService.generate_html_site()` method that writes a browsable `/html/` directory beside the markdown output
- HTML pages rendered with Python's `markdown` package, preserving headings and lists

## Output structure

```text
data_out/<domain>/<working_title>/
├── index.md
├── overview.md
├── metadata.yml
├── html/
│   ├── index.html
│   ├── overview.html
│   └── ...
├── _originals/
└── topics/
```

## Why this approach

- It keeps the markdown-based source of truth untouched.
- It avoids adding a heavy static-site generator dependency by default.
- It creates a lightweight preview artifact that is easy to inspect in browser or via the generated output tree.
- It leaves room for a later integration with a richer SSG such as MkDocs/Hugo when editorial workflows mature.

## Notes

The project docs already mention a static-site-generator-ready flow. This change makes that path concrete without forcing a specific external library into the base runtime. The HTML output is designed as an optional preview layer, while the canonical dataset remains markdown and metadata-based.

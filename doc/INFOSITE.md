# Infosite Feature - Knowledge Presentation

The **infosite** feature (Knowledge Presentation) generates a browsable, markdown-based knowledge website from structured content. It's designed to be version-controllable, static-site-generator-compatible, and ready for AI-assisted content enhancement.

## Features

- **Markdown Output** - All content is generated as clean, version-controllable markdown files
- **Hierarchical Structure** - Organized directory structure with index files for automatic navigation
- **Metadata Tracking** - YAML frontmatter for version control and content lineage
- **Original Backup** - Automatic versioning of the initial content as baseline
- **SSG-Ready** - Compatible with Hugo, Jekyll, MkDocs, and other static site generators
- **AI-Friendly** - Designed for incremental improvements with AI assistance

## Configuration

Configure infosite in your `ki.yaml` config file:

```yaml
infosite:
  enabled: true
  title: "My Knowledge Base"        # Display title for the site
  domain: "default"                 # Domain/namespace for content
  output_base_dir: "/path/to/data/out"  # Base directory for output
```

The output structure will be:
```
<output_base_dir>/<domain>/<slugified-title>/
├── index.md                    # Home page
├── metadata.yml                # Version and metadata
├── overview/index.md           # Overview page
├── resources/index.md          # Resources page
└── _originals/
    └── v1-original/            # Backup of original version
```

## Usage

### Programmatic Usage

```python
from ki_core.config import Config
from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator
from ki_knowledge.infosite.models import PageSpec

# Load configuration
config = Config.from_yaml()

# Create infosite configuration
infosite_config = InfoSiteConfig(
    enabled=True,
    title="My Knowledge Base",
    domain="tech",
    output_base_dir=config.knowledge_data_root,
)

# Create generator
generator = InfoSiteGenerator(infosite_config)

# Define pages
pages = [
    PageSpec(
        slug="index",
        title="Home",
        content="Welcome to the knowledge base",
    ),
    PageSpec(
        slug="topic-1",
        title="First Topic",
        content="Content for first topic",
    ),
]

# Generate
output_dir = generator.generate(pages, create_originals_backup=True)
print(f"Generated to: {output_dir}")
```

### Using the Example Script

```bash
cd examples
python infosite_generate.py
```

The script will:
1. Read your `ki.yaml` configuration
2. Generate example knowledge base structure
3. Create markdown files with sample content
4. Back up the original version to `_originals/v1-original/`

## Output Structure

Each page is stored as `<slug>/index.md` with a title header:

```markdown
# Page Title

Page content goes here...

## Section 1
...

## Section 2
...
```

### Metadata File

`metadata.yml` contains version information and metadata:

```yaml
version: v1-original              # Version identifier
generated_at: 2026-09-02T...     # Generation timestamp
title: My Knowledge Base          # Site title
domain: default                   # Domain
source_documents: []              # List of source documents
```

## Content Organization

### Slugs

Page slugs are converted to lowercase, hyphen-separated URLs:
- "First Topic" → `first-topic`
- "Getting Started" → `getting-started`
- "API Reference" → `api-reference`

### Hierarchy

Pages can have nested child pages:

```python
parent = PageSpec(
    slug="parent",
    title="Parent Topic",
    content="Parent content",
    children=[
        PageSpec(slug="child1", title="Child 1", content="..."),
        PageSpec(slug="child2", title="Child 2", content="..."),
    ]
)
```

This creates:
```
parent/
├── index.md          # Parent page
├── child1/index.md   # Child 1
└── child2/index.md   # Child 2
```

## Versioning

### Original Version Backup

When generating with `create_originals_backup=True`, the generator creates:

```
_originals/v1-original/
├── index.md
├── metadata.yml
├── topic-1/
└── ...
```

This preserves the initial content version for comparison and rollback.

### Version Naming

Versions follow this pattern:
- `v1-original` - Initial version from source documents
- `v2-ai-enhanced` - After AI improvements
- `v3-community-edited` - After community edits

## Integration with Static Site Generators

### Hugo

```bash
hugo new site my-knowledge-base
cp -r output/default/my-knowledge-base/* my-knowledge-base/content/
hugo
```

### Jekyll

```bash
cp -r output/default/my-knowledge-base/* _posts/
jekyll build
```

### MkDocs

```bash
mkdocs new my-knowledge-base
cp -r output/default/my-knowledge-base/docs/
mkdocs serve
```

## Future Enhancements

### Phase 2: AI-Assisted Generation
- Automatic content generation from source documents
- AI-powered refinement suggestions
- Semantic enhancement with AI

### Phase 3: Knowledge Block Integration
- Link content to semantic knowledge blocks
- Graph-based navigation
- Relationship mapping

### Phase 4: Collaborative Editing
- Version history tracking
- Diff-based change management
- Collaborative improvements

## API Reference

### InfoSiteConfig

- `enabled: bool` - Enable/disable feature
- `title: str` - Site title
- `domain: str` - Content domain
- `output_base_dir: str` - Output base directory
- `get_output_dir() -> Path` - Get full output directory

### InfoSiteMetadata

- `version: str` - Version identifier
- `generated_at: datetime` - Generation timestamp
- `title: str` - Site title
- `domain: str` - Domain
- `source_documents: List[str]` - Source document references
- `custom_fields: Dict` - Additional metadata
- `to_frontmatter_dict() -> Dict` - Convert to YAML dict

### PageSpec

- `slug: str` - URL-friendly page identifier
- `title: str` - Display title
- `content: str` - Markdown content
- `order: int` - Sort order
- `children: List[PageSpec]` - Child pages
- `get_path(base_path) -> Path` - Get file path

### InfoSiteGenerator

- `__init__(config, metadata=None)` - Initialize generator
- `generate(pages, create_originals_backup=True) -> Path` - Generate site
- `create_default_pages(title) -> List[PageSpec]` - Create default pages

## Examples

See `examples/infosite_generate.py` for a complete example demonstrating:
- Configuration loading
- Custom page creation with hierarchy
- Original version backup
- Output file listing

## Testing

Run tests with:

```bash
python -m pytest tests/test_infosite.py -v
```

Tests cover:
- Configuration and slug generation
- Page generation and file output
- Metadata handling
- Page hierarchy
- Original version backup

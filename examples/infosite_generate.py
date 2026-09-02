"""Example script for infosite generation."""

import sys
from pathlib import Path

from ki_core.config import Config

from ki_knowledge.infosite import InfoSiteConfig, InfoSiteGenerator
from ki_knowledge.infosite.models import PageSpec


def create_example_pages() -> list[PageSpec]:
    """Create example page structure for demonstration."""
    return [
        PageSpec(
            slug="index",
            title="Welcome to My Knowledge Base",
            content="""
This is an example knowledge presentation generated with the infosite feature.

## What is this?

This is a browsable, markdown-based knowledge website that can be:
- Version controlled with Git
- Automatically regenerated from source documents
- Enhanced with AI assistance
- Built into static websites using tools like Hugo or Jekyll

## Getting Started

Start by exploring the [Overview](overview/index.md) section.

## Example Topics

The knowledge base contains example topics organized by category:

1. **Topic 1** - Introduction to basic concepts
2. **Topic 2** - Advanced topics and techniques  
3. **Resources** - Links and references

---

*This is an example generated knowledge base.*
""".strip(),
            order=0,
        ),
        PageSpec(
            slug="overview",
            title="Overview",
            content="""
# Knowledge Base Overview

This knowledge base is organized into several main sections:

## Sections

### 1. Fundamentals
Introduction to core concepts and basic principles.

### 2. Advanced Topics
Deeper exploration of specialized areas.

### 3. Resources
References, tools, and external materials.

## Accessing Content

You can navigate this knowledge base by:
- Following links in the structure
- Using your static site generator's search
- Browsing the directory structure

## About Version Control

All markdown files in this knowledge base are suitable for version control.
Each change can be tracked, and versions can be compared easily.
""".strip(),
            order=1,
        ),
        PageSpec(
            slug="topic-1",
            title="Topic 1: Getting Started",
            content="""
## Introduction

This section covers the basics and getting started concepts.

### Key Concepts

1. **Concept A** - Understanding the fundamentals
2. **Concept B** - Building on basics
3. **Concept C** - Combining concepts

### Examples

Here are some practical examples:

- Example 1: Basic usage
- Example 2: Intermediate techniques
- Example 3: Advanced patterns

### Next Steps

After understanding the basics, explore Topic 2 for more advanced content.
""".strip(),
            order=2,
            children=[
                PageSpec(
                    slug="basics",
                    title="Basics",
                    content="""
## Getting Started with Basics

This section introduces fundamental concepts.

### What You'll Learn

- Core principles
- Basic terminology
- Essential tools

### Quick Start

1. Learn the fundamentals
2. Practice with examples
3. Build your understanding

### Resources

- [Official Documentation](http://example.com)
- [Community Guide](http://example.com)
- [Video Tutorials](http://example.com)
""".strip(),
                ),
                PageSpec(
                    slug="tutorials",
                    title="Tutorials",
                    content="""
## Tutorials

Step-by-step guides for common tasks.

### Tutorial 1: Getting Started
Follow these steps to get set up and running.

### Tutorial 2: Intermediate Tasks
Once you've mastered the basics, try these intermediate tutorials.

### Tutorial 3: Advanced Techniques
Push your skills with these advanced tutorials.

Each tutorial includes examples and explanations.
""".strip(),
                ),
            ],
        ),
        PageSpec(
            slug="resources",
            title="Resources",
            content="""
## Resources and References

A collection of useful resources for further learning.

### External References

- [Reference 1](http://example.com)
- [Reference 2](http://example.com)
- [Reference 3](http://example.com)

### Tools and Libraries

- Tool A - Description
- Tool B - Description
- Tool C - Description

### Further Reading

For more information, see:
- Academic papers
- Technical documentation
- Community forums

### Contributing

Found a useful resource? Consider contributing to this knowledge base!
""".strip(),
            order=3,
        ),
    ]


def main():
    """Generate example infosite."""
    # Load configuration
    config = Config.from_yaml()

    # Check if infosite is configured
    if not config.infosite_output_base_dir:
        print("Error: infosite_output_base_dir not configured")
        print("Please set 'infosite_output_base_dir' in your ki.yaml config")
        sys.exit(1)

    # Create infosite configuration
    infosite_config = InfoSiteConfig(
        enabled=True,
        title=config.infosite_title or "Example Knowledge Base",
        domain=config.infosite_domain,
        output_base_dir=config.infosite_output_base_dir,
    )

    print(f"Generating infosite: {infosite_config.title}")
    print(f"Domain: {infosite_config.domain}")
    print(f"Output: {infosite_config.get_output_dir()}")

    # Create generator
    generator = InfoSiteGenerator(infosite_config)

    # Create example pages
    pages = create_example_pages()

    # Generate
    output_dir = generator.generate(pages, create_originals_backup=True)

    print(f"\n✓ Infosite generated successfully!")
    print(f"✓ Output directory: {output_dir}")
    print(f"✓ Original version backed up to: {output_dir.parent / '_originals' / 'v1-original'}")

    # List generated files
    print("\nGenerated files:")
    for md_file in sorted(output_dir.glob("**/*.md")):
        if "_originals" not in md_file.parts:
            relative = md_file.relative_to(output_dir)
            print(f"  - {relative}")


if __name__ == "__main__":
    main()

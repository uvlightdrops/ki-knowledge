"""Wagtail-based CMS/workflow layer for ki-knowledge.

This app is deliberately thin: it consumes the canonical data-source
abstraction (ki_knowledge.knowledge.models / adapters) instead of owning its
own content model. It exists to introduce editorial workflow, moderation and
review on top of the existing InfoSite/Knowledge core without forcing a
big-bang migration.
"""

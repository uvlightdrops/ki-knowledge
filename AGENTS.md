# Agent Usage Guide for Copilot CLI

This document describes how to effectively delegate work to Copilot sub-agents when working on this project.

## When to Use Sub-Agents

### ✅ DO Delegate
- **Large codebase exploration** (200+ files to search across)
  - Use: `explore` agent
  - Example: "Search codebase for all places where KnowledgeBlockRecord is used"
  
- **Independent parallel investigations**
  - Use: Multiple `explore` agents simultaneously
  - Example: Agent A investigates data schema, Agent B searches for related views
  
- **Complex multi-step tasks** with long-running commands
  - Use: `general-purpose` agent with mode="background"
  - Example: Run tests, build, lint, install dependencies
  
- **Code review of large diffs** (200+ lines across many files)
  - Use: `code-review` agent
  - Example: Review Phase 2 or Phase 3 commits for bugs
  
- **Security vulnerability investigation** when explicitly requested
  - Use: `security-review` agent
  - Example: "Find exploitable vulnerabilities in authentication"

- **Research and verification** (fetching external docs, verifying claims)
  - Use: `research` agent
  - Example: "Verify Django 6.1 template tag syntax"

### ❌ DON'T Delegate
- Simple single grep/glob search
- Reading 1-5 known files
- Quick edits to known files
- Commands that finish in <5 seconds
- "Find this specific function in views.py"
- Single file operations

## Project-Specific Patterns

### Multi-Phase Implementation
Each phase typically has:
1. **View/Model changes** (Python)
2. **Template changes** (HTML)
3. **URL routing** (urls.py)
4. **Database integration** (models.py)
5. **Testing/Validation**

For a phase:
- Search for related code yourself (grep/glob) — it's faster
- Delegate if you need to audit 50+ files at once
- Use `explore` agent for understanding unfamiliar code areas

### Knowledge Block Pipeline
Current phases:
- **Phase A** (done): Parse markdown → KnowledgeBlockData
- **Phase B** (in progress): Store in knowledge_store.py, UI integration
- **Phase C** (future): Entity extraction, semantic analysis
- **Phase D** (future): Knowledge graph visualization

### Common Commands
```bash
# Django system check (quick, do yourself)
python manage.py check

# Run specific test
python manage.py test infosite_tests.test_something

# Full test suite (delegate if >5 minutes)
python manage.py test

# Search for symbol (use grep/glob, not agent)
grep -r "KnowledgeBlockRecord" --include="*.py"

# Explore unknown module (delegate only if 100+ files)
# Don't delegate: explore 5 files to understand InfoSiteProject
# DO delegate: explore entire codebase for all uses of a symbol
```

## Agent Request Template

When delegating, provide:

```markdown
**Task:** [Brief description]

**Context:** 
- This is part of Phase B: Knowledge Block Storage
- Current file: ki_knowledge/django_site/infosite_views.py
- Related files: ki_knowledge/knowledge/models.py, ki_knowledge/integrations/knowledge_store.py

**What to find/investigate:**
- [Specific question 1]
- [Specific question 2]
- Look for patterns in: [file globs]

**Return:** 
- File paths with line numbers
- Code snippets showing the pattern
- Summary of findings
```

## Background vs Sync Mode

### Sync Mode (default)
- Use for: Quick exploration, simple fixes, "I need this before I continue"
- The agent completes and returns results in one turn
- Your next action depends on its output
- Example: "Find where SourceDocument.file_size_display is used"

### Background Mode
- Use for: Long-running work (builds, tests, indexing)
- You continue with other work while agent runs
- Notification when done
- Use when: "I'll explore X while you build Y"
- Example: "Build the project and run test suite (I'll check model definitions)"

**Important:** Only use background mode if you have other independent work to do immediately after. Don't background an agent and then wait for it.

## Agent Capabilities Reference

| Agent | Best For | Tools | Speed | Notes |
|-------|----------|-------|-------|-------|
| `explore` | Code search, understanding architecture | grep/glob/view/bash | Fast | Lightweight, good for parallel work |
| `task` | Building, testing, long commands | bash, all CLI | Variable | Returns brief summary on success, full output on fail |
| `general-purpose` | Complex multi-step workflows | All tools | Slower | High-capability, keeps main context clean |
| `code-review` | Auditing diffs for bugs | All read-only tools | Medium | Read-only, high confidence findings only |
| `research` | Fetching docs, verifying facts | web_fetch, bash, grep/glob | Medium | Handles citations, external research |
| `security-review` | Finding exploitable vulnerabilities | All read-only tools | Medium | High confidence only, security-focused |

## Parallel Delegation Pattern

Maximize efficiency when working on multiple features:

```
Main conversation (you):
1. Search for model definitions (grep/view)
2. Start explore-agent-1 in background: "Find all uses of X"
3. While agent-1 runs, you search for template changes
4. Start explore-agent-2 in background: "Find all uses of Y"
5. Meanwhile, you edit known files
6. Wait for agent-1 → read results
7. Use those results for next edits
8. Wait for agent-2 → incorporate findings
```

This approach:
- ✅ Keeps context in main conversation
- ✅ Parallelizes independent work
- ✅ Minimizes idle time
- ✅ Avoids context waste on sub-agent overhead

## Decision Tree

```
Is this task < 2 grep/view/edit calls?
  → Do it yourself

Need to search 200+ files for a pattern?
  → explore agent (sync)

Need to understand code in unfamiliar area?
  → Read 5 files yourself
  → If still unclear, ask user or use explore agent

Need to run tests/build/lint?
  → If <1 min: do yourself
  → If 1-5 min: task agent (sync)
  → If >5 min and you have other work: task agent (background)

Need to review a diff?
  → If <50 lines: do yourself
  → If 50-500 lines: code-review agent
  → If >500 lines or security concern: code-review + security-review

Investigating a crash/exception?
  → Try debugging locally first
  → If stuck: debug skill or general-purpose agent

Need external information?
  → research agent
```

## Debugging Sub-Agents

If an agent fails or returns nothing:

1. **Check the prompt** — was it specific enough?
2. **Retry with more context** — include file paths, line numbers
3. **Fall back to doing it yourself** — sub-agents add latency; if repeated failures, don't use them
4. **Ask the user** — "I'm uncertain how to proceed, should we try a different approach?"

## Project-Specific Notes

### InfoSite Pipeline
- Data flows: SourceDocument → markdown files → KnowledgeBlockData → KnowledgeBlockRecord → KnowledgeStore
- Each stage has tests; verify after changes
- URLs follow pattern: `/infosite/project/<id>/<feature>/`

### Django Changes Pattern
- Add view to `infosite_views.py`
- Add URL to `infosite_urls.py`
- Create template in `templates/infosite/<feature>.html`
- Add @login_required decorator
- Test with `python manage.py check`

### Common Modules
- `ki_knowledge/services/block_extractor.py` — markdown parsing
- `ki_knowledge/knowledge/models.py` — knowledge data structures
- `ki_knowledge/integrations/knowledge_store.py` — storage layer
- `ki_knowledge/django_site/infosite_*.py` — all InfoSite views, models, URLs

---

**Last Updated:** 2026-09-03
**Project:** ki-knowledge
**Version:** 1.0

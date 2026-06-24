---
name: docs-site-governor
description: Generate and validate open-source documentation-site readiness for Codex engineering skills. Use when publishing docs, checking documentation navigation, generating skill catalogs, scenario guides, FAQ pages, or detecting missing docs and broken local Markdown links.
---

# Docs Site Governor

Use this skill before publishing documentation or adding new public skills.

## Commands

```bash
python3 skills/core/docs-site-governor/scripts/docs_site.py generate --root .
python3 skills/core/docs-site-governor/scripts/docs_site.py validate --root .
```

## Rules

- Required docs: Getting Started, Workflow, Architecture, Open Core Boundary, Skill Catalog, Scenario Guide, FAQ.
- Skill catalog must reflect actual `SKILL.md` files.
- Scenario guide must reflect actual `examples/scenarios`.
- Local Markdown links must resolve.

## Output

The output uses schema `codex-docs-site-v1`.

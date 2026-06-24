---
name: roadmap-governor
description: Review roadmap consistency for Codex engineering skills. Use when adding skills, changing README skill lists, updating CHANGELOG, or preparing releases to ensure docs/open-source-roadmap.md reflects actual public skills and avoids stale or untracked capability claims.
---

# Roadmap Governor

Use this skill after adding or removing public skills.

## Command

```bash
python3 skills/core/roadmap-governor/scripts/roadmap.py --root .
```

## Rules

- Every public skill name should appear in roadmap, README, or generated skill catalog.
- Roadmap should include done markers for implemented capabilities.
- Future section should not contain empty placeholders.

## Output

The output uses schema `codex-roadmap-review-v1`.

---
name: code-index-builder
description: Build a compact local code index for a project repository. Use when onboarding a project, reducing token-heavy source searches, refreshing private overlay indexes, or preparing code-index-lookup for requirement routing.
---

# Code Index Builder

Use this skill in private overlays, not to publish real project indexes in open core.

## Command

```bash
python3 skills/core/code-index-builder/scripts/build_index.py \
  --repo /path/to/project \
  --project web-app \
  --out overlay/indexes/web-app.index.json
```

## Output

The output uses schema `codex-code-index-v1`.

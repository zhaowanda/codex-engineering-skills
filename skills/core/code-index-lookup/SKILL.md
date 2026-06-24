---
name: code-index-lookup
description: Query compact project code indexes before broad source reads. Use when a requirement mentions files, symbols, endpoints, routes, pages, services, or business keywords and an index from code-index-builder exists.
---

# Code Index Lookup

Use this skill before reading a large codebase.

## Command

```bash
python3 skills/core/code-index-lookup/scripts/lookup_index.py \
  --index overlay/indexes/web-app.index.json \
  --query "checkout route"
```

## Output

The output uses schema `codex-code-index-lookup-v1`.

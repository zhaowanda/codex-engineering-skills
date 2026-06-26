---
name: code-index-lookup
description: Query compact project code indexes before broad source reads. Use when a requirement mentions files, symbols, endpoints, routes, pages, services, or business keywords and an index from code-index-builder exists.
---

# Code Index Lookup

Use this skill before reading a large codebase.

## Position

```text
code-index-builder
-> code-index-lookup
-> focused source inspection
-> requirement/design/implementation work
```

## Rules

- Query an existing index before broad file searches in large repositories.
- Return ranked hints only; do not treat lookup results as proof that no matching code exists.
- If the index is missing, stale, or from another project, rebuild it instead of guessing.
- Use lookup output to choose files for direct reading, not to replace source inspection.
- Avoid exposing private project terms outside the private overlay or local working context.

## Command

```bash
python3 scripts/lookup_index.py \
  --index overlay/indexes/web-app.index.json \
  --query "checkout route"
```

## Output

The output uses schema `codex-code-index-lookup-v1`.

The artifact reports query text, ranked matches, match reasons, and lookup limitations.

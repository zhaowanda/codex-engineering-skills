---
name: code-index-lookup
description: Query compact project code indexes before broad source reads. Use when a requirement mentions files, symbols, endpoints, routes, pages, services, or business keywords and an index from code-index-builder exists.
category: extractor-analyzer
maturity: deterministic-helper
stage: project-understanding
gate: false
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
- Treat empty or weak matches as a warning that direct source search is still required.
- Treat missing, unreadable, or schema-mismatched indexes as blockers for lookup-based planning.

## Command

```bash
python3 scripts/lookup_index.py \
  --index overlay/indexes/web-app.index.json \
  --query "checkout route"
```

## Output

The output uses schema `codex-code-index-lookup-v1`.

Decision values:

- `pass`: the index exists, matches the expected project, and returns useful ranked hints.
- `warn`: the index is valid but matches are weak or incomplete; continue with direct source inspection.
- `block`: the index is missing, unreadable, stale, schema-mismatched, or from a different project.

The artifact reports query text, ranked matches, match reasons, lookup limitations, warnings, blockers, and the final decision.

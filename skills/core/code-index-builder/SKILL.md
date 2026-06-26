---
name: code-index-builder
description: Build a compact local code index for a project repository. Use when onboarding a project, reducing token-heavy source searches, refreshing private overlay indexes, or preparing code-index-lookup for requirement routing.
---

# Code Index Builder

Use this skill in private overlays, not to publish real project indexes in open core.

## Position

```text
project-onboard / project-understanding-runner
-> code-index-builder
-> code-index-lookup
-> targeted source reading
```

## Rules

- Build compact navigation hints, not a full source mirror.
- Exclude binary files, generated dependency folders, caches, secrets, and large build outputs.
- Keep generated indexes in a private overlay or temporary artifact directory for real projects.
- Include enough file, symbol, route, and keyword hints to reduce broad source reads.
- Treat the index as stale after major refactors; refresh before using it for implementation planning.
- Do not commit private project indexes to the open-core repository.

## Command

```bash
python3 scripts/build_index.py \
  --repo /path/to/project \
  --project web-app \
  --out overlay/indexes/web-app.index.json
```

## Output

The output uses schema `codex-code-index-v1`.

The artifact should contain project metadata, indexed files, symbols, route hints, keywords, warnings, and generation limits.

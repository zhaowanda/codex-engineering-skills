---
name: api-surface-extractor
description: Extract generic API and route surface hints from a source repository. Use when reverse-engineering backend or frontend routes for private baseline docs without publishing real endpoint maps in open core.
---

# API Surface Extractor

Use this skill during project understanding before writing baseline docs or route-specific requirements.

## Position

```text
repository-analyzer
-> api-surface-extractor
-> project-baseline-reverser / project-understanding-runner
-> baseline-quality-governor
```

## Rules

- Extract route and endpoint hints only; do not publish private endpoint maps in open-core docs.
- Treat results as inferred hints, not authoritative API contracts.
- Record framework files, route-like strings, and frontend navigation hints when present.
- Return an empty surface with warnings rather than failing when a repository has no recognizable API routes.
- Do not include request payload examples, secrets, tokens, customer identifiers, or real hostnames.
- Prefer private overlay storage for generated artifacts from real repositories.

## Command

```bash
python3 scripts/api_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/api_surface.json
```

## Output

The output uses schema `codex-api-surface-v1`.

The artifact should include project identity, discovered route hints, source files, warnings, and limitations.

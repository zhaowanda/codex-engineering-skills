---
name: api-surface-extractor
description: Extract generic API and route surface hints from a source repository. Use when reverse-engineering backend or frontend routes for private baseline docs without publishing real endpoint maps in open core.
---

# API Surface Extractor

## Command

```bash
python3 skills/core/api-surface-extractor/scripts/api_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/api_surface.json
```

## Output

The output uses schema `codex-api-surface-v1`.

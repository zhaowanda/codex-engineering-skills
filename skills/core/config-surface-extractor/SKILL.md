---
name: config-surface-extractor
description: Extract configuration surface hints from a source repository without exposing secret values. Use when reverse-engineering config files, environment keys, Docker/CI config, feature flag hints, or private overlay baseline docs.
---

# Config Surface Extractor

## Command

```bash
python3 skills/core/config-surface-extractor/scripts/config_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/config_surface.json
```

## Output

The output uses schema `codex-config-surface-v1`.

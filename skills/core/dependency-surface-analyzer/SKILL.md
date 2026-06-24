---
name: dependency-surface-analyzer
description: Analyze dependency and build surface for a source repository. Use when reverse-engineering package managers, dependency files, build command hints, test command hints, and runtime ecosystem before creating private baseline docs.
---

# Dependency Surface Analyzer

## Command

```bash
python3 skills/core/dependency-surface-analyzer/scripts/dependency_surface.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/dependency_surface.json
```

## Output

The output uses schema `codex-dependency-surface-v1`.

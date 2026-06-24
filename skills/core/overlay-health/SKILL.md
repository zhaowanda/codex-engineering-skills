---
name: overlay-health
description: Check private overlay consistency for project registry, project skills, indexes, baseline docs, and delivery docs manifests. Use in private repositories before team rollout or after project onboarding.
---

# Overlay Health

## Command

```bash
python3 skills/core/overlay-health/scripts/overlay_health.py \
  --overlay-root overlay
```

## Output

The output uses schema `codex-overlay-health-v1`.

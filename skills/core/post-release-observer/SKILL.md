---
name: post-release-observer
description: Generate and validate post-release observation evidence. Use after deployment when APIs, frontend pages, reports, permissions, payments, devices, logs, metrics, alerts, or business indicators need observation before closing release.
---

# Post Release Observer

## Command

```bash
python3 skills/core/post-release-observer/scripts/post_release_observer.py template \
  --out artifacts/REQ-001/post_release_observation.json

python3 skills/core/post-release-observer/scripts/post_release_observer.py validate \
  --file artifacts/REQ-001/post_release_observation.json
```

## Output

The output uses schema `codex-post-release-observation-v1`.

---
name: post-release-observer
description: Generate and validate post-release observation evidence. Use after deployment when APIs, frontend pages, reports, permissions, payments, devices, logs, metrics, alerts, or business indicators need observation before closing release.
category: release-governor
maturity: expert-gate
stage: release
gate: true
---

# Post Release Observer

Use this skill after deployment and before closing release evidence.

## Position

```text
production deployment
-> post-release-observer
-> release-evidence-binder
-> release closure
```

## Rules

- Require observation window, owner, monitored checks, result, incidents, and close decision.
- Block release closure if required checks are missing, failed, or still observing.
- Include logs, metrics, alerts, business indicators, and user-visible smoke checks when applicable.
- Record incidents or anomalies with owner and follow-up action.
- Do not include secrets, customer data, private dashboards, or raw production credentials in artifacts.

## Command

```bash
python3 scripts/post_release_observer.py template \
  --out artifacts/REQ-001/post_release_observation.json

python3 scripts/post_release_observer.py validate \
  --file artifacts/REQ-001/post_release_observation.json
```

## Output

The output uses schema `codex-post-release-observation-v1`.

The artifact reports observation scope, checks, metrics/log references, incident status, close readiness, blockers, and warnings.

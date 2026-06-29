---
name: environment-promotion-governor
description: Generate and validate DEV/SIT/UAT/PRE/PROD environment promotion evidence. Use before release when a change needs environment entry criteria, exit criteria, configuration differences, validation evidence, blockers, and rollback readiness.
category: release-governor
maturity: expert-gate
stage: release
gate: true
---

# Environment Promotion Governor

Use this skill when a change moves through DEV/SIT/UAT/PRE/PROD or equivalent environments.

## Position

```text
configuration/test evidence
-> environment-promotion-governor
-> release-change-governor
-> release-evidence-binder
```

## Rules

- Require entry criteria, exit criteria, validation evidence, configuration differences, blockers, and rollback readiness per environment.
- Block promotion if required evidence or rollback readiness is missing for the target environment.
- Record environment-specific differences without storing secret values.
- Treat skipped environments as explicit waivers with owner and reason.
- Keep promotion evidence separate from deployment execution logs unless referenced as artifacts.

## Command

```bash
python3 scripts/environment_promotion.py template \
  --out artifacts/REQ-001/environment_promotion.json

python3 scripts/environment_promotion.py validate \
  --file artifacts/REQ-001/environment_promotion.json
```

## Output

The output uses schema `codex-environment-promotion-v1`.

The artifact reports environment readiness, criteria status, validation evidence, config differences, blockers, warnings, and rollback readiness.

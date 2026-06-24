---
name: environment-promotion-governor
description: Generate and validate DEV/SIT/UAT/PRE/PROD environment promotion evidence. Use before release when a change needs environment entry criteria, exit criteria, configuration differences, validation evidence, blockers, and rollback readiness.
---

# Environment Promotion Governor

## Command

```bash
python3 skills/core/environment-promotion-governor/scripts/environment_promotion.py template \
  --out artifacts/REQ-001/environment_promotion.json

python3 skills/core/environment-promotion-governor/scripts/environment_promotion.py validate \
  --file artifacts/REQ-001/environment_promotion.json
```

## Output

The output uses schema `codex-environment-promotion-v1`.

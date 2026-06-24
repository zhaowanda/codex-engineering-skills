---
name: uat-acceptance-governor
description: Generate and validate business UAT acceptance evidence. Use before release when user-visible behavior, reports, permissions, workflows, exports, payments, or cross-repo features require business/product acceptance.
---

# UAT Acceptance Governor

## Command

```bash
python3 skills/core/uat-acceptance-governor/scripts/uat_acceptance.py template \
  --out artifacts/REQ-001/uat_acceptance.json

python3 skills/core/uat-acceptance-governor/scripts/uat_acceptance.py validate \
  --file artifacts/REQ-001/uat_acceptance.json
```

## Output

The output uses schema `codex-uat-acceptance-v1`.

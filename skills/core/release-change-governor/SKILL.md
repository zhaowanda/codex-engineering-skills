---
name: release-change-governor
description: Generate and validate production release change evidence. Use before production release when a change needs release window, approvers, release order, rollback owner, change ticket, risk level, and communication plan.
---

# Release Change Governor

## Command

```bash
python3 skills/core/release-change-governor/scripts/release_change.py template \
  --out artifacts/REQ-001/release_change.json

python3 skills/core/release-change-governor/scripts/release_change.py validate \
  --file artifacts/REQ-001/release_change.json
```

## Output

The output uses schema `codex-release-change-v1`.

---
name: change-risk-governor
description: Classify engineering change risk from diff impact, delivery plan, configuration, security, performance, frontend, database, permission, and release signals. Use after diff-impact analysis or before release planning to choose lightweight, standard, heavy, or high-risk delivery controls.
---

# Change Risk Governor

Use this skill after implementation impact analysis or before release planning to determine the required control level.

## Command

```bash
python3 skills/core/change-risk-governor/scripts/change_risk.py \
  --artifact-dir artifacts/REQ-001 \
  --out artifacts/REQ-001/change_risk.json
```

## Risk Levels

- `low`: docs/tests-only or isolated low-impact code.
- `medium`: normal code change with standard review and test evidence.
- `high`: database, permission, configuration, payment, security, cross-repo, or performance-sensitive change.
- `critical`: destructive data changes, authentication/authorization, secrets, production config, rollback uncertainty, or multiple high-risk signals.

## Output

The output uses schema `codex-change-risk-v1`.

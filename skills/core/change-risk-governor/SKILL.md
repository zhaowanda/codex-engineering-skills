---
name: change-risk-governor
description: Classify engineering change risk from diff impact, delivery plan, configuration, security, performance, frontend, database, permission, and release signals. Use after diff-impact analysis or before release planning to choose lightweight, standard, heavy, or high-risk delivery controls.
category: workflow-gate
maturity: expert-gate
stage: post-implementation-review
gate: true
---

# Change Risk Governor

Use this skill after implementation impact analysis or before release planning to determine the required control level.

## Position

```text
diff-impact-analyzer / implementation-completion-gate
-> change-risk-governor
-> code-review-gate / release-change-governor
```

## Rules

- Classify risk from impact areas, delivery plan scope, configuration, security, performance, traceability, implementation, and diff text signals.
- Escalate to high or critical when database, permissions, auth, secrets, production config, payments, destructive operations, or rollback uncertainty appear.
- Never downgrade risk just because an evidence file is missing; missing evidence should increase uncertainty.
- Prefer `medium` for ordinary code changes with standard review and tests.
- Include required controls so release planning can choose validation, approval, and rollback depth.

## Command

```bash
python3 scripts/change_risk.py \
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

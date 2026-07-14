---
name: release-change-governor
description: Generate and validate production release change evidence. Use before production release when a change needs release window, approvers, release order, rollback owner, change ticket, risk level, and communication plan.
category: release-governor
maturity: expert-gate
stage: release
gate: true
---

# Release Change Governor

Use this skill before production release approval or change-ticket closure.

## Position

```text
release evidence preparation
-> release-change-governor
-> release-evidence-binder
-> production release approval
```

## Rules

- Require release window, approvers, release order, rollback owner, change ticket, risk level, and communication plan.
- Under a regulated release policy, require structured approver identity, approval timestamp/evidence, distinct approver count, implementer/approver separation of duties, immutable audit retention, and CI/change/deployment/observability integration evidence.
- Block release evidence when rollback owner or rollback plan is missing.
- Treat high-risk changes as requiring explicit approver and post-release check ownership.
- Keep release change evidence generic; do not include private credentials or customer data.
- Validate filled templates before binding release evidence.

## Command

```bash
python3 scripts/release_change.py template \
  --out artifacts/REQ-001/release_change.json

python3 scripts/release_change.py validate \
  --file artifacts/REQ-001/release_change.json
```

## Output

The output uses schema `codex-release-change-v1`.

The artifact reports release metadata, approval readiness, rollback readiness, communication plan, blockers, and warnings.

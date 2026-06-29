---
name: configuration-governor
description: Generate and validate configuration readiness evidence for engineering delivery. Use when requirements, designs, code changes, tests, or releases involve environment variables, database, MQ, email, SMS, payment, callbacks, certificates, feature flags, secrets, or provider configuration.
category: workflow-gate
maturity: expert-gate
stage: release
gate: true
---

# Configuration Governor

Use this skill during design and before release.

## Position

```text
spec/design/diff
-> configuration-governor
-> code-review-gate / release-evidence-binder
```

## Command

```bash
python3 scripts/configuration.py \
  analyze \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --architecture-design artifacts/REQ-001/architecture_design.json \
  --out artifacts/REQ-001/configuration_readiness.json
```

## Rules

- Block release if required runtime configuration lacks owner, environment scope, default, rollback, or secret-handling decision.
- Treat secrets/certificates/tokens as sensitive; never put values in artifacts.
- Payment/callback/MQ/database changes require environment and rollback verification.

## Output

The output uses schema `codex-configuration-readiness-v1`.

The artifact lists configuration items, owners, environment scope, defaults, rollback decisions, secret-handling rules, blockers, and warnings.

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
- Do not infer runtime configuration changes from ordinary business/data/API words alone. A database table, payment report, callback handler, or MQ mention is not a configuration item unless an explicit configuration/env/provider/callback URL/secret/feature flag context is present.
- During design, inferred configuration items without explicit required ownership are advisory readiness items; only explicit required runtime configuration may block for missing owner/default/rollback.
- Treat secrets/certificates/tokens as sensitive; never put values in artifacts.
- Payment/callback/MQ/database changes require environment and rollback verification.

## Output

The output uses schema `codex-configuration-readiness-v1`.

The artifact lists configuration items, owners, environment scope, defaults, rollback decisions, secret-handling rules, blockers, and warnings.

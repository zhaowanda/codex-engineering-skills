---
name: data-security-governor
description: Generate and validate data security review evidence for design, implementation, and release. Use when requirements, designs, diffs, logs, exports, permissions, tenants, payments, secrets, PII, audit, or data retention may be affected.
---

# Data Security Governor

Use this skill during design and release review.

## Command

```bash
python3 skills/core/data-security-governor/scripts/data_security.py \
  design \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --architecture-design artifacts/REQ-001/architecture_design.json \
  --out artifacts/REQ-001/data_security_review.json
```

## Rules

- Block permission/tenant/payment/export/PII/security-sensitive designs without controls.
- Require negative permission cases for permission-sensitive requirements.
- Require masking/no-secret-value rules for logs, configs, exports, and artifacts.

## Output

The output uses schema `codex-data-security-review-v1`.

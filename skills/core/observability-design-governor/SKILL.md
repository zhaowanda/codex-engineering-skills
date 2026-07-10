---
name: observability-design-governor
description: Generate observability design artifacts for logs, metrics, traces, alerts, dashboards, MQ lag, scheduled/manual task monitoring, cache metrics, and post-release validation. Use for backend, frontend, MQ, scheduled task, cross-system, cache, data, or release-sensitive changes.
category: artifact-generator
maturity: expert-gate
stage: design
gate: true
---

# Observability Design Governor

Use this skill during design, before implementation and release evidence.

## Position

Run alongside technical design and before release evidence so runtime checks are planned before code is written.

## Rules

- Generate `observability_design.json`.
- Every changed business flow needs minimum logs, metrics, traces, and alert/waiver decisions.
- MQ, scheduled jobs, manual tasks, cache, and cross-system calls require trigger-specific observability.
- Do not log secrets, tokens, or sensitive payload values.

## Command

```bash
python3 scripts/observability_design.py \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --out artifacts/REQ-001/observability_design.json
```

## Output

The script writes `codex-observability-design-v1` with logs, metrics, traces, alerts, dashboards, and post-release checks.

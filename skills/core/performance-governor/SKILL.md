---
name: performance-governor
description: Generate and validate performance review evidence for design, implementation, and release. Use when requirements or diffs may affect latency, SQL/query count, loops, exports, reports, frontend bundle/runtime, MQ throughput, external calls, or batch processing.
---

# Performance Governor

Use this skill during design and after implementation.

## Position

```text
spec/design/diff
-> performance-governor
-> code-review-gate / release-evidence-binder
```

## Command

```bash
python3 scripts/performance.py \
  design \
  --spec artifacts/REQ-001/spec.json \
  --technical-design artifacts/REQ-001/technical_design.json \
  --architecture-design artifacts/REQ-001/architecture_design.json \
  --out artifacts/REQ-001/performance_design_review.json
```

## Rules

- Block high-risk designs without an evidence plan.
- Require API timing for API changes, query evidence for database changes, browser evidence for UI changes, and throughput evidence for MQ/batch/export changes.
- Treat unknown performance impact as `needs_evidence`.

## Output

The output uses schema `codex-performance-review-v1`.

The artifact reports risk level, affected performance dimensions, required measurements, evidence plan, blockers, warnings, and residual risks.

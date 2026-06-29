---
name: delivery-case-capture
description: Capture a completed or attempted delivery as a reusable anonymized learning case. Use after implementation, review, release, blocked runs, Codex confusion, missed gates, or successful end-to-end delivery to improve future skills and examples.
category: artifact-generator
maturity: deterministic-helper
stage: meta
gate: false
---

# Delivery Case Capture

Use this skill after a delivery run.

## Command

```bash
python3 scripts/capture_case.py \
  --artifact-dir artifacts/REQ-001 \
  --case-id CASE-001 \
  --out cases/CASE-001.json
```

## Rules

- Capture only artifact summaries, not secrets or local-only paths.
- Record what worked, what blocked, and which skill/gate should improve.
- Keep real organization details in a private overlay.

## Output

The output uses schema `codex-delivery-case-v1`.

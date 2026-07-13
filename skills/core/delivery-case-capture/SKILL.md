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

Validate anonymized replay cases:

```bash
python3 scripts/capture_case.py \
  --validate-replay-dir examples/replay-cases
```

## Rules

- Mark synthetic fixtures with `source_type=synthetic`.
- Accept `source_type=anonymized_real_project` only with approved privacy review, reviewer/timestamp, expert and framework decisions, risk level, and a boolean agreement label.
- Capture only artifact summaries, not secrets or local-only paths.
- Record what worked, what blocked, and which skill/gate should improve.
- Keep real organization details in a private overlay.
- Validate replay cases before adding them to examples or CI.
- Replay validation reports complex case count, scenario family coverage, and behavior coverage score.

## Output

The output uses schema `codex-delivery-case-v1`.
Replay validation uses schema `codex-delivery-replay-validation-v1`.

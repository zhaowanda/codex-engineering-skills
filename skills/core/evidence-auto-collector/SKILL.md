---
name: evidence-auto-collector
description: Collect conservative evidence gaps from diff impact and command logs before code review or release. Use after implementation to generate evidence_gap_summary.json from diff impact areas, required evidence, CI/test log status, and missing validation artifacts.
category: extractor-analyzer
maturity: deterministic-helper
stage: post-implementation-review
gate: false
---

# Evidence Auto Collector

Use this skill after implementation evidence exists and before closing review or release readiness.

## Position

```text
diff-impact-analyzer
-> evidence-auto-collector
-> code-review-gate / test-evidence-gate / release-evidence-binder
```

## Rules

- Compare required evidence from diff impact against command logs and artifact presence.
- Report missing evidence conservatively; do not assume a test passed without explicit log or artifact evidence.
- Treat failed, interrupted, or absent command logs as gaps.
- Keep this as an evidence summary, not a replacement for test-evidence-gate or release-evidence-binder.
- Do not mutate artifacts except writing the requested summary output.

## Command

```bash
python3 scripts/evidence_collect.py \
  --diff-impact artifacts/REQ-001/diff_impact.json \
  --command-log test.log \
  --artifact-dir artifacts/REQ-001
```

## Output

The output uses schema `codex-evidence-gap-summary-v1`.

The artifact lists required evidence, found evidence, missing evidence, command-log status, and conservative review gaps.

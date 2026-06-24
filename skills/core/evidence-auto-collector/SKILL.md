---
name: evidence-auto-collector
description: Collect conservative evidence gaps from diff impact and command logs before code review or release. Use after implementation to generate evidence_gap_summary.json from diff impact areas, required evidence, CI/test log status, and missing validation artifacts.
---

# Evidence Auto Collector

## Command

```bash
python3 skills/core/evidence-auto-collector/scripts/evidence_collect.py \
  --diff-impact artifacts/REQ-001/diff_impact.json \
  --command-log test.log \
  --artifact-dir artifacts/REQ-001
```

## Output

The output uses schema `codex-evidence-gap-summary-v1`.

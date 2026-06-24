---
name: baseline-quality-governor
description: Review quality of generated project baseline artifacts. Use after project-baseline-reverser or project-understanding-runner to verify repository overview, modules, API surface, config surface, dependency surface, tests, risks, limitations, and human follow-up points are present.
---

# Baseline Quality Governor

## Command

```bash
python3 skills/core/baseline-quality-governor/scripts/baseline_quality.py \
  --baseline /tmp/baseline.json \
  --out /tmp/baseline_quality.json
```

## Output

The output uses schema `codex-baseline-quality-v1`.

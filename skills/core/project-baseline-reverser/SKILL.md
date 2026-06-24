---
name: project-baseline-reverser
description: Generate baseline project documentation from source structure and Git history. Use when a repository lacks design docs and teams need a private baseline overview, module map, API/route hints, configuration hints, test hints, and recent change summary.
---

# Project Baseline Reverser

Use this skill in private overlays. Do not publish generated real baselines in open core.

## Command

```bash
python3 skills/core/project-baseline-reverser/scripts/reverse_baseline.py \
  --repo /path/to/project \
  --project web-app \
  --out overlay/baseline/web-app.baseline.json
```

## Output

The output uses schema `codex-project-baseline-v1`.

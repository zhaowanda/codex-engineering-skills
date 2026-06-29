---
name: project-baseline-reverser
description: Generate baseline project documentation from source structure and Git history. Use when a repository lacks design docs and teams need a private baseline overview, module map, API/route hints, configuration hints, test hints, and recent change summary.
category: extractor-analyzer
maturity: deterministic-helper
stage: project-understanding
gate: false
---

# Project Baseline Reverser

Use this skill in private overlays. Do not publish generated real baselines in open core.

## Position

```text
repository/api/config/dependency/git analysis
-> project-baseline-reverser
-> baseline-quality-governor
-> requirement/design planning
```

## Rules

- Generate inferred baseline documentation from repository structure and generic analysis artifacts.
- Mark uncertainty and follow-up questions instead of inventing project facts.
- Keep real project baselines in private overlays or temporary artifacts.
- Do not include secrets, private hostnames, customer data, or local absolute paths in shareable baselines.
- Run baseline-quality-governor before relying on generated baselines for design.

## Command

```bash
python3 scripts/reverse_baseline.py \
  --repo /path/to/project \
  --project web-app \
  --out overlay/baseline/web-app.baseline.json
```

## Output

The output uses schema `codex-project-baseline-v1`.

The artifact reports overview, module hints, API/config/dependency references, test hints, recent change summary, risks, limitations, and follow-up items.

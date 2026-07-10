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
- Treat missing repository input, unreadable source, empty analysis artifacts, or privacy-scan hits as blockers.
- Treat inferred modules, incomplete route/config coverage, or stale Git history as warnings that require human confirmation.

## Command

```bash
python3 scripts/reverse_baseline.py \
  --repo /path/to/project \
  --project web-app \
  --out overlay/baseline/web-app.baseline.json
```

## Output

The output uses schema `codex-project-baseline-v1`.

Decision values:

- `pass`: the baseline was generated from readable source evidence and has no blocking privacy or coverage issues.
- `warn`: the baseline is useful but contains uncertainty, stale evidence, or incomplete module/API/config coverage.
- `block`: source input is missing/unreadable, required analysis artifacts are absent, or privacy blockers exist.

The artifact reports overview, module hints, API/config/dependency references, test hints, recent change summary, risks, limitations, warnings, blockers, and follow-up items.

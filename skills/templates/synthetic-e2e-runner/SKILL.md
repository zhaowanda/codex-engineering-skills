---
name: synthetic-e2e-runner
description: Run the synthetic end-to-end example through requirement ingestion, spec normalization, design generation, test design, specialist reviews, delivery plan, and delivery status inspection. Use to validate the open-core workflow without private repositories.
category: template-runner
maturity: template
stage: workflow-orchestration
gate: false
---

# Synthetic E2E Runner

Use this skill to verify the open-core workflow.

## Position

```text
open-core changes
-> synthetic-e2e-runner
-> forward-test-runner / benchmark-governor
-> release readiness
```

## Rules

- Run only synthetic open-core scenarios; do not depend on private repositories.
- Exercise requirement ingestion, spec, design, test design, specialist reviews, delivery plan, and delivery status inspection.
- Exercise implementation follow-up closure across evidence-auto-collector, code-review-gate, and release-evidence-binder.
- Treat failures as release blockers until the expected workflow or scenario fixture is corrected.
- Write outputs to a temporary or explicit artifact directory.
- Do not commit generated scenario outputs unless they are intentional examples.

## Command

```bash
python3 scripts/run_synthetic_e2e.py \
  --out-dir /tmp/codex-synthetic
```

## Output

The output uses schema `codex-synthetic-e2e-run-v1`.

The artifact reports executed stages, generated artifacts, decisions, blockers, and scenario summary. Required scenario cases include blocked delivery, happy design/docs path, frontend evidence path, data-migration blocked path, release blocked path, release happy path, and implementation follow-up release chain path.

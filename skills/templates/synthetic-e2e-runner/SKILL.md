---
name: synthetic-e2e-runner
description: Run the synthetic end-to-end example through requirement ingestion, spec normalization, design generation, test design, specialist reviews, delivery plan, and delivery status inspection. Use to validate the open-core workflow without private repositories.
---

# Synthetic E2E Runner

Use this skill to verify the open-core workflow.

## Command

```bash
python3 skills/templates/synthetic-e2e-runner/scripts/run_synthetic_e2e.py \
  --out-dir /tmp/codex-synthetic
```

## Output

The output uses schema `codex-synthetic-e2e-run-v1`.

---
name: baseline-quality-governor
description: Review quality of generated project baseline artifacts. Use after project-baseline-reverser or project-understanding-runner to verify repository overview, modules, API surface, config surface, dependency surface, tests, risks, limitations, and human follow-up points are present.
category: reviewer
maturity: advisory-review
stage: project-understanding
gate: true
---

# Baseline Quality Governor

Use this skill after generating baseline artifacts and before depending on them for design or implementation planning.

## Position

```text
project-baseline-reverser / project-understanding-runner
-> baseline-quality-governor
-> requirement/design planning
```

## Rules

- Block or warn on missing overview, module hints, API/config/dependency references, test hints, risks, limitations, or follow-up items.
- Treat generated baselines as inferred documentation; require human follow-up when critical facts are absent.
- Do not approve baselines that expose private paths, secrets, real customer data, or proprietary hostnames.
- Prefer warnings for thin but usable baselines and blockers for missing required sections.
- Keep the result conservative so downstream design does not rely on false certainty.

## Command

```bash
python3 scripts/baseline_quality.py \
  --baseline /tmp/baseline.json \
  --out /tmp/baseline_quality.json
```

## Output

The output uses schema `codex-baseline-quality-v1`.

The artifact reports decision, blockers, warnings, checked sections, and follow-up requirements.

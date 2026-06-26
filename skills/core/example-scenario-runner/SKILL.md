---
name: example-scenario-runner
description: Run and validate open-source example scenarios for bugfixes, small features, configuration changes, and frontend changes. Use when demonstrating the framework, adding examples, or forward-testing whether a scenario can produce spec, design, test, traceability, and risk summaries.
---

# Example Scenario Runner

Use this skill to validate example scenarios without private project data.

## Command

```bash
python3 scripts/example_scenario.py \
  --root . \
  --out /tmp/codex-example-scenarios
```

## Rules

- Every scenario needs a `requirement.md`.
- Scenario output must include spec, technical design summary, architecture summary, test summary, traceability summary, and risk summary.
- Examples must remain synthetic and free of private project names or customer data.

## Output

The output uses schema `codex-example-scenario-run-v1`.

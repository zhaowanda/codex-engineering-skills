---
name: benchmark-governor
description: Generate open-core benchmark and quality metric reports for Codex engineering skills. Use when measuring repository health, skill counts, schema counts, prompt counts, scenario counts, test coverage shape, privacy scan status, and skill-health status before release.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# Benchmark Governor

Use this skill before releases or major refactors to track quality signals.

## Command

From an installed skill directory:

```bash
python3 scripts/benchmark.py --root .
```

From this repository root, prefer the unified CLI:

```bash
python3 scripts/codex_eng.py run benchmark --root .
```

## Rules

- Count skills, schemas, prompts, scenarios, and tests.
- Run privacy scan and skill health as subprocesses.
- Report pass/warn/block without mutating repository files.

## Output

The output uses schema `codex-benchmark-report-v1`.

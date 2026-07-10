---
name: diff-impact-analyzer
description: Analyze a git diff and classify engineering impact areas before review, testing, or release. Use after implementation to detect API, database, configuration, permission, performance, frontend, docs, tests, migration, and release risks from changed files and diff content.
category: extractor-analyzer
maturity: deterministic-helper
stage: post-implementation-review
gate: false
---

# Diff Impact Analyzer

Use this skill immediately after implementation and before review, testing, or release evidence selection.

## Position

```text
implementation diff
-> diff-impact-analyzer
-> evidence-auto-collector / change-risk-governor
-> code-review-gate
```

## Rules

- Classify impact areas from changed paths and diff content, including API, database, configuration, permission, performance, frontend, tests, docs, migration, and release.
- Prefer conservative evidence requirements when a change could affect more than one area.
- Treat unknown file types as review evidence, not as safe/no-impact changes.
- Do not inspect live systems or mutate repositories; analyze supplied diff text only.
- Include required evidence so downstream gates can identify missing validation.

## Command

```bash
python3 scripts/diff_impact.py \
  --diff-file /path/to/change.diff \
  --out artifacts/REQ-001/diff_impact.json
```

## Output

The output uses schema `codex-diff-impact-v1`.

Decision values:

- `pass`: the diff was parsed and impact areas/evidence requirements were produced.
- `warn`: the diff was parsed but includes unknown file types, weak signals, or broad impact that needs manual review.
- `block`: the diff is missing, empty, unreadable, or cannot be parsed into changed files.

The artifact includes impact areas, evidence required, warnings, blockers, and review notes inferred from the diff.

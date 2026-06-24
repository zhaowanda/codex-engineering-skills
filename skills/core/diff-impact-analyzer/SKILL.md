---
name: diff-impact-analyzer
description: Analyze a git diff and classify engineering impact areas before review, testing, or release. Use after implementation to detect API, database, configuration, permission, performance, frontend, docs, tests, migration, and release risks from changed files and diff content.
---

# Diff Impact Analyzer

## Command

```bash
python3 skills/core/diff-impact-analyzer/scripts/diff_impact.py \
  --diff-file /path/to/change.diff \
  --out artifacts/REQ-001/diff_impact.json
```

## Output

The output uses schema `codex-diff-impact-v1`.

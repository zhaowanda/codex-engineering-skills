---
name: project-understanding-runner
description: Run a full generic project-understanding pipeline for an existing source repository. Use when onboarding or reverse-engineering a codebase to produce repository analysis, API surface, config surface, dependency surface, git history, code index, baseline, baseline quality, and human baseline documentation in a private overlay or artifact directory.
---

# Project Understanding Runner

Use this skill to analyze a repository before requirement planning or baseline documentation.

## Command

```bash
python3 skills/core/project-understanding-runner/scripts/project_understand.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/project-understanding
```

## Rules

- Write outputs only to the requested `--out` directory.
- Do not commit generated real project outputs to open core.
- Treat all generated baseline docs as heuristic until owner-reviewed.

## Output

The output uses schema `codex-project-understanding-run-v1`.

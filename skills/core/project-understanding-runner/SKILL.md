---
name: project-understanding-runner
description: Run a full generic project-understanding pipeline for an existing source repository. Use when onboarding or reverse-engineering a codebase to produce repository analysis, API surface, config surface, dependency surface, git history, code index, baseline, baseline quality, and human baseline documentation in a private overlay or artifact directory.
category: template-runner
maturity: orchestrator
stage: project-understanding
gate: false
---

# Project Understanding Runner

Use this skill to analyze a repository before requirement planning or baseline documentation.

## Command

```bash
python3 scripts/project_understand.py \
  --repo /path/to/repo \
  --project example \
  --out /tmp/project-understanding
```

To also generate or refresh a private project skill with the standard project-level structure:

```bash
python3 scripts/project_understand.py \
  --repo /path/to/repo \
  --project operate-platform-fe \
  --out /tmp/project-understanding \
  --write-project-skill \
  --overlay-root /path/to/private-overlay \
  --type frontend \
  --default-branch main
```

## Rules

- Write outputs only to the requested `--out` directory.
- Write project skill skeletons only when `--write-project-skill` is explicitly set.
- Project skill output must use `SKILL.md` plus `references/` containing business boundary, feature map, API map, code index, change playbook, contract patterns, validation recipes, pitfalls, project edit gate, and review cases.
- Do not commit generated real project outputs to open core.
- Treat all generated baseline docs as heuristic until owner-reviewed.

## Output

The output uses schema `codex-project-understanding-run-v1`.

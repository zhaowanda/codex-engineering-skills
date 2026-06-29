---
name: project-onboard
description: Onboard a repository into a private overlay by creating a generic project skill skeleton and project registry entry. Use when adding a new project to Codex engineering skills without publishing private indexes or business semantics.
category: artifact-generator
maturity: orchestrator
stage: project-understanding
gate: false
---

# Project Onboard

Use this skill in a private overlay repository.

## Position

```text
new project adoption
-> project-onboard
-> overlay-health
-> project-understanding-runner
```

## Rules

- Create generic project skill skeletons and registry entries in a private overlay only.
- Project skill skeletons must use `SKILL.md` plus `references/` with business boundary, feature map, API map, code index, change playbook, contract patterns, validation recipes, pitfalls, project edit gate, and review cases.
- Do not publish private repository paths, business terms, generated indexes, or baseline docs to open core.
- Require project name, repository path, type, overlay root, and default branch.
- Treat onboarding as registry setup; run project-understanding-runner afterwards for baseline evidence.
- Validate overlay health before team rollout.

## Command

```bash
python3 scripts/project_onboard.py \
  --project web-app \
  --repo /path/to/web-app \
  --type frontend \
  --overlay-root overlay \
  --default-branch main
```

## Output

The output uses schema `codex-project-onboard-v1`.

The artifact reports planned or created registry entries, project skill paths, blockers, warnings, and next commands.

---
name: project-onboard
description: Onboard a repository into a private overlay by creating a generic project skill skeleton and project registry entry. Use when adding a new project to Codex engineering skills without publishing private indexes or business semantics.
---

# Project Onboard

Use this skill in a private overlay repository.

## Command

```bash
python3 skills/core/project-onboard/scripts/project_onboard.py \
  --project web-app \
  --repo /path/to/web-app \
  --type frontend \
  --overlay-root overlay \
  --default-branch main
```

## Output

The output uses schema `codex-project-onboard-v1`.

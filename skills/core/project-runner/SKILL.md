---
name: project-runner
description: Unified project entrypoint for new and legacy project setup. Use when creating or refreshing project-level skills, projects.yaml registration, canonical code indexes, and baseline evidence in a private overlay.
---

# Project Runner

Use this skill as the independent project setup entrypoint before requirement delivery work.

## Modes

```text
new project
-> project-runner new
-> project-onboard
-> code-index-builder
-> overlay-health

legacy project
-> project-runner legacy
-> project-understanding-runner
-> project-onboard
-> code-index-builder
-> baseline artifacts
-> overlay-health
```

## Rules

- Always write project assets to a private overlay, never to open core for real projects.
- Both modes must create or refresh `skills/<project>/SKILL.md`, the standard `references/` files, `projects.yaml`, and `indexes/<project>.code_index.json`.
- Legacy mode must also produce project-understanding artifacts and `baseline/<project>.baseline.json`.
- Project references must be expert-grade: business boundary, feature routing, API contracts, code search protocol, change playbook, validation recipes, pitfalls, edit gate, and review cases.
- Treat generated legacy references as heuristic until owner-reviewed.
- Run overlay health after setup and report blockers.

## Command

```bash
python3 scripts/project_runner.py new \
  --project web-app \
  --repo /path/to/web-app \
  --type frontend \
  --overlay-root /path/to/private-overlay \
  --default-branch main
```

```bash
python3 scripts/project_runner.py legacy \
  --project operate-platform-fe \
  --repo /path/to/operate-platform-fe \
  --type frontend \
  --overlay-root /path/to/private-overlay \
  --default-branch main \
  --out /tmp/operate-platform-fe-understanding
```

## Output

The output uses schema `codex-project-runner-summary-v1`.

The artifact reports mode, project skill paths, registry path, index path, optional baseline path, project-understanding output, overlay health, blockers, and next actions.

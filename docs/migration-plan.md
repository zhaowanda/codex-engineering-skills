# Migration Plan

## Phase 0: Freeze Internal Source

- Do not publish the internal `company` skills directory.
- Treat it as source material only.
- Run privacy scans before copying any file.

## Phase 1: Extract Open Core

Migrate only generic components first:

- delivery state
- Git worktree readiness
- edit readiness
- write guard
- design and architecture review
- code design quality review
- test evidence gate
- frontend acceptance
- release evidence binding

Required changes:

- Replace absolute paths with environment variables or config.
- Replace company names with neutral examples.
- Remove generated project references.
- Add synthetic regression cases.

## Phase 2: Add Templates

Create reusable templates:

- project skill template
- project registry template
- requirement dossier template
- technical design template
- architecture design template
- delivery plan template
- test plan template
- release evidence template

## Phase 3: Private Overlay Adapter

Keep organization-specific content in a private repository:

```text
codex-engineering-overlay/
  projects.yaml
  skills/projects/
  indexes/
  baselines/
  semantic-map.yaml
  golden-cases/
```

The open core reads overlay paths through config.

## Phase 4: Release Gate

Before each public release:

```bash
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
python3 -m pytest tests
```

No release is allowed with private hits.


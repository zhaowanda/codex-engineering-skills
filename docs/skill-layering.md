# Skill Layering

## Layer 1: Open Core

Generic skills and scripts:

- requirement ingestion
- spec governor
- design and architecture reviewer
- delivery state governor
- Git worktree governor
- edit readiness governor
- workspace write guard
- test governor
- code design quality reviewer
- code review gate
- release evidence binder
- frontend acceptance runner

These skills must be configurable and must not depend on real project names.

## Layer 2: Organization Overlay

Private, organization-specific material:

- `projects.yaml`
- project skills
- generated indexes
- contract patterns
- baseline docs
- semantic map
- golden cases based on internal business

This layer lives in a separate private repository.

## Layer 3: Runtime Artifacts

Per-requirement artifacts:

- requirement normalized docs
- delivery_state.json
- technical_design.json
- architecture_design.json
- delivery_plan.json
- git evidence
- edit permits
- review findings
- test evidence
- release evidence

These artifacts should never be committed to the open-source core unless fully synthetic.


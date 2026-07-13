# Changelog

## Unreleased

### Changed

- Upgraded workflow profiles to `codex-workflow-profiles-v2` and the stage registry to `codex-workflow-stages-v3`, adding fail-closed artifact contracts, semantic dependencies, input lineage, cross-repo draft planning, and a mandatory pre-edit write snapshot.
- Upgraded the workflow stage registry to `codex-workflow-stages-v2` with lifecycle phases, explicit dependencies, conditional stages, stale-input detection, and complete implementation/release readiness paths.
- Bound requirement questions and aggregate design reviews to canonical input digests so changed requirements or specialty evidence invalidate stale approvals.

### Compatibility

- `codex-workflow-profiles-v1` and `codex-workflow-stages-v2` remain discoverable as deprecated schema identifiers during migration.
- `codex-workflow-stages-v1` remains listed as a deprecated public schema identifier for compatibility discovery. The shipped stage registry and current validators use v2.

### Migration

- Regenerate workflow artifacts through `auto-runner` so `producer`, `producer_version`, `lineage_schema`, and `input_digests` are populated; existence-only artifacts are no longer implementation or release evidence.
- Replace profile v1/stage v2 registries with profile v2/stage v3 and create `write_guard_snapshot.json` after the edit permit and before implementation.
- Replace a v1 stage registry with v2, add `phase_order`, assign every stage a `phase` and `depends_on`, and declare conditional nodes with `conditional_skill` or `conditional_impacts` before running `skill-health`.
- Regenerate `open_questions.json` and `design_architecture_review.json` to populate their new input digests before relying on implementation readiness.

## 0.1.0

### Release Notes

- Initial open engineering skills framework with generic delivery workflow skills, templates, validation scripts, privacy scan, CI, and synthetic examples.

### Compatibility

- Public open-core repository only. Private organization overlays remain outside this repository.

### Migration

- No migration required for the initial release.

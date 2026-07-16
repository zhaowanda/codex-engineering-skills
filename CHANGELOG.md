# Changelog

## Unreleased

### Changed

- Added structured requirement scope roles, context-aware ambiguity handling, and non-blocking metric questions.
- Added project overlay reference provenance and semantic Harness checks for repository, scope, design, diff, and acceptance consistency.
- Added controlled design-change evidence and AC/entrypoint-bound frontend acceptance.
- Removed settlement-specific semantics from the generic docs renderer and added real-case regression fixtures.
- Made human design rendering applicability-aware so excluded API/data/backend surfaces produce explicit no-change boundaries, frontend-only diagrams avoid invented backend/database nodes, and unchanged referenced APIs satisfy BRK binding without fake per-slice contract changes.
- Added the embedded Agent Runtime with redacted SHA-256 chained events, action authorization, seven lifecycle checkpoints, and generic provider attestations; integrated Runtime-backed Harness checkpoints into auto, edit, pre-push, release, and post-release flow.
- Upgraded workflow profiles to `codex-workflow-profiles-v3`, the stage registry to `codex-workflow-stages-v4`, and Harness checkpoints to `codex-harness-checkpoint-v2`; all 57 registered stages now retain fail-closed semantic validation.
- Added requirement-specific source-location evidence with confirmed, reference-only, and rejected code candidates; spec, design, test, plan, traceability, and auto-runner gates now fail closed instead of promoting broad code-index matches into implementation scope.
- Preserved source-confirmed API contracts in system sequences, rebuilt ordered business process flows from triggers and acceptance outcomes, and required human designs to include both Mermaid flowcharts and sequence diagrams.
- Upgraded the shared artifact validator with typed fields, non-empty evidence, cardinality, constants, patterns, cross-field rules, and adversarial correct-schema/vacuous-evidence rejection for all 45 stages.
- Upgraded workflow lineage to `codex-workflow-artifact-lineage-v2` with semantic artifact digests, deterministic input replacement, command digests, Git context, and permit binding where available.
- Split skill maturity into behavior-backed `expert_contract` and real-project-backed `expert_proven`; no skill or framework receives proven expert status without approved replay calibration.
- Added explicit replay `source_type`, privacy approval, ground truth, agreement metrics, risk-adaptive governance levels, workflow cost metrics, multi-version CI, coverage, lint, typing, security, and property tests.
- Corrected behavior-test scoring to follow module-level script aliases, eliminating false zero-coverage skill ratings without counting unrelated tests.
- Added structured governance waivers with subject/gate binding, owner-approver separation, expiry, compensating controls, immutable audit retention, and conditional-release semantics.
- Hardened provider attestations with supported type, subject, timestamp, verifier, immutable URI, and SHA-256 evidence-digest validation.
- Added per-profile cost budgets, accurate cache reuse/invalidation metrics, and direct Runtime post-release close coverage.
- Made `deliveries/<doc_id>` the canonical unified-docs record, with sanitized managed artifacts, deterministic digests, stale projection detection, cross-doc rejection, and target-doc Git synchronization gates.
- Upgraded workflow profiles to `codex-workflow-profiles-v2` and the stage registry to `codex-workflow-stages-v3`, adding fail-closed artifact contracts, semantic dependencies, input lineage, cross-repo draft planning, and a mandatory pre-edit write snapshot.
- Upgraded the workflow stage registry to `codex-workflow-stages-v2` with lifecycle phases, explicit dependencies, conditional stages, stale-input detection, and complete implementation/release readiness paths.
- Bound requirement questions and aggregate design reviews to canonical input digests so changed requirements or specialty evidence invalidate stale approvals.

### Compatibility

- `codex-workflow-profiles-v2`, `codex-workflow-stages-v3`, and `codex-harness-checkpoint-v1` remain discoverable as deprecated or accepted legacy identifiers; newly generated artifacts use profile v3, stage v4, and Harness v2.
- `codex-workflow-artifact-lineage-v1` remains discoverable for compatibility, but newly generated artifacts use lineage v2.
- `codex-workflow-profiles-v1` and `codex-workflow-stages-v2` remain discoverable as deprecated schema identifiers during migration.
- `codex-workflow-stages-v1` remains listed as a deprecated public schema identifier for compatibility discovery. The shipped stage registry and current validators use v2.

### Migration

- Replace profile v2/stage v3 registries with profile v3/stage v4, regenerate delivery artifacts through `auto-runner`, and create a Runtime session/checkpoint chain. Release flows must provide verified CI, change-management, deployment, and observability attestations.
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

# Skill Catalog

Skills are grouped by delivery stage. Each entry shows maturity and category from `SKILL.md` frontmatter.

## Recommended Minimum Paths

- Bugfix: `requirement-document-ingestor -> spec-governor -> technical-design-governor -> design-architecture-reviewer -> delivery-plan-templates -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`.
- Standard feature: bugfix path plus `architecture-design-governor`, `test-design-governor`, `test-data-governor`, and `traceability-governor` when acceptance coverage or cross-module scope is non-trivial.
- Frontend change: standard feature path plus `frontend-acceptance-runner` and `test-evidence-gate`.
- Data/config/security/performance change: standard feature path plus the matching `configuration-governor`, `data-security-governor`, and `performance-governor`.
- Release readiness: start from `implementation-completion-gate`, then `code-review-gate`, `test-evidence-gate`, environment/UAT/release-change evidence, and `release-evidence-binder`.

Do not run every skill for every task. Use the workflow profile and change-risk evidence to choose the smallest gate set that can block unsafe implementation or release.

## Requirements

- `skills/core/requirement-document-ingestor`: requirement-document-ingestor (deterministic-helper, extractor-analyzer)
- `skills/core/requirement-question-governor`: requirement-question-governor (expert-gate, workflow-gate)
- `skills/core/spec-governor`: spec-governor (expert-gate, workflow-gate)

## Project Understanding

- `skills/core/api-surface-extractor`: api-surface-extractor (deterministic-helper, extractor-analyzer)
- `skills/core/baseline-quality-governor`: baseline-quality-governor (advisory-review, reviewer)
- `skills/core/code-index-builder`: code-index-builder (deterministic-helper, extractor-analyzer)
- `skills/core/code-index-lookup`: code-index-lookup (deterministic-helper, extractor-analyzer)
- `skills/core/config-surface-extractor`: config-surface-extractor (deterministic-helper, extractor-analyzer)
- `skills/core/dependency-surface-analyzer`: dependency-surface-analyzer (deterministic-helper, extractor-analyzer)
- `skills/core/git-history-miner`: git-history-miner (deterministic-helper, extractor-analyzer)
- `skills/core/project-baseline-reverser`: project-baseline-reverser (deterministic-helper, extractor-analyzer)
- `skills/core/project-onboard`: project-onboard (orchestrator, artifact-generator)
- `skills/core/project-runner`: project-runner (orchestrator, template-runner)
- `skills/core/project-understanding-runner`: project-understanding-runner (orchestrator, template-runner)
- `skills/core/repository-analyzer`: repository-analyzer (deterministic-helper, extractor-analyzer)

## Design

- `skills/core/architecture-design-governor`: architecture-design-governor (deterministic-helper, artifact-generator)
- `skills/core/design-architecture-reviewer`: design-architecture-reviewer (expert-gate, workflow-gate)
- `skills/templates/design-doc-templates`: design-doc-templates (template, template-runner)
- `skills/core/technical-design-governor`: technical-design-governor (deterministic-helper, artifact-generator)

## Delivery Planning

- `skills/core/delivery-plan-reviewer`: delivery-plan-reviewer (expert-gate, workflow-gate)
- `skills/templates/delivery-plan-templates`: delivery-plan-templates (template, template-runner)
- `skills/core/delivery-runner`: delivery-runner (orchestrator, template-runner)
- `skills/core/delivery-state-governor`: delivery-state-governor (expert-gate, workflow-gate)

## Edit Readiness

- `skills/core/edit-readiness-governor`: edit-readiness-governor (expert-gate, workflow-gate)
- `skills/core/git-worktree-governor`: git-worktree-governor (expert-gate, workflow-gate)
- `skills/core/workspace-write-guard`: workspace-write-guard (expert-gate, workflow-gate)

## Post Implementation Review

- `skills/core/change-risk-governor`: change-risk-governor (expert-gate, workflow-gate)
- `skills/core/code-design-quality-reviewer`: code-design-quality-reviewer (expert-gate, workflow-gate)
- `skills/core/code-review-gate`: code-review-gate (expert-gate, workflow-gate)
- `skills/core/diff-impact-analyzer`: diff-impact-analyzer (deterministic-helper, extractor-analyzer)
- `skills/core/evidence-auto-collector`: evidence-auto-collector (deterministic-helper, extractor-analyzer)
- `skills/core/implementation-completion-gate`: implementation-completion-gate (expert-gate, workflow-gate)
- `skills/core/post-change-skill-sync`: post-change-skill-sync (deterministic-helper, artifact-generator)
- `skills/core/traceability-governor`: traceability-governor (expert-gate, workflow-gate)

## Testing

- `skills/core/frontend-acceptance-runner`: frontend-acceptance-runner (expert-gate, workflow-gate)
- `skills/core/test-data-governor`: test-data-governor (expert-gate, workflow-gate)
- `skills/core/test-design-governor`: test-design-governor (expert-gate, workflow-gate)
- `skills/core/test-evidence-gate`: test-evidence-gate (expert-gate, workflow-gate)

## Release

- `skills/core/configuration-governor`: configuration-governor (expert-gate, workflow-gate)
- `skills/core/data-security-governor`: data-security-governor (expert-gate, workflow-gate)
- `skills/core/dependency-license-governor`: dependency-license-governor (deterministic-helper, extractor-analyzer)
- `skills/core/environment-promotion-governor`: environment-promotion-governor (expert-gate, release-governor)
- `skills/core/performance-governor`: performance-governor (expert-gate, workflow-gate)
- `skills/core/post-release-observer`: post-release-observer (expert-gate, release-governor)
- `skills/core/release-change-governor`: release-change-governor (expert-gate, release-governor)
- `skills/core/release-evidence-binder`: release-evidence-binder (expert-gate, release-governor)
- `skills/core/release-package-governor`: release-package-governor (deterministic-helper, meta-governor)
- `skills/core/uat-acceptance-governor`: uat-acceptance-governor (expert-gate, release-governor)
- `skills/core/version-release-governor`: version-release-governor (deterministic-helper, meta-governor)

## Documentation

- `skills/templates/artifact-splitter`: artifact-splitter (template, template-runner)
- `skills/core/docs-governor`: docs-governor (deterministic-helper, meta-governor)
- `skills/core/docs-readability-governor`: docs-readability-governor (deterministic-helper, meta-governor)
- `skills/core/docs-site-governor`: docs-site-governor (deterministic-helper, meta-governor)
- `skills/core/human-doc-reviewer`: human-doc-reviewer (deterministic-helper, meta-governor)

## Workflow Orchestration

- `skills/core/auto-runner`: auto-runner (orchestrator, template-runner)
- `skills/core/example-scenario-runner`: example-scenario-runner (orchestrator, template-runner)
- `skills/core/forward-test-runner`: forward-test-runner (orchestrator, template-runner)
- `skills/templates/synthetic-e2e-runner`: synthetic-e2e-runner (template, template-runner)

## Meta

- `skills/core/artifact-schema-governor`: artifact-schema-governor (deterministic-helper, meta-governor)
- `skills/core/benchmark-governor`: benchmark-governor (deterministic-helper, meta-governor)
- `skills/templates/ci-templates`: ci-templates (template, template-runner)
- `skills/core/compatibility-governor`: compatibility-governor (deterministic-helper, meta-governor)
- `skills/core/contribution-governor`: contribution-governor (deterministic-helper, meta-governor)
- `skills/core/delivery-case-capture`: delivery-case-capture (deterministic-helper, artifact-generator)
- `skills/core/deprecation-governor`: deprecation-governor (deterministic-helper, meta-governor)
- `skills/core/framework-config-governor`: framework-config-governor (deterministic-helper, meta-governor)
- `skills/core/issue-pr-governor`: issue-pr-governor (deterministic-helper, meta-governor)
- `skills/core/mcp-integration-governor`: mcp-integration-governor (deterministic-helper, meta-governor)
- `skills/core/overlay-health`: overlay-health (deterministic-helper, meta-governor)
- `skills/core/prompt-effectiveness-governor`: prompt-effectiveness-governor (deterministic-helper, meta-governor)
- `skills/core/prompt-pack-governor`: prompt-pack-governor (deterministic-helper, meta-governor)
- `skills/core/roadmap-governor`: roadmap-governor (deterministic-helper, meta-governor)
- `skills/core/security-policy-governor`: security-policy-governor (deterministic-helper, meta-governor)
- `skills/core/skill-health`: skill-health (deterministic-helper, meta-governor)
- `skills/core/skill-installation-governor`: skill-installation-governor (deterministic-helper, meta-governor)

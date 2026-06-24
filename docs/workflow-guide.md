# Workflow Guide

## Main Flow

```text
requirement source
-> project-understanding-runner when existing repositories or legacy code must be understood
-> requirement-document-ingestor
-> spec-governor
-> requirement-question-governor
-> technical-design-governor
-> architecture-design-governor
-> test-design-governor
-> configuration/performance/data-security governors
-> design-architecture-reviewer
-> delivery-plan-templates
-> git-worktree-governor
-> edit-readiness-governor
-> implementation
-> implementation-completion-gate
-> diff-impact-analyzer
-> traceability-governor
-> change-risk-governor
-> evidence-auto-collector
-> workspace-write-guard
-> code-design-quality-reviewer
-> code-review-gate
-> test-evidence-gate
-> frontend-acceptance-runner when UI changed
-> environment-promotion-governor
-> uat-acceptance-governor
-> release-change-governor
-> release-evidence-binder
-> post-release-observer
-> delivery-case-capture
-> issue-pr-governor / version-release-governor / dependency-license-governor for open-source publication
-> artifact-schema-governor / prompt-pack-governor / skill-installation-governor for distribution readiness
-> contribution-governor / security-policy-governor / docs-site-governor / compatibility-governor / mcp-integration-governor / benchmark-governor for open-source maturity
-> release-package-governor / deprecation-governor / roadmap-governor / docs-readability-governor / prompt-effectiveness-governor for release evolution
-> skill-health / forward-test-runner before publishing
```

## Coding Is Allowed Only When

- Spec is ready and required open questions are closed.
- Technical and architecture designs exist.
- Design review passes or explicitly allows continuation.
- Delivery plan identifies modify repos, file scope, tests, release order, and rollback.
- Git worktree is on a non-default working branch.
- Edit permit exists and file scope is narrow.

## Release Is Allowed Only When

- Implementation completion evidence exists.
- Write guard audit is clean.
- Code review gate approves or has accepted residual risks.
- Test evidence gate passes.
- Frontend acceptance passes when UI changed.
- Environment promotion, UAT acceptance, and release change evidence are complete.
- Configuration, performance, and data-security blockers are resolved.
- Release evidence binder returns `go` or explicitly accepted `conditional_go`.
- Post-release observation is required before the release is closed.

## Open Core And Private Overlay

Open core contains generic skills, scripts, templates, tests, and synthetic examples.

Private overlay contains:

- real project registry
- project-specific skills
- generated code indexes
- baseline docs
- project understanding dossiers
- API/config/dependency/git surfaces from real repositories
- delivery docs
- business semantic maps
- real cases

Never publish private overlay artifacts in this repository.

## MCP Integration Guidance

MCP usage must stay inside the current task boundary and must produce evidence that can be reviewed without relying on private tool state. Browser or Chrome DevTools MCP evidence is expected for UI acceptance, GitHub MCP evidence is useful for issue and PR workflows, and filesystem or knowledge MCP outputs must avoid private overlays. If an MCP server is unavailable, fall back to repository scripts, local artifacts, or manual evidence and record the fallback in the gate output.

## Token Strategy

- Use `delivery-runner` first to identify the current stage.
- Use `project-understanding-runner` once per relevant repository before long requirement design or legacy maintenance.
- Use `code-index-lookup` before reading source broadly.
- Reuse generated repository/API/config/dependency/baseline JSON as compact context instead of re-reading whole repositories.
- Use generated JSON artifacts as compact context.
- Keep human-readable documents separate from machine gate JSON.
- Run `traceability-governor` to prove acceptance coverage and task/file scope before implementation or release.
- Run `change-risk-governor` after diff analysis to choose lightweight, standard, heavy, or critical controls.
- Capture repeated blockers with `delivery-case-capture`.
- Run `issue-pr-governor`, `version-release-governor`, and `dependency-license-governor` before open-source release or external contribution merge.
- Run `example-scenario-runner` to verify bugfix, feature, configuration, and frontend example paths remain demonstrable.
- Run `artifact-schema-governor` after adding gate scripts so machine-readable contracts stay discoverable.
- Run `prompt-pack-governor` before publishing user-facing prompt examples.
- Run `skill-installation-governor` to verify installability before release.
- Run contribution, security policy, docs-site, compatibility, MCP integration, and benchmark governors before external releases.
- Run release package, deprecation, roadmap, docs readability, and prompt effectiveness governors before tagging or publishing open-core releases.
- Run `skill-health` and `forward-test-runner` before publishing open-core changes.

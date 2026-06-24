# Workflow Guide

## Main Flow

```text
requirement source
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
- delivery docs
- business semantic maps
- real cases

Never publish private overlay artifacts in this repository.

## Token Strategy

- Use `delivery-runner` first to identify the current stage.
- Use `code-index-lookup` before reading source broadly.
- Use generated JSON artifacts as compact context.
- Keep human-readable documents separate from machine gate JSON.
- Run `traceability-governor` to prove acceptance coverage and task/file scope before implementation or release.
- Run `change-risk-governor` after diff analysis to choose lightweight, standard, heavy, or critical controls.
- Capture repeated blockers with `delivery-case-capture`.
- Run `skill-health` and `forward-test-runner` before publishing open-core changes.

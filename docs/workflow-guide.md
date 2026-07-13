# Workflow Guide

## Main Flow

```text
requirement source
-> project-understanding-runner when existing repositories or legacy code must be understood
-> requirement-document-ingestor
-> spec-governor
-> requirement-question-governor (required questions block design approval and implementation)
-> domain-model-governor
-> architecture-framing-governor
-> UI/API/data/observability specialty design governors as applicable
-> technical-design-governor
-> architecture-design-governor
-> design-architecture-reviewer
-> test-design-governor
-> test-data-governor
-> configuration/performance/data-security design governors
-> delivery-plan-templates
-> cross-repo-planner before delivery plan review when more than one repository or contract boundary is involved
-> traceability-governor initial pass after delivery_plan exists to prove requirement/design/test/task coverage
-> delivery-plan-reviewer
-> git-worktree-governor
-> edit-readiness-governor
-> implementation
-> implementation-completion-gate
-> diff-impact-analyzer
-> traceability-governor post-implementation pass to bind requirements to diff, tests, and release evidence
-> change-risk-governor
-> evidence-auto-collector
-> workspace-write-guard
-> code-design-quality-reviewer
-> code-review-gate
-> frontend-acceptance-runner when UI changed
-> test-evidence-gate
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

## Standard Design-First Profile

Use this profile for normal feature work before any Git or edit readiness step:

```text
requirement-document-ingestor
-> spec-governor
-> requirement-question-governor
-> domain-model-governor
-> architecture-framing-governor
-> specialty design governors as applicable
-> technical-design-governor
-> architecture-design-governor
-> design-architecture-reviewer
-> test-design-governor
-> test-data-governor
-> delivery-plan-templates
-> cross-repo-planner before delivery-plan-reviewer when repository order or contract compatibility can change the plan
-> traceability-governor initial pass
-> delivery-plan-reviewer
```

## Workflow Profiles

| Scenario | Required path |
| --- | --- |
| `bugfix` | `requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> design-architecture-reviewer -> test-design-governor -> test-data-governor -> delivery-plan-templates -> traceability-governor initial pass -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; API/data/UI/cross-repo/MQ/async/scheduler/task/job/cache/integration/permission/security signals elevate above the light path. |
| `small_feature` | Standard design-first profile, then Git/edit readiness gates. |
| `frontend_change` | Standard design-first profile plus pre-technical `ui-ue-design-governor`, `ui-ue-reviewer`, and `frontend-implementation-planner`. Real `frontend-acceptance-runner -> test-evidence-gate` evidence is collected after implementation, before release. UI/UE design must name concrete user entry surfaces and cover loading, empty, success, validation error, permission denied, and dependency error states. |
| `cross_repo_api` | API/cross-repo contract profile with project understanding, pre-technical API/observability design, delivery plan, cross-repo execution graph/readiness before delivery plan review, initial traceability, and release evidence gates. |
| `data_migration` | Standard design-first profile plus configuration, security, and performance design gates before design approval; release gates run only after implementation evidence exists. |
| `release_readiness` | `implementation-completion-gate -> post-change-skill-sync -> code-review-gate -> frontend-acceptance-runner when UI changed -> test-evidence-gate -> post-implementation traceability -> environment-promotion-governor -> uat-acceptance-governor -> release-change-governor -> release-evidence-binder`. |

Profiles are machine-validated contracts, not only documentation. Each profile declares required skills, expected artifacts, required gate artifacts, accepted decisions, and readiness fields. Stage order and next commands are defined in `config/workflow-stages.example.yaml`.
Profile `notes` are human guidance only; executable readiness is defined by `required_gate_artifacts` and the stage registry.
Profile `artifact_steps` declare profile-specific artifact generation or inspection commands. `auto-runner` interprets these steps instead of hard-coding frontend, data, or release behavior.

Traceability is intentionally two-pass. The initial pass (`traceability_matrix.json`) runs before implementation and proves that requirements, design, tests, and delivery tasks line up. The post-implementation pass (`post_implementation_traceability_matrix.json`) runs after changes exist and binds requirements to diff, test evidence, review evidence, and release evidence.

## Coding Is Allowed Only When

- Spec is ready and `open_questions.json` has `decision=pass`; draft design artifacts may be generated for discussion, but unresolved required questions block design approval and implementation.
- `technical_design.json` and `architecture_design.json` exist.
- `design_architecture_review.json` has `decision=pass` or `approved` and `readiness_gate.implementation_allowed=true`.
- `delivery_plan_review.json` has `decision=pass` and `readiness_gate.implementation_allowed=true`.
- Delivery plan identifies modify repos, file scope, tests, release order, and rollback.
- Git worktree evidence proves the target repo fetched the remote and updated the base branch with `pull --ff-only`.
- Git worktree is on a non-default working branch.
- `edit_permit.json` exists, is ready, and binds a narrow file scope.
- `write_guard_snapshot.json` exists after the permit when direct edits are used.
- `write_guard_audit.json` passes before commit, push, or release evidence.

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

For local development, install open-core skills from this repository into the Codex skills directory:

```bash
python3 scripts/codex_eng.py run sync-local-skills --force
```

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
- Run initial `traceability-governor` to prove acceptance coverage and task/file scope before implementation, then run post-implementation traceability after diff/test/release evidence exists.
- Run `change-risk-governor` after diff analysis to choose lightweight, standard, heavy, or critical controls.
- Capture repeated blockers with `delivery-case-capture`.
- Run `issue-pr-governor`, `version-release-governor`, and `dependency-license-governor` before open-source release or external contribution merge.
- Run `example-scenario-runner` to verify bugfix, feature, configuration, and frontend example paths remain demonstrable.
- Run `synthetic-e2e-runner` or `forward-test-runner` to verify blocked, happy-path, frontend, data-migration, and release-readiness scenarios.
- Run `artifact-schema-governor` after adding gate scripts so machine-readable contracts stay discoverable.
- Run `prompt-pack-governor` before publishing user-facing prompt examples.
- Run `skill-installation-governor` to verify installability before release.
- Run contribution, security policy, docs-site, compatibility, MCP integration, and benchmark governors before external releases.
- Run release package, deprecation, roadmap, docs readability, and prompt effectiveness governors before tagging or publishing open-core releases.
- Run `skill-health` and `forward-test-runner` before publishing open-core changes.

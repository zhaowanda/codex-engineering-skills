# Workflow Guide

## Main Flow

```text
requirement source
-> Agent Runtime session and intake checkpoint
-> requirement-document-ingestor
-> project-understanding-runner when existing repositories or legacy code must be understood
-> Harness source-location checkpoint when repository evidence is present
-> spec-governor
-> requirement-question-governor (required questions block design approval and implementation)
-> domain-model-governor
-> architecture-framing-governor
-> UI/API/data/observability specialty design governors as applicable
-> technical-design-governor
-> architecture-design-governor
-> configuration/performance/data-security design governors as applicable
-> delivery-plan-templates draft when more than one repository or contract boundary is involved
-> cross-repo-planner when applicable
-> test-design-governor using the complete design and cross-repo evidence
-> design-architecture-reviewer with test design and cross-repo readiness
-> test-data-governor
-> final delivery plan
-> traceability-governor initial pass after delivery_plan exists to prove requirement/design/test/task coverage
-> delivery-plan-reviewer
-> Agent Runtime design checkpoint
-> Harness design checkpoint
-> git-worktree-governor
-> edit-readiness-governor
-> Agent Runtime pre-edit checkpoint
-> workspace-write-guard snapshot
-> implementation
-> implementation-completion-gate
-> post-change-skill-sync
-> workspace-write-guard audit
-> diff-impact-analyzer
-> Agent Runtime post-implementation checkpoint
-> Harness post-implementation checkpoint for plan-to-diff alignment
-> traceability-governor post-implementation pass to bind requirements to diff, tests, and release evidence
-> change-risk-governor
-> evidence-auto-collector
-> code-design-quality-reviewer
-> frontend-acceptance-runner when UI changed
-> test-evidence-gate
-> code-review-gate aggregate approval
-> Agent Runtime pre-push checkpoint
-> Harness pre-push checkpoint
-> environment-promotion-governor
-> uat-acceptance-governor
-> release-change-governor
-> Agent Runtime release checkpoint with provider attestations
-> release-evidence-binder
-> post-release-observer
-> Agent Runtime close checkpoint
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
-> configuration/performance/data-security design governors as applicable
-> delivery plan draft and cross-repo readiness when repository order or contract compatibility can change the plan
-> test-design-governor
-> final design review with test design and cross-repo readiness
-> test-data-governor and final delivery plan
-> traceability-governor initial pass
-> delivery-plan-reviewer
```

<!-- GENERATED:WORKFLOW_PROFILES:START -->
## Workflow Profiles

| Scenario | Required path |
| --- | --- |
| `small_feature-lite` | `requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> architecture-design-governor -> design-architecture-reviewer -> test-design-governor -> delivery-plan-templates -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; use only for a small single-scope request with no declared API, UI, cross-repo, data, permission, or runtime integration impact. |
| `small_feature` | Standard design-first profile, then Git/edit readiness gates. |
| `bugfix` | `requirement-document-ingestor -> spec-governor -> requirement-question-governor -> technical-design-governor -> test-design-governor -> design-architecture-reviewer -> test-data-governor -> delivery-plan-templates -> traceability-governor initial pass -> delivery-plan-reviewer -> git-worktree-governor -> edit-readiness-governor`; API/data/UI/cross-repo/MQ/async/scheduler/task/job/cache/integration/permission/security signals elevate above the light path. |
| `frontend_change` | Standard design-first profile plus pre-technical `ui-ue-design-governor`, `ui-ue-reviewer`, and `frontend-implementation-planner`. Real `frontend-acceptance-runner -> test-evidence-gate` evidence is collected after implementation, before release. UI/UE design must name concrete user entry surfaces and cover loading, empty, success, validation error, permission denied, and dependency error states. |
| `cross_repo_api` | API/cross-repo contract profile with project understanding, pre-technical API/observability design, delivery plan, cross-repo execution graph/readiness before delivery plan review, initial traceability, and release evidence gates. |
| `data_migration` | Standard design-first profile plus configuration, security, and performance design gates before design approval; release gates run only after implementation evidence exists. |
| `release_readiness` | `implementation-completion-gate -> post-change-skill-sync -> workspace-write-guard audit -> diff-impact-analyzer -> change-risk-governor -> evidence-auto-collector -> code-design-quality-reviewer -> frontend-acceptance-runner when UI changed -> test-evidence-gate -> post-implementation traceability -> code-review-gate -> environment-promotion-governor -> uat-acceptance-governor -> release-change-governor -> release-evidence-binder`. |

Profiles use schema `codex-workflow-profiles-v3` and select scenario skills and impacts; they do not define execution order. Stage order, schemas, required fields, decisions, dependencies, lineage inputs, Runtime gates, conditional skills, conditional impacts, and next commands are defined by the `codex-workflow-stages-v4` registry in `config/workflow-stages.example.yaml`.
<!-- GENERATED:WORKFLOW_PROFILES:END -->

Harness policy uses `config/harness-policy.example.yaml`. The lifecycle checkpoints are source location, design, post implementation, and pre-push. They are normal DAG stages with lineage, so changing a code index, confirmed source file, design, plan, diff, test result, or review evidence invalidates the applicable downstream checkpoint.

Agent Runtime policy uses `config/agent-runtime-policy.example.yaml`. Runtime owns session identity, redacted append-only tool events, action authorization, checkpoint evidence, and provider attestation validation. Harness owns semantic quality checks over delivery artifacts. Runtime checkpoint roots are historical event-chain members, while checkpoint lineage binds immutable business evidence; appending a later event therefore does not make an earlier accepted checkpoint stale.
Profile `notes` are human guidance only; executable readiness is defined by `required_gate_artifacts` and the stage registry.
Profile `artifact_steps` declare profile-specific artifact generation or inspection commands. `auto-runner` interprets these steps instead of hard-coding frontend, data, or release behavior.

`open_questions.json` is bound to the canonical current spec through `spec_digest`. Regeneration preserves answers only for unchanged stable question IDs, records answer provenance, and marks questions removed by the new spec as non-blocking `obsolete`. A digest mismatch blocks profile readiness even when every required question in the old artifact was answered.

Use `python3 scripts/codex_eng.py clarify --artifact-dir <delivery-dir>` to answer open questions sequentially in a terminal. Required answers cannot be blank; every completed response is immediately persisted with actor and timestamp provenance to `open_questions.json` and `clarification_answers.md`. The command fails closed without a TTY. On the next same-directory auto run, confirmed answers are merged into `requirement.clarified.txt` and used for source-location and Spec regeneration.

The question stage may consume a blocked `spec.json` as a draft to break the clarification cycle. That exception does not complete the Spec stage: requirement text or project evidence must be updated and Spec must be regenerated before any design stage can pass.

Every applicable artifact records its direct input digests. Updating an input recursively invalidates downstream readiness. Cross-repo work uses a draft plan before test design and aggregate design review, so testability is reviewed against `cross_repo_readiness.json` before final test data and delivery artifacts are generated.

The unified delivery docs repository uses `deliveries/<doc_id>` as its canonical record. Requirement input, generated artifacts, evidence, and Runtime records live below that directory; human documents, machine bundles, raw compatibility copies, and indexes are generated projections bound to the canonical artifact digest. Pre-push validation rejects stale projections, cross-document artifacts, uncommitted target-doc changes, or a docs branch that is not synchronized with its upstream.

The shared artifact contract also declares `evidence_fields` and optional typed field constraints. Correct schema and an accepted decision are insufficient when evidence is empty, has the wrong type, violates cardinality, or conflicts with a readiness constant. Lineage v2 binds the semantic artifact digest, deterministic direct inputs, producer version, command digest, Git context, and permit when available.

Profiles declare `governance_level` as `light`, `standard`, `heavy`, or `critical`, plus observable step/artifact/duration budgets. Auto-run summaries distinguish cache reuse, invalidation, forced regeneration, first-run misses, and non-applicable steps; budget breaches are warnings for calibration rather than fabricated pass evidence.

Exceptions use `codex-governance-waiver-v1`. A waiver is accepted only when it binds the subject and affected gates, records risk and compensating controls, has distinct owner and approver identities, remains unexpired, and points to immutable retained audit evidence. Valid waivers produce conditional release signals and never erase an upstream blocker.

Regulated release policy overlays can require structured approval identities, separation of duties, immutable audit retention, and provider evidence from CI, change management, deployment, and observability systems. Provider credentials and organization-specific adapters remain in the private overlay; open-core artifacts retain only provider names and evidence identifiers or URLs.

Provider attestations must identify the provider, evidence, subject, immutable evidence URI, issue time, verification result, and accepted status. Optional expiry timestamps must be timezone-aware and unexpired. Release Runtime advancement requires one verified attestation from each of `ci`, `change_management`, `deployment`, and `observability`.

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
- `harness_validation.json` passes before docs/Git readiness.
- `runtime/checkpoints/pre_edit.json` passes and records edit authorization.
- `delivery-runner` reports `can_implement=true`, `next_stage=implementation`, `next_action_type=ready_to_implement`, and no blockers for the selected profile.

## Release Is Allowed Only When

- Implementation completion evidence exists.
- Post-change evidence passes; when project skill sync candidates exist, `project_skill_index_sync.json` must prove the project-level skill index was updated or carry an explicit owner-reviewed waiver.
- `harness/post_implementation.json` proves actual changed files stay within the reviewed delivery-plan scope.
- `harness/pre_push.json` proves post-change, traceability, tests, review, skill-index sync, and commit binding are current.
- A pre-commit or pre-push failure caused by a missing Codex script path is a hook installation defect, not grounds for `--no-verify`. Repair only the affected hook with `workspace-write-guard/scripts/install_pre_commit.py --repo <repo> --hook pre-push`, then rerun the same Git operation with hooks enabled.
- `runtime/checkpoints/post_implementation.json`, `runtime/checkpoints/pre_push.json`, and `runtime/checkpoints/release.json` pass; release carries all four required provider attestations.
- Write guard audit is clean.
- Code review gate approves or has accepted residual risks.
- Test evidence gate passes.
- Frontend acceptance passes when UI changed.
- Environment promotion, UAT acceptance, and release change evidence are complete.
- Configuration, performance, and data-security blockers are resolved.
- Release evidence binder returns `go`; `conditional_go` remains blocked until a separate time-bounded waiver contract with owner and expiry is implemented.
- `delivery-runner --profile release_readiness` reports `can_release=true`, `next_action_type=ready_to_release`, and no blockers.
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

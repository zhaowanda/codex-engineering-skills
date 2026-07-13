# Codex Engineering Skills

Open engineering-delivery skill framework for Codex-style coding agents.

This repository is the open-source shell of an internal engineering delivery system. It provides reusable workflow structure, gates, scripts, and templates for requirement intake, design-first delivery, Git readiness, implementation control, review, testing, release evidence, and post-change learning.

It intentionally does not include private company project skills, generated code indexes, internal baseline documents, proprietary business terms, local absolute paths, or real customer artifacts.

## Goals

- Make AI-assisted engineering follow a traditional delivery lifecycle.
- Prevent coding before requirement, design, Git branch, and edit-permit readiness.
- Keep human-readable docs and machine-readable gates separate.
- Reduce interaction rounds by producing the next required gate and command.
- Provide reusable checks for design depth, code quality, tests, frontend acceptance, release evidence, and documentation quality.

## Non-Goals

- This is not a replacement for project CI, code owners, security review, or production approval.
- This repository should not contain organization-specific source indexes or baseline docs.
- This repository should not contain real secrets, internal hostnames, customer data, or proprietary project names.

## Repository Layout

```text
codex-engineering-skills/
  install.py
  config/
    framework.example.yaml
    private-patterns.example.yaml
  docs/
    architecture.md
    getting-started.md
    skill-catalog.md
    migration-plan.md
    open-source-boundary.md
    open-source-roadmap.md
    workflow-guide.md
  examples/
    project-registry/
      projects.example.yaml
    scenarios/
      bugfix/
      small-feature/
      config-change/
      frontend-change/
    synthetic-e2e-case/
      requirement.md
  scripts/
    codex_eng.py
    privacy_scan.py
    skill_health.py
    sync_local_skills.py
  prompts/
    one-line-request.md
    long-prd.md
    bugfix.md
    code-review.md
    release-readiness.md
    low-rework-implementation.md
  skills/
    core/
      <skill-name>/
        SKILL.md
        scripts/
    templates/
      <template-skill-name>/
        SKILL.md
        scripts/
  tests/
    test_*.py
```

## Skill Layers

- `core`: generic engineering workflow skills and scripts safe for open-source use.
- `templates`: skeleton project skills, docs templates, and registry examples.
- `organization overlay`: private repository layer that contains project registry, project-specific skills, generated indexes, baseline docs, and business semantics.

Do not publish the organization overlay.

## First Safety Check

Run before publishing:

```bash
python3 scripts/privacy_scan.py \
  --root . \
  --patterns config/private-patterns.example.yaml
```

The scanner blocks absolute user paths, private project names, internal workspace names, and configurable sensitive patterns.

## Start Here

Preview setup and local checks:

```bash
python3 scripts/codex_eng.py setup
```

Install and check the local skill set:

```bash
python3 scripts/codex_eng.py setup --force
```

List supported development scenarios:

```bash
python3 scripts/codex_eng.py scenarios --format markdown
```

Run the safe one-command workflow:

```bash
python3 scripts/codex_eng.py docs configure \
  --docs-root /tmp/codex-delivery-docs \
  --git-url git@github.com:your-org/delivery-docs.git

python3 scripts/codex_eng.py docs init \
  --docs-root /tmp/codex-delivery-docs \
  --doc-id REQ-DEMO

python3 scripts/codex_eng.py auto \
  --input examples/synthetic-e2e-case/requirement.md \
  --doc-id REQ-DEMO \
  --out /tmp/codex-auto-demo \
  --format human
```

Configure the delivery docs repository once per workspace. Later requirements reuse the configured docs repo by `doc_id`; pass `--docs-root` only when overriding the workspace default.

The auto runner ingests the requirement, verifies delivery docs readiness, selects a workflow profile, generates spec/domain/framing/specialty-design/technical-design/architecture-design/test/test-data/plan artifacts, inspects workflow status, and reports the next safe action. It does not edit business code, create Git branches, commit, deploy, or release.

Check the next safe action later:

```bash
python3 scripts/codex_eng.py next --artifact-dir /tmp/codex-auto-demo
```

Preview implementation scope before editing:

```bash
python3 scripts/codex_eng.py implement --artifact-dir /tmp/codex-auto-demo
```

Implementation dry-run blocks until the full pre-edit gate is ready: delivery docs manifest, `technical_design.json`, `architecture_design.json`, `design_architecture_review.json` with `implementation_allowed=true`, `delivery_plan_review.json` with `implementation_allowed=true`, Git evidence that fetched the remote and updated the base branch with `pull --ff-only`, and `edit_permit.json`. For direct edits, create `write_guard_snapshot.json` after the permit and require `write_guard_audit.json` before commit or push.

Default target: `${CODEX_HOME:-~/.codex}/skills/codex-engineering-skills`.

Install this repository into the local Codex skills directory:

```bash
python3 scripts/codex_eng.py run sync-local-skills --dry-run
python3 scripts/codex_eng.py run sync-local-skills --force
```

This copies open-core skills from the repository into `${CODEX_HOME:-~/.codex}/skills/codex-engineering-skills`.

If this open-source repository should be the only non-system local skill source, archive legacy local skill folders:

```bash
python3 scripts/codex_eng.py run sync-local-skills --prune-legacy --dry-run
python3 scripts/codex_eng.py run sync-local-skills --prune-legacy --force
```

- [Getting Started](docs/getting-started.md): run the synthetic workflow end to end.
- [Workflow Guide](docs/workflow-guide.md): understand the gates, allowed implementation conditions, release conditions, and private overlay boundary.
- [Skill Catalog](docs/skill-catalog.md): browse skills by delivery stage, maturity, and category.
- [Skill Assessment](docs/skill-assessment.md): review current skill quality level, orchestration fit, and optimization backlog.
- [Scenario Guide](docs/scenario-guide.md): browse synthetic example scenarios.
- [FAQ](docs/faq.md): common open-core usage and boundary questions.
- [Deprecation Policy](docs/deprecation-policy.md): public contract deprecation and migration rules.

Unified CLI:

```bash
python3 scripts/codex_eng.py auto --input examples/synthetic-e2e-case/requirement.md
python3 scripts/codex_eng.py synthetic-e2e --out-dir /tmp/codex-synthetic
python3 scripts/codex_eng.py inspect --artifact-dir /tmp/codex-synthetic
```

Framework validation:

```bash
python3 -m pytest -q
python3 -m compileall -q scripts skills tests
python3 scripts/skill_health.py --root .
```

Analyze an existing repository before requirement design:

```bash
python3 scripts/codex_eng.py project legacy \
  --repo examples/synthetic-repos/basic-web-service \
  --project basic-web-service \
  --type backend \
  --git-url git@example.com:org/basic-web-service.git \
  --overlay-root /tmp/codex-private-overlay \
  --out /tmp/codex-project-understanding
```

The project runner creates the project skill, `projects.yaml`, canonical code index, and legacy baseline outputs in a private overlay. For new projects, use `python3 scripts/codex_eng.py project new ...` to create the same project skill and registry structure before implementation work.

## Available Core Skills

Every skill declares `category`, `maturity`, `stage`, and `gate` in `SKILL.md` frontmatter. See the [Skill Catalog](docs/skill-catalog.md) for the stage-grouped taxonomy; the list below is a compact inventory.

- `skills/core/auto-runner`: one-command safe workflow runner that ingests a requirement, optionally understands a repository, generates artifacts, inspects status, and reports the next action.
- `skills/core/requirement-document-ingestor`: ingests Markdown, text, JSON, copied docs, and PDF placeholders into normalized requirement text and source manifest.
- `skills/core/spec-governor`: normalizes one-line requests or long requirement text into `spec.json` with scope, acceptance criteria, rules, risks, and open questions.
- `skills/core/requirement-question-governor`: generates and validates focused open questions so unresolved ambiguity blocks design or implementation instead of being guessed.
- `skills/core/domain-model-governor`: models business objects, lifecycle, state machine, invariants, rules, triggers, and clarification gaps before architecture framing or technical design.
- `skills/core/architecture-framing-governor`: frames owner system, repo boundaries, new-service decisions, provider/consumer direction, entrypoints, dependency degree, release order, and rollback before technical design.
- `skills/core/technical-design-governor`: generates a structured technical design draft with process flow, module decomposition, data flow, API/UI behavior, options, tests, and traceability.
- `skills/core/architecture-design-governor`: generates an architecture design draft with boundaries, repo responsibilities, contracts, data ownership, deployment, rollback, and option comparison.
- `skills/core/ui-ue-design-governor`: generates first-class UI/UE design artifacts for user goals, entry actions, flows, state matrices, accessibility, and browser evidence.
- `skills/core/ui-ue-reviewer`: reviews UI/UE artifacts so shallow entrypoints, missing states, unclear contracts, and weak evidence block frontend implementation.
- `skills/core/frontend-implementation-planner`: maps UI/UE design into frontend routes, components, API dependencies, state handling, permission behavior, and acceptance evidence.
- `skills/core/api-contract-governor`: generates API contract design artifacts for endpoint naming, request/response, errors, permissions, idempotency, compatibility, and consumers.
- `skills/core/data-model-governor`: generates data model design artifacts for tables, fields, indexes, migrations, history data, consistency, rollback, and test data.
- `skills/core/observability-design-governor`: designs logs, metrics, traces, alerts, dashboards, MQ/task/cache signals, and post-release validation.
- `skills/core/cross-repo-planner`: generates a cross-repository execution graph, readiness gate, and release plan for multi-repo requirements with provider/consumer dependencies.
- `skills/core/delivery-plan-reviewer`: reviews delivery plans for executable task depth, narrow file scope, evidence mapping, rollback controls, and unresolved gates before Git or edit readiness.
- `skills/core/delivery-runner`: one-command status inspector that reports current stage, blockers, next command, and whether implementation/release is allowed.
- `skills/core/test-design-governor`: generates and validates test design before implementation, including acceptance mapping, regression, integration, permission, and frontend scope.
- `skills/core/test-data-governor`: generates and validates `test_data_plan.json` so test cases have synthetic/anonymized fixtures, accounts, roles, cleanup, and privacy controls before execution.
- `skills/core/configuration-governor`: detects and gates runtime configuration readiness for database, MQ, email, SMS, payment, callbacks, secrets, certificates, and feature flags.
- `skills/core/performance-governor`: creates performance review evidence plans for API timing, SQL/query impact, exports, frontend runtime, MQ throughput, and batch work.
- `skills/core/data-security-governor`: creates data security review evidence for PII, permissions, tenants, payment data, secrets, exports, logs, and audit-sensitive changes.
- `skills/core/code-index-builder`: builds compact private project indexes from source files, symbols, routes, and keywords to reduce broad source searches.
- `skills/core/code-index-lookup`: queries compact project indexes before reading large codebases.
- `skills/core/project-runner`: unified private-overlay project entrypoint for new and legacy repositories, generating project skills, `projects.yaml`, canonical indexes, and legacy baselines.
- `skills/core/project-onboard`: creates a private overlay project skill skeleton and project registry entry for a new repository.
- `skills/core/docs-governor`: initializes and validates a long-lived delivery docs repository layout that separates human docs from machine artifacts.
- `skills/core/project-baseline-reverser`: generates inferred baseline documentation from source structure and Git history for projects without existing docs.
- `skills/core/repository-analyzer`: summarizes repository structure, languages, entrypoints, build files, config files, tests, CI, and framework hints before design or maintenance work.
- `skills/core/api-surface-extractor`: extracts API, route, controller, and frontend route hints from common frameworks without requiring private project knowledge.
- `skills/core/config-surface-extractor`: extracts configuration files and key names only, avoiding values, for environment and runtime readiness analysis.
- `skills/core/dependency-surface-analyzer`: summarizes dependency manifests, ecosystems, and likely build/test commands.
- `skills/core/git-history-miner`: mines recent Git history, hot files, and hot directories without exposing author emails.
- `skills/core/baseline-quality-governor`: checks whether inferred baseline documentation has enough overview, module, API, config, dependency, test, risk, and follow-up coverage.
- `skills/core/project-understanding-runner`: orchestrates repository, API, config, dependency, Git, code index, baseline, and baseline-quality analysis into one project understanding dossier.
- `skills/core/delivery-case-capture`: captures completed, blocked, or confusing delivery runs as anonymized reusable learning cases.
- `skills/core/diff-impact-analyzer`: classifies git diff impact areas and required evidence across API, database, configuration, permission, performance, frontend, tests, and docs.
- `skills/core/traceability-governor`: builds requirement-to-delivery traceability across acceptance criteria, design, tasks, implementation, tests, and evidence.
- `skills/core/change-risk-governor`: classifies change risk and required controls from diff impact, cross-repo scope, security, performance, and configuration signals.
- `skills/core/issue-pr-governor`: validates open-source issue and PR templates for linked issue, scope, tests, evidence, risk, rollback, and release notes.
- `skills/core/version-release-governor`: checks SemVer, `pyproject.toml`, `CHANGELOG.md`, release notes, breaking changes, and migration notes before tagging.
- `skills/core/dependency-license-governor`: checks open-source license presence, project license metadata, dependency manifests, and high-risk license signals.
- `skills/core/example-scenario-runner`: runs synthetic bugfix, small feature, configuration, and frontend scenarios to demonstrate framework behavior.
- `skills/core/skill-installation-governor`: installs or dry-runs open-core skills into a local Codex skills directory with overwrite-safe validation.
- `skills/core/artifact-schema-governor`: inventories emitted JSON artifact schemas and flags missing or unstable machine-readable contracts.
- `skills/core/prompt-pack-governor`: validates reusable prompt packs for one-line requests, long PRDs, bugfixes, code review, release readiness, and low-rework implementation.
- `skills/core/contribution-governor`: validates CONTRIBUTING, contribution support files, PR expectations, tests, privacy scan, and skill-health guidance.
- `skills/core/security-policy-governor`: validates SECURITY policy coverage for vulnerability reporting, supported versions, private data, secrets, dependency review, and response process.
- `skills/core/docs-site-governor`: generates and validates public docs navigation, skill catalog, scenario guide, FAQ, and local Markdown links.
- `skills/core/compatibility-governor`: reviews skill, schema, and CLI command compatibility risks against a base Git ref.
- `skills/core/mcp-integration-governor`: validates generic MCP guidance and evidence expectations for browser, GitHub, and workflow integrations.
- `skills/core/benchmark-governor`: generates quality metrics for skills, scripts, schemas, prompts, scenarios, tests, privacy, and skill health.
- `skills/core/release-package-governor`: validates release package readiness, required paths, version consistency, changelog entry, and dry-run manifest.
- `skills/core/deprecation-governor`: validates deprecation policy, migration guidance, compatibility window, and removal rules.
- `skills/core/roadmap-governor`: checks roadmap consistency against actual skills, README, and generated skill catalog.
- `skills/core/docs-readability-governor`: checks public documentation readability, onboarding path, boundary explanation, maintenance commands, and local path safety.
- `skills/core/prompt-effectiveness-governor`: evaluates prompt packs for design-first behavior, boundaries, Git readiness, tests, evidence, stop conditions, and token/source-reading controls.
- `skills/core/implementation-completion-gate`: validates real diff evidence, delivery-plan scope alignment, changed files, and implementation summary before review/testing.
- `skills/core/post-change-skill-sync`: generates post-change implementation evidence after edits, including changed files, validation needs, baseline candidates, project-skill sync candidates, and docs binding status.
- `skills/core/evidence-auto-collector`: creates conservative evidence gap summaries from diff impact and command logs.
- `skills/core/environment-promotion-governor`: validates DEV/SIT/UAT/PRE/PROD promotion evidence, entry/exit criteria, configuration differences, approvers, and rollback readiness.
- `skills/core/uat-acceptance-governor`: validates business UAT scope, acceptors, cases, known issues, and signoff.
- `skills/core/release-change-governor`: validates release window, change ticket, approvers, release order, rollback owner, rollback plan, and post-release checks.
- `skills/core/post-release-observer`: validates post-release observation metrics, logs, alerts, business checks, incidents, and close evidence.
- `skills/core/skill-health`: checks open-core skill repository health, frontmatter, script compilation, README listing, roadmap, and tests.
- `skills/core/overlay-health`: checks private overlay registry, project skills, indexes, baseline docs, and docs manifests.
- `skills/core/human-doc-reviewer`: reviews human-readable docs for clarity, decisions, option comparison, risks, evidence, rollback, local paths, and secrets.
- `skills/core/forward-test-runner`: runs synthetic forward tests and validates expected schemas and decisions.
- `skills/core/delivery-state-governor`: canonical `delivery_state.json` state board for delivery lanes, gate advancement, blockers, and implementation/release validation.
- `skills/core/git-worktree-governor`: generic Git readiness gate that fetches latest base branches, creates feature branches, prepares all modify repositories from a delivery plan, and blocks edits on default branches or dirty worktrees.
- `skills/core/edit-readiness-governor`: final pre-edit gate that verifies doc id, design evidence, delivery state, Git branch readiness, file scope, and short-lived edit permits before writes.
- `skills/core/workspace-write-guard`: write-layer backstop that snapshots and audits Git workspace changes against edit permits, including direct edits that bypass command wrappers.
- `skills/core/framework-config-governor`: validates framework configuration and private overlay wiring before teams run the workflow on real repositories.
- `skills/core/design-architecture-reviewer`: design-depth gate that scores technical and architecture designs for requirement coverage, flows, data, APIs, UI/UX, option comparison, security, performance, boundaries, rollback, observability, and testability.
- `skills/core/code-design-quality-reviewer`: first-pass diff reviewer for cohesion, coupling, responsibility boundaries, API contracts, permission, transaction, performance, security, configuration, testability, and maintainability risks.
- `skills/core/code-review-gate`: aggregate review gate that combines write audit, code review, design quality, security, performance, test, CI, frontend, configuration, and evidence-gap results into approve/request_changes/block.
- `skills/core/test-evidence-gate`: validates real test execution, CI command evidence, test-data linkage, blocker coverage, and optional frontend acceptance before release evidence binding.
- `skills/core/frontend-acceptance-runner`: generates and validates browser acceptance evidence for UI pages, routes, forms, lists, exports, permissions, responsive behavior, console errors, and network failures.
- `skills/core/release-evidence-binder`: binds design, implementation, review, test, CI, frontend, configuration, environment, UAT, rollback, and post-release evidence into a final go/conditional_go/no_go release gate.
- `skills/templates/design-doc-templates`: renderer for technical and architecture design JSON templates plus a synthetic example that passes the design reviewer.
- `skills/templates/delivery-plan-templates`: renderer for delivery plans that map reviewed designs into repo roles, tasks, allowed file scope, validation evidence, release order, and rollback order.
- `skills/templates/artifact-splitter`: separates machine-readable gate JSON from human-readable Markdown summaries with local path sanitization by default.
- `skills/templates/ci-templates`: renders GitHub Actions or GitLab CI validation templates for compile, test, and privacy scan checks.
- `skills/templates/synthetic-e2e-runner`: runs the synthetic example through the open-core workflow and emits an execution summary.

## Open-Source Maintenance Checks

```bash
python3 skills/core/issue-pr-governor/scripts/issue_pr.py --root .
python3 skills/core/issue-pr-governor/scripts/issue_pr.py --pr-file .github/pull_request_template.md
python3 skills/core/version-release-governor/scripts/version_release.py --root . --version 0.1.0
python3 skills/core/dependency-license-governor/scripts/dependency_license.py --root .
python3 skills/core/example-scenario-runner/scripts/example_scenario.py --root . --out /tmp/codex-example-scenarios
python3 skills/core/artifact-schema-governor/scripts/artifact_schema.py --root .
python3 skills/core/prompt-pack-governor/scripts/prompt_pack.py --root . --validate
python3 scripts/skill_health.py --root .
python3 skills/core/skill-installation-governor/scripts/install_skills.py --source . --target /tmp/codex-skills --dry-run
python3 scripts/codex_eng.py run contribution --root .
python3 scripts/codex_eng.py run security-policy --root .
python3 scripts/codex_eng.py run docs-site --root .
python3 scripts/codex_eng.py run compatibility --root .
python3 scripts/codex_eng.py run mcp-integration --root .
python3 scripts/codex_eng.py run benchmark --root .
python3 scripts/codex_eng.py run release-package --root .
python3 scripts/codex_eng.py run deprecation --root .
python3 scripts/codex_eng.py run roadmap --root .
python3 scripts/codex_eng.py run docs-readability --root .
python3 scripts/codex_eng.py run prompt-effectiveness --root .
python3 scripts/codex_eng.py run sync-local-skills --dry-run
```

## Migration Strategy

Do not copy an internal `.codex/skills/company` directory into this repository wholesale.

Use the migration plan:

1. Extract generic scripts and remove absolute paths.
2. Replace organization names with neutral examples.
3. Move project-specific knowledge into private overlays.
4. Add regression tests before publishing each migrated component.
5. Run privacy scan and framework tests before release.

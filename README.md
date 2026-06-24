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
  config/
    framework.example.yaml
    private-patterns.example.yaml
  docs/
    architecture.md
    getting-started.md
    migration-plan.md
    skill-layering.md
    open-source-boundary.md
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
  prompts/
    one-line-request.md
    long-prd.md
    bugfix.md
    code-review.md
    release-readiness.md
    low-rework-implementation.md
  skills/
    core/
    templates/
  tests/
    test_privacy_scan.py
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

- [Getting Started](docs/getting-started.md): run the synthetic workflow end to end.
- [Workflow Guide](docs/workflow-guide.md): understand the gates, allowed implementation conditions, release conditions, and private overlay boundary.

Unified CLI:

```bash
python3 scripts/codex_eng.py synthetic-e2e --out-dir /tmp/codex-synthetic
python3 scripts/codex_eng.py inspect --artifact-dir /tmp/codex-synthetic
```

## Available Core Skills

- `skills/core/requirement-document-ingestor`: ingests Markdown, text, JSON, copied docs, and PDF placeholders into normalized requirement text and source manifest.
- `skills/core/spec-governor`: normalizes one-line requests or long requirement text into `spec.json` with scope, acceptance criteria, rules, risks, and open questions.
- `skills/core/requirement-question-governor`: generates and validates focused open questions so unresolved ambiguity blocks design or implementation instead of being guessed.
- `skills/core/technical-design-governor`: generates a structured technical design draft with process flow, module decomposition, data flow, API/UI behavior, options, tests, and traceability.
- `skills/core/architecture-design-governor`: generates an architecture design draft with boundaries, repo responsibilities, contracts, data ownership, deployment, rollback, and option comparison.
- `skills/core/delivery-runner`: one-command status inspector that reports current stage, blockers, next command, and whether implementation/release is allowed.
- `skills/core/test-design-governor`: generates and validates test design before implementation, including acceptance mapping, regression, integration, permission, and frontend scope.
- `skills/core/configuration-governor`: detects and gates runtime configuration readiness for database, MQ, email, SMS, payment, callbacks, secrets, certificates, and feature flags.
- `skills/core/performance-governor`: creates performance review evidence plans for API timing, SQL/query impact, exports, frontend runtime, MQ throughput, and batch work.
- `skills/core/data-security-governor`: creates data security review evidence for PII, permissions, tenants, payment data, secrets, exports, logs, and audit-sensitive changes.
- `skills/core/code-index-builder`: builds compact private project indexes from source files, symbols, routes, and keywords to reduce broad source searches.
- `skills/core/code-index-lookup`: queries compact project indexes before reading large codebases.
- `skills/core/project-onboard`: creates a private overlay project skill skeleton and project registry entry for a new repository.
- `skills/core/docs-governor`: initializes and validates a long-lived delivery docs repository layout that separates human docs from machine artifacts.
- `skills/core/project-baseline-reverser`: generates inferred baseline documentation from source structure and Git history for projects without existing docs.
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
- `skills/core/implementation-completion-gate`: validates real diff evidence, delivery-plan scope alignment, changed files, and implementation summary before review/testing.
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
- `skills/core/test-evidence-gate`: validates real test execution, CI command evidence, blocker coverage, and optional frontend acceptance before release evidence binding.
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
python3 skills/core/skill-installation-governor/scripts/install_skills.py --source . --target /tmp/codex-skills --dry-run
```

## Migration Strategy

Do not copy an internal `.codex/skills/company` directory into this repository wholesale.

Use the migration plan:

1. Extract generic scripts and remove absolute paths.
2. Replace organization names with neutral examples.
3. Move project-specific knowledge into private overlays.
4. Add regression tests before publishing each migrated component.
5. Run privacy scan and framework tests before release.

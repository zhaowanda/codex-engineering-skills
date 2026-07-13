# Skill Assessment

This assessment records the current quality level, orchestration fit, and remaining optimization work for the open-core skill set.

## Summary

Current level: **advanced fail-closed framework with runtime-validated orchestration; expert status awaits real-project calibration**.

The health report separates skill contract quality, DAG integrity, gate semantics, synthetic path reality, and real-project calibration. Static skill quality no longer makes the whole framework `expert`; at least three privacy-reviewed anonymized real-project replays across three scenario families are required for that level.

The repository has a coherent delivery framework rather than a loose prompt collection. Skills are grouped by lifecycle stage, most commands produce machine-readable artifacts, and the main gates expose `decision`, `blockers`, and readiness fields. The unified CLI, workflow profiles, scenario catalog, forward tests, privacy scan, and health checks make the system operable as a repeatable workflow.

The main remaining risk is real-project calibration. The lifecycle now has a phase-ordered DAG, explicit dependencies, conditional specialty stages, stale-input detection, and executable implementation/release happy paths. Private overlays, project-specific skills, code indexes, baseline docs, and team release policies remain necessary before complex production changes.

## Expert Assessment Model

`skill_health` reports five independent framework dimensions:

- `skill_contract_quality`: per-skill documentation, scripts, and direct test contract quality; only expert/advisory gates may receive an expert-level skill classification.
- `dag_integrity`: lifecycle phases, dependencies, cycles, artifact uniqueness, and profile-to-stage registration.
- `gate_semantics`: required gates accept only non-blocking decisions and enforce declared readiness fields.
- `happy_blocked_path_reality`: `skill_health` actually runs the synthetic E2E suite and proves both blocking behavior and genuine implementation/release readiness.
- `real_project_calibration`: privacy-reviewed anonymized real-project replay evidence, kept distinct from synthetic fixtures.

The whole framework is `expert` only when its weighted score is at least 90 and at least three validated replays across three scenario families declare `source_type=anonymized_real_project`. High static skill scores or synthetic happy paths alone cannot award framework-level expert status.

## Verified Baseline

- `skill_health`: pass, 84 skills, 33 expert-level gate contracts and 84 advanced-or-better contracts; framework score 80 (`advanced`).
- Framework dimensions: skill contract quality 100, DAG integrity 100, gate semantics 100, happy/blocked path reality 100, real-project calibration 0.
- Runtime assessment: all 45 workflow stages reject placeholder artifacts and all 7 synthetic blocked/happy paths pass.
- `benchmark`: pass, 84 skills, 89 scripts, 133 schemas, 6 prompts, 8 documented and forward-tested scenarios, and 7 validated synthetic replay cases.
- `pytest`: pass, 388 tests.
- `compileall`: pass for `scripts`, `skills`, and `tests`.
- `privacy_scan`: pass, no hits.
- `forward_test`: pass for all 8 scenarios and all 7 synthetic blocked/happy-path cases, including genuine implementation and release readiness.
- Real-project replay count: 0; framework-level expert status remains intentionally unavailable.

## Orchestration Assessment

The default orchestration is reasonable:

- `auto-runner` is the right entrypoint for requirement intake because it creates artifacts and reports the next safe action without editing business code.
- `workflow-profiles.example.yaml` covers the main delivery lanes and uses required gate artifacts instead of relying on prose-only instructions.
- Auto summaries expose `workflow_strictness`, effective controls, light-tier gate overrides, strictness gate gaps, and elevation impacts; scenario docs now distinguish light bugfix effective gates from standard pre-edit gates.
- Profile composition is useful for mixed-impact work, such as bugfix plus UI/API/data impact.
- `delivery-runner` and `implement_dry_run.py` provide a practical stop point before edits.

The orchestration can become heavy for very small fixes. That is acceptable for high-control environments, but teams should use the smallest matching profile and avoid forcing every skill into every task.

## Skill Levels By Area

| Area | Level | Notes |
| --- | --- | --- |
| Requirements | A | Strong intake, normalization, ambiguity gating, business-object extraction, rule-conflict blocking, implicit constraints, inferred-acceptance downgrading, and impact-driven expert questions; domain semantics still need real-project calibration. |
| Project understanding | A | Generic analyzers now share `decision`, `blockers`, `warnings`, `confidence`, and `confidence_details`; real value still depends on private overlay quality. |
| Design | A | Strong technical/architecture design and design review gates. |
| Delivery planning | A | Good plan rendering, review, state, and next-action inspection. |
| Git/edit readiness | A | Strong controls for branch readiness, edit permits, and write audits. |
| Post-implementation review | A- | Good diff impact, design quality, risk, evidence, and review aggregation. |
| Testing/frontend acceptance | A | Test design, test data planning, execution evidence, browser evidence, screenshot proof, console errors, network failures, route, and viewport/device evidence are linked; real project runs still need actual browser artifacts. |
| Release | A | Broad release evidence coverage with environment policy, release window, approver, rollback owner, and post-release checks enforced by release evidence binding. |
| Documentation | A- | Good docs separation and quality checks; needs discipline in delivery docs repos. |
| Meta/open-source governance | A | Strong health, privacy, replay validation, schema, compatibility, release, prompt, and roadmap checks. |

## Skill Disposition

Keep all current skills. None need immediate deletion.

Recommended actions:

- **Keep as core gates**: `spec-governor`, `requirement-question-governor`, `design-architecture-reviewer`, `delivery-plan-reviewer`, `git-worktree-governor`, `edit-readiness-governor`, `workspace-write-guard`, `implementation-completion-gate`, `code-review-gate`, `test-data-governor`, `test-evidence-gate`, `release-evidence-binder`.
- **Keep as generators/orchestrators**: `auto-runner`, `delivery-runner`, `project-runner`, `project-understanding-runner`, `technical-design-governor`, `architecture-design-governor`, `test-design-governor`, template skills.
- **Keep as situational specialists**: frontend, configuration, data security, performance, UAT, environment, release change, post-release, dependency, compatibility, MCP, and open-source governance skills.
- **Strengthen through real-project use**: project understanding, frontend acceptance, data migration, and release readiness paths.

## Scenario Coverage

| Scenario | Current Fit | Optimization Need |
| --- | --- | --- |
| One-line request | Strong | Keep default path lightweight. |
| Long PRD | Strong | Ensure open questions block design when material. |
| Bugfix | Strong | Light by default only when no material impact is detected; API/UI impacts elevate to standard, and data/database/security/permission/configuration/performance/release impacts elevate to regulated. |
| Frontend change | Strong | Browser evidence now supports screenshot, route, viewport/device, console, and network proof, with a clean fixture for validation; real project runs still need actual browser artifacts. |
| Cross-repo API | Strong | Requires fresh project registry, index, and baseline docs in private overlay. |
| Data migration | Good | Needs real-project rollback, data security, and performance evidence calibration. |
| Release readiness | Strong | Built-in and regulated release-policy examples cover environment aliases, approval roles, tickets, and observation metrics. |
| Code review | Strong | Best after write guard, diff impact, tests, and CI evidence exist. |

## Optimization Backlog

1. Keep command documentation dual-mode: installed skill commands use `python3 scripts/...`; repository-root examples should use `python3 scripts/codex_eng.py ...`.
2. Keep test data plans linked to execution evidence: `test_design.json` declares data refs, `test_data_plan.json` defines synthetic/anonymized data, and `test_execution_evidence.json` records dataset usage.
3. Convert the now-validated anonymized replay skeleton fixtures into captured real-project replay cases after private data review.
4. Tune `overlay-health-policy.example.yaml` thresholds and required project-skill sections per team once generated indexes and baseline docs are in regular use.
5. Validate automatic bugfix elevation against several real bugfix deliveries before making the impact rules stricter or looser.
6. Expand frontend acceptance examples with captured browser artifacts from real applications.
7. Add team-specific release-policy overlays derived from `release-policy.regulated.example.yaml`.
8. Calibrate requirement conflict and implicit-constraint rules with real PRDs from each business domain.

## Operating Guidance

Use `auto` first for new requirements, then follow `next` and `implement` dry-run output. For maintenance of this repository, run:

```bash
python3 -m pytest -q
python3 -m compileall -q scripts skills tests
python3 scripts/privacy_scan.py --root . --patterns config/private-patterns.example.yaml
python3 scripts/skill_health.py --root .
python3 scripts/codex_eng.py run benchmark --root .
python3 skills/core/forward-test-runner/scripts/forward_test.py --root .
python3 scripts/codex_eng.py setup --format json
```

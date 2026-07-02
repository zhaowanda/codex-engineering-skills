# Skill Assessment

This assessment records the current quality level, orchestration fit, and remaining optimization work for the open-core skill set.

## Summary

Current level: **expert-ready for controlled real-project rollout**.

The repository has a coherent delivery framework rather than a loose prompt collection. Skills are grouped by lifecycle stage, most commands produce machine-readable artifacts, and the main gates expose `decision`, `blockers`, and readiness fields. The unified CLI, workflow profiles, scenario catalog, forward tests, privacy scan, and health checks make the system operable as a repeatable workflow.

The main remaining risk is not basic correctness. It is real-project calibration: private overlays, project-specific skills, code indexes, baseline docs, and team release policies must be added before the framework can reliably handle complex production changes.

## Verified Baseline

- `skill_health`: pass, 75 skills, 75 expert-level scores.
- `benchmark`: pass, 75 skills, 77 scripts, 113 schemas, 6 prompts, 8 documented and forward-tested scenarios.
- `pytest`: pass, 229 tests.
- `compileall`: pass for `scripts`, `skills`, and `tests`.
- `privacy_scan`: pass, no hits.
- `forward_test`: pass for one-line request, long PRD, bugfix, frontend change, cross-repo API, data migration, release readiness, and code review.

## Orchestration Assessment

The default orchestration is reasonable:

- `auto-runner` is the right entrypoint for requirement intake because it creates artifacts and reports the next safe action without editing business code.
- `workflow-profiles.example.yaml` covers the main delivery lanes and uses required gate artifacts instead of relying on prose-only instructions.
- Profile composition is useful for mixed-impact work, such as bugfix plus UI/API/data impact.
- `delivery-runner` and `implement_dry_run.py` provide a practical stop point before edits.

The orchestration can become heavy for very small fixes. That is acceptable for high-control environments, but teams should use the smallest matching profile and avoid forcing every skill into every task.

## Skill Levels By Area

| Area | Level | Notes |
| --- | --- | --- |
| Requirements | A | Strong intake, normalization, and ambiguity gating. |
| Project understanding | A- | Good generic analyzers; real value depends on private overlay quality. |
| Design | A | Strong technical/architecture design and design review gates. |
| Delivery planning | A | Good plan rendering, review, state, and next-action inspection. |
| Git/edit readiness | A | Strong controls for branch readiness, edit permits, and write audits. |
| Post-implementation review | A- | Good diff impact, design quality, risk, evidence, and review aggregation. |
| Testing/frontend acceptance | A | Test design, test data planning, execution evidence, and browser evidence are now linked; browser evidence still depends on real project integration. |
| Release | A- | Broad release evidence coverage; production policy must be supplied by teams. |
| Documentation | A- | Good docs separation and quality checks; needs discipline in delivery docs repos. |
| Meta/open-source governance | A | Strong health, privacy, schema, compatibility, release, prompt, and roadmap checks. |

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
| Bugfix | Strong | Avoid adding release-only gates unless risk requires them. |
| Frontend change | Strong | Bind generated acceptance templates to real browser evidence. |
| Cross-repo API | Good | Requires project registry and baseline docs in private overlay. |
| Data migration | Good | Needs real rollback, data security, and environment evidence. |
| Release readiness | Good | Needs team-specific approval and production policy. |
| Code review | Strong | Best after write guard, diff impact, tests, and CI evidence exist. |

## Optimization Backlog

1. Keep command documentation dual-mode: installed skill commands use `python3 scripts/...`; repository-root examples should use `python3 scripts/codex_eng.py ...`.
2. Keep test data plans linked to execution evidence: `test_design.json` declares data refs, `test_data_plan.json` defines synthetic/anonymized data, and `test_execution_evidence.json` records dataset usage.
3. Add real-project replay cases for backend API, frontend UI, data/config-sensitive change, and release readiness.
4. Add profile strictness tiers, such as `light`, `standard`, and `regulated`, so tiny changes are not over-gated.
5. Add more assertions around profile composition for mixed-impact changes.
6. Expand frontend acceptance examples with real browser artifacts where possible.
7. Add private overlay quality gates for project skills, generated indexes, and baseline docs before real delivery.

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

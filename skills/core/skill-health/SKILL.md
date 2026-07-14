---
name: skill-health
description: Check open-core skill repository health. Use before release or contribution review to validate SKILL.md frontmatter, script presence, Python compilation, README skill listing, roadmap status, tests, and privacy scan readiness.
category: meta-governor
maturity: deterministic-helper
stage: meta
gate: false
---

# Skill Health

Use this skill before contribution review, release packaging, or large skill refactors.

## Position

```text
skill/documentation changes
-> skill-health
-> benchmark-governor
-> release-package-governor
```

## Rules

- Every skill must have valid frontmatter with `name` and `description`.
- Every skill must declare `category`, `maturity`, `stage`, and `gate`.
- `expert-gate` skills must declare `gate=true` and have direct test coverage.
- Template, helper, extractor, and orchestrator skills must not be marked as `expert-gate`.
- Gate skills must document or emit `schema`, `decision`, and `blockers`.
- Skill names should align with folder paths.
- Skills should be listed in README by path, folder, or name.
- Python scripts under skill folders must compile.
- Tests must exist for the repository.
- Roadmap should contain completion markers for release tracking.
- Validate workflow v3 schemas, required fields, semantic dependencies, profile applicability, and the default fail-closed validator.
- Execute the synthetic E2E suite and reject correct-schema artifacts with vacuous semantic evidence for every registered stage; source-string presence is not runtime evidence.
- Reserve `expert_contract` for expert/advisory gates with positive and negative behavior tests. Reserve `expert_proven` for privacy-reviewed real-project calibration. Helpers, orchestrators, and templates may score advanced but not expert.
- Set real-project calibration to zero until replay validation confirms privacy-reviewed `source_type=anonymized_real_project` cases with ground truth. Framework expert requires at least three valid replays across three scenario families and at least 80% expert/framework agreement.

## Command

```bash
python3 scripts/skill_health.py \
  --root .
```

## Output

The output uses schema `codex-skill-health-v1`.

The artifact reports skill count, blockers, warnings, runtime workflow assessment, five-dimensional framework assessment, and a pass/warn/block decision.

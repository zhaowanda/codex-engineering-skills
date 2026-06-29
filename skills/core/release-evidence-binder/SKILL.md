---
name: release-evidence-binder
description: Bind delivery evidence into a final release gate report. Use before release approval to aggregate design review, implementation completion, write audit, code review, test evidence, CI, frontend acceptance, configuration readiness, environment promotion, UAT, rollback, and post-release checks into go, conditional_go, or no_go.
category: release-governor
maturity: expert-gate
stage: release
gate: true
---

# Release Evidence Binder

Use this skill after implementation, review, and test evidence exist.

## Position

```text
design review
-> implementation completion
-> code review gate
-> test evidence gate
-> release-evidence-binder
-> release change approval
-> post-release observation
```

## Required Evidence For Code Changes

- `delivery_plan.json`
- `design_architecture_review.json`
- `implementation_completion_gate.json`
- `write_guard_audit.json`
- `code_review_gate.json`
- `test_evidence_gate.json`
- `ci_execution_evidence.json`
- rollback evidence from `delivery_plan.json`, `release_change.json`, or `post_release_checks.json`
- post-release checks from `post_release_checks.json`, `release_change.json`, or `delivery_plan.json`

Optional but binding when present:

- `frontend_acceptance.json`
- `configuration_readiness.json`
- `environment_promotion.json`
- `uat_acceptance.json`
- `release_change.json`
- `data_security_review.json`
- `performance_diff_review.json`
- `performance_design_review.json`
- `evidence_gap_summary.json`

## Decision Rules

- `no_go` if any required evidence is missing for code changes.
- `no_go` if any gate has `block`, `blocked`, `no_go`, `fail`, or failed command evidence.
- `no_go` if design, security, performance, code review, test, CI, frontend, configuration, environment, or UAT evidence contains release blockers.
- `no_go` if rollback or post-release checks are missing.
- `conditional_go` if no blockers remain but warnings, accepted risks, unresolved non-blocking evidence gaps, or manual waivers exist.
- `go` only when required evidence exists, all gates pass, rollback is concrete, and post-release checks are defined.

## Command

```bash
python3 scripts/bind_release.py \
  --artifact-dir artifacts/review \
  --out artifacts/review/release_gate.json
```

For documentation-only changes:

```bash
python3 scripts/bind_release.py \
  --artifact-dir artifacts/review \
  --change-type docs \
  --out artifacts/review/release_gate.json
```

## Output

The output uses schema `codex-release-gate-v1`.

Decision values:

- `go`
- `conditional_go`
- `no_go`

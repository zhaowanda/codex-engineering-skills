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
- `post_change_implementation_report.json`
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

## Rules

- Bind every required and optional evidence artifact that is relevant to the change type.
- Do not downgrade missing required evidence to a warning for code changes.
- Treat failed commands, blocked gates, unresolved high-risk findings, missing rollback, or missing post-release checks as blockers.
- Treat unclosed `implementation_completion_gate.evidence_followups` as blockers for code/config releases.
- Require `evidence_gap_summary.json` when implementation follow-ups exist, so release binding can prove required evidence was not skipped.
- Require `evidence_gap_summary.implementation_followup_requirements` to cover every surface declared by `implementation_completion_gate.evidence_followups`; an empty pass summary is not sufficient.
- Require surface-specific artifacts for implementation follow-ups when the surface has a dedicated gate; for example `frontend_acceptance` requires `frontend_acceptance.json`, and `configuration` requires `configuration_readiness.json`.
- Treat accepted risks, manual waivers, non-blocking warnings, or incomplete optional evidence as conditional release signals.
- Keep documentation-only release binding separate from code-change release binding.

## Decision Rules

- `no_go` if any required evidence is missing for code changes.
- `no_go` if any gate has `block`, `blocked`, `no_go`, `fail`, or failed command evidence.
- `no_go` if design, security, performance, code review, test, CI, frontend, configuration, environment, or UAT evidence contains release blockers.
- `no_go` if implementation follow-ups are declared but no evidence-gap summary or required surface-specific evidence closes them.
- `no_go` if the evidence-gap summary does not explicitly include the declared implementation follow-up surfaces.
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

The artifact reports bound evidence, missing evidence, warnings, blockers, accepted risks, rollback readiness, post-release readiness, and the final decision.

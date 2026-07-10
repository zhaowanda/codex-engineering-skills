---
name: evidence-auto-collector
description: Collect conservative evidence gaps from diff impact and command logs before code review or release. Use after implementation to generate evidence_gap_summary.json from diff impact areas, required evidence, CI/test log status, and missing validation artifacts.
category: extractor-analyzer
maturity: deterministic-helper
stage: post-implementation-review
gate: false
---

# Evidence Auto Collector

Use this skill after implementation evidence exists and before closing review or release readiness.

## Position

```text
diff-impact-analyzer
-> evidence-auto-collector
-> code-review-gate / test-evidence-gate / release-evidence-binder
```

## Rules

- Compare required evidence from diff impact against command logs and artifact presence.
- Read `implementation_completion_gate.json` when present and convert `evidence_followups` into concrete evidence requirements.
- Report missing evidence conservatively; do not assume a test passed without explicit log or artifact evidence.
- Treat failed, interrupted, or absent command logs as gaps.
- Keep this as an evidence summary, not a replacement for test-evidence-gate or release-evidence-binder.
- Do not mutate artifacts except writing the requested summary output.

## Command

```bash
python3 scripts/evidence_collect.py \
  --diff-impact artifacts/REQ-001/diff_impact.json \
  --command-log test.log \
  --artifact-dir artifacts/REQ-001
```

When `artifacts/REQ-001/implementation_completion_gate.json` contains `evidence_followups`, the collector expects matching artifacts such as `test_execution_evidence.json`, `frontend_acceptance.json`, `configuration_readiness.json`, or `post_release_observation.json` depending on the declared surface.

## Output

The output uses schema `codex-evidence-gap-summary-v1`.

Decision values:

- `pass`: required evidence is present and command logs show no failures.
- `warn`: non-blocking evidence gaps or weak logs exist and require reviewer attention.
- `block`: required evidence is missing, logs failed/interrupted, or validation artifacts cannot be found.

The artifact lists required evidence, evidence-to-artifact expectations, found evidence, missing evidence, implementation follow-up requirements, command-log status, warnings, blockers, and conservative review gaps.

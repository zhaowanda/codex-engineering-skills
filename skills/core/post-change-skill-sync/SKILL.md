---
name: post-change-skill-sync
description: Generate post-change implementation evidence after code, config, docs, or test edits and before release evidence binding. Use after implementation to capture changed files, diff buckets, validation needs, baseline update candidates, and docs binding status without private project overlays.
category: artifact-generator
maturity: deterministic-helper
stage: post-implementation-review
gate: false
---

# Post Change Skill Sync

Use this skill after implementation and before release evidence binding.

## Position

```text
implementation changes
-> implementation-completion-gate
-> post-change-skill-sync
-> code-review-gate / test-evidence-gate / release-evidence-binder
```

## Rules

- Generate `post_change_implementation_report.json` and a human-readable `.md` report in the artifact directory.
- Capture Git branch, HEAD, changed files, diff stat, file buckets, validation needs, baseline update candidates, and project-skill sync candidates.
- Stay open-core: do not depend on private `company/projects.yaml`, private docs governors, or backup code.
- Treat project-skill and baseline updates as owner-review candidates only; do not mutate project skills or baselines automatically.
- If `--require-docs` is set, block when the docs repository, manifest, or doc id is missing.
- This report is not a substitute for test evidence, code review, UAT, CI, or release approval.

## Command

```bash
python3 scripts/sync_after_change.py \
  --repo /path/to/repo \
  --artifact-dir artifacts/REQ-001 \
  --doc-id REQ-001
```

## Output

The output uses schema `codex-post-change-implementation-report-v1`.

The artifact reports decision, changed files, file summary, validation needs, baseline update candidates, project skill sync candidates, docs binding status, blockers, and warnings.

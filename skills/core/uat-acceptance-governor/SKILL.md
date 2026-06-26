---
name: uat-acceptance-governor
description: Generate and validate business UAT acceptance evidence. Use before release when user-visible behavior, reports, permissions, workflows, exports, payments, or cross-repo features require business/product acceptance.
---

# UAT Acceptance Governor

Use this skill when business/product acceptance is required before release.

## Position

```text
test evidence / frontend acceptance
-> uat-acceptance-governor
-> release-evidence-binder
-> release approval
```

## Rules

- Require acceptor, scope, cases, execution result, known issues, and signoff for UAT-required changes.
- Block release if required UAT cases are missing, failed, or unsigned.
- Capture accepted known issues with owner and resolution plan.
- Do not use UAT as a substitute for automated tests or technical acceptance evidence.
- Keep business evidence free of customer secrets and private production data.

## Command

```bash
python3 scripts/uat_acceptance.py template \
  --out artifacts/REQ-001/uat_acceptance.json

python3 scripts/uat_acceptance.py validate \
  --file artifacts/REQ-001/uat_acceptance.json
```

## Output

The output uses schema `codex-uat-acceptance-v1`.

The artifact reports UAT scope, acceptors, cases, results, signoff, blockers, warnings, and known issues.

---
name: spec-governor
description: Normalize one-line requests, long PRDs, pasted notes, or imported requirement text into a structured spec artifact with scope, acceptance criteria, rules, risks, and open questions before technical design or coding.
category: workflow-gate
maturity: expert-gate
stage: requirements
gate: true
---

# Spec Governor

Use this skill before technical design, architecture design, delivery planning, or implementation.

## Command

```bash
python3 scripts/spec_governor.py \
  normalize \
  --doc-id REQ-001 \
  --title "Checkout discount display" \
  --input requirement.txt \
  --out artifacts/REQ-001/spec.json
```

Validate a spec:

```bash
python3 scripts/spec_governor.py \
  validate \
  --file artifacts/REQ-001/spec.json
```

## Rules

- Block design if requirement summary, acceptance criteria, scope, or actors are missing.
- Block implementation if open questions are not closed.
- Block design when extracted business rules conflict.
- Keep extracted facts separate from assumptions.
- For long PRDs, preserve business rules and source evidence references.
- Extract business objects, operations, data fields, state transitions, impact surface, implicit constraints, and negative acceptance needs.
- Convert high-risk implicit constraints into derived clarification questions and expert readiness gaps.
- Treat fully inferred acceptance criteria as usable but not expert-ready until confirmed.

## Output

The output uses schema `codex-spec-v1`.

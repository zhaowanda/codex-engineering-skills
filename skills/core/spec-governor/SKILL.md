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
- Block design if the real business purpose, business flow, or triggering entrypoint cannot be understood or is only inferred from a vague action.
- Require an explicit business purpose/current pain point/expected business outcome; do not treat "optimize/support/fix/sync" as a real purpose.
- Separate confirmed facts, inferred assumptions, and unresolved points; never hide assumptions inside normalized requirements.
- Assign `requirements_understanding.level`: `expert_ready`, `clarification_required`, or `insufficient_context`.
- Block design when ambiguous terms such as "优化", "支持", "同步", "修复", "默认", "状态更新", "optimize", "support", "sync", or "fix" are not resolved into concrete behavior, scope, trigger, and acceptance evidence.
- Block implementation if open questions are not closed.
- Block design when extracted business rules conflict.
- Keep extracted facts separate from assumptions.
- For long PRDs, preserve business rules and source evidence references.
- Extract business objects, operations, data fields, state transitions, impact surface, implicit constraints, and negative acceptance needs.
- Extract business intent, current business problem, expected business outcome, business flow, entrypoints, trigger conditions, preconditions, postconditions, and ambiguity records.
- Convert high-risk implicit constraints into derived clarification questions and expert readiness gaps.
- Treat fully inferred acceptance criteria as usable but not expert-ready until confirmed.
- Do not accept weak acceptance criteria such as "功能正常", "页面展示正确", "数据同步成功", "状态更新正确", or "满足业务需求" without executable evidence rules.

## Output

The output uses schema `codex-spec-v1`.

Key fields:

- `business_intent`
- `business_problem`
- `expected_business_outcome`
- `business_flow`
- `entrypoints`
- `trigger_conditions`
- `ambiguities`
- `requirements_understanding`
- `requirements_understanding_evidence`
- `confirmed_facts`
- `inferred_assumptions`
- `unresolved_points`
- `understanding_confidence`
- `design_allowed`
- `implementation_allowed`

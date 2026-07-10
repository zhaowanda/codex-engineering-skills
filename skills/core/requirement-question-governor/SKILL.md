---
name: requirement-question-governor
description: Generate and validate open requirement questions before design or implementation. Use when spec-governor finds ambiguity, product docs contain TBDs, acceptance criteria are missing, or Codex must stop instead of guessing.
category: workflow-gate
maturity: expert-gate
stage: requirements
gate: true
---

# Requirement Question Governor

Use this skill after ingestion/spec normalization and before design.

## Command

```bash
python3 scripts/question_governor.py \
  generate \
  --spec artifacts/REQ-001/spec.json \
  --out artifacts/REQ-001/open_questions.json
```

Validate answers:

```bash
python3 scripts/question_governor.py \
  validate \
  --file artifacts/REQ-001/open_questions.json
```

## Rules

- Block design/implementation while required questions are open.
- Ask focused questions only; do not ask for information already present in the spec.
- Track owner, required flag, answer, and status.
- Every required question must include `risk_if_unanswered` so reviewers understand why design must stop.
- Generate categorized clarification questions for unclear business goal, business flow, actor/entrypoint, scope boundary, data rule, state transition, trigger timing, exception handling, compatibility, and acceptance evidence.
- Convert `spec.ambiguities` and `requirements_understanding.blockers` into required clarification questions.
- Convert weak `requirements_understanding.scorecard` dimensions into targeted clarification questions.
- Ask for current-state implementation evidence when existing UI/API/task/MQ/manual entrypoints, data ownership, or downstream dependencies are missing.
- Ask decision-level questions for missing business closure, state machine, retry/idempotency/timeout/compensation, dependency chain, and repository/service ownership.
- Generate expert clarification questions from impact surface and implicit constraints, including permission, data/export, API, performance, security, and configuration questions.
- Treat required questions as closed only when they include an answer.

## Output

The output uses schema `codex-open-questions-v1`.

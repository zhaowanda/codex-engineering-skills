---
name: requirement-question-governor
description: Generate and validate open requirement questions before design or implementation. Use when spec-governor finds ambiguity, product docs contain TBDs, acceptance criteria are missing, or Codex must stop instead of guessing.
category: workflow-gate
maturity: expert-gate
stage: requirements
gate: true
---

# Requirement Question Governor

`open_questions.json` may be generated from a blocked `spec.json` draft so the workflow can explain and resolve requirement gaps. This dependency exception permits question generation only: downstream design remains blocked until the requirement source or project evidence is updated and `spec.json` is regenerated with an accepted decision. Closing a question must never override source-location, schema, permission, security, or other evidence gates by itself.

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
  --file artifacts/REQ-001/open_questions.json \
  --spec artifacts/REQ-001/spec.json
```

Answer open questions interactively, one at a time:

```bash
python3 scripts/codex_eng.py clarify --artifact-dir artifacts/REQ-001
```

The command asks required open questions in artifact order and persists both `open_questions.json` and `clarification_answers.md` after every answer. Use `--include-optional` to include optional open questions. It fails closed outside an interactive TTY so CI cannot hang waiting for input. Re-run `auto` with the same artifact directory after answering; the runner creates `requirement.clarified.txt` and regenerates Spec from the original normalized requirement plus confirmed answers.

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
- Reject blank answers for required questions and preserve completed answers on EOF or interruption.
- Record `source=interactive_cli`, actor, and answer timestamp as provenance for every terminal response.
- Bind every generated artifact to the canonical current spec through `spec_digest` and `spec_schema`; validation with `--spec` blocks stale question sets.
- Derive stable question IDs from the question source, category, and text so regeneration can carry answers forward without relying on list position.
- Regenerate and merge instead of skipping an existing artifact. Preserve prior answers and append `answer_provenance` when the same stable question remains applicable.
- Retain questions that disappear from the current spec as `status=obsolete`, set `required=false`, and preserve their history without allowing them to block the current decision.
- Never carry an answer to a materially changed question with a different stable ID; require a new answer instead.

## Output

The output uses schema `codex-open-questions-v1` and includes `spec_schema`, `spec_digest`, `generated_at`, stable question IDs, and answer provenance where answers were carried forward.

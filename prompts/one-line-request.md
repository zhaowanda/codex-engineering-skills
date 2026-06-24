# One-Line Request Prompt

Scenario: a user gives a short requirement and wants Codex to expand it safely.

Use the Codex engineering skills workflow. Convert the one-line request into explicit artifacts before editing code.

Required behavior:

- Identify scope boundary and out-of-scope items.
- Produce or update requirement, spec, technical design, architecture design, test design, traceability, and risk artifacts as needed.
- Stop before implementation if open questions, missing evidence, missing Git branch, or missing edit readiness exists.
- Use compact artifact JSON as context and avoid broad source reads unless routed by an index.
- Report the next command and evidence needed to continue.

Stop conditions:

- Requirement is ambiguous.
- Project boundary is unknown.
- Git readiness is missing.
- Edit permit is missing.

Evidence:

- List generated artifacts.
- List unanswered questions.
- List validation commands that passed or failed.

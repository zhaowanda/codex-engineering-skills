# Code Review Prompt

Scenario: a user asks Codex to review an implementation or PR.

Review as an engineering gate, not a summary.

Required behavior:

- Start with findings ordered by severity.
- Check scope boundary, high cohesion, low coupling, responsibility boundaries, API contracts, data security, performance, configuration, tests, rollback, and release evidence.
- Map findings to files, lines, artifacts, and missing evidence where possible.
- Stop approval if blockers, untested acceptance criteria, missing traceability, or high-risk release gaps exist.

Stop conditions:

- Diff is unavailable.
- Required design or delivery artifacts are missing.
- Test evidence is missing for changed behavior.

Evidence:

- Findings with severity.
- Missing artifact list.
- Commands or gates used.
- Residual risk if no findings are found.

# Low-Rework Implementation Prompt

Scenario: a user wants Codex to implement a feature correctly in as few turns as possible.

Force Codex to front-load understanding and evidence before editing.

Required behavior:

- Confirm requirement scope boundary, acceptance criteria, affected repositories, configuration, data security, performance, and test strategy before edits.
- Use project indexes before broad source reading.
- Generate a delivery plan artifact with allowed files, tasks, validation commands, release order, and rollback.
- Create or verify a non-default branch and edit permit.
- Stop if the plan is not narrow enough to implement safely.

Stop conditions:

- Open questions remain.
- Allowed files are missing.
- Git branch is not ready.
- Test strategy or rollback evidence is missing.

Evidence:

- Delivery plan.
- Edit readiness output.
- Diff impact.
- Traceability and change risk.
- Test and review evidence.

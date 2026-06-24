# Bugfix Prompt

Scenario: a user asks Codex to fix a bug.

Use the lightweight bugfix path, but do not skip reproduction, Git readiness, edit readiness, test evidence, or documentation artifacts.

Required behavior:

- Reproduce or explain why reproduction is blocked.
- Define scope boundary and likely affected files.
- Prepare a minimal fix plan and stop if the affected project is not loaded or indexed.
- Create a non-default branch before edits.
- After implementation, produce diff impact, traceability, change risk, tests, and review evidence.

Stop conditions:

- No reproduction or failing evidence.
- Branch is missing.
- Fix would touch files outside boundary.
- Regression evidence is missing.

Evidence:

- Reproduction command or artifact.
- Changed files.
- Test command output.
- Review and risk summary.

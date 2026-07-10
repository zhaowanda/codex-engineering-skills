# Small Feature Scenario

Business purpose: Help engineers quickly understand delivery progress without manually opening every artifact file.

Scenario: Engineer runs the progress command in an artifact directory, the command reads existing JSON artifacts, and prints completed stages plus the next missing stage.

Entry: CLI command invoked by an engineer in a local workspace.

Req: Add a command that summarizes delivery progress from existing artifact JSON files.

Acceptance criteria:

- The command prints completed stages.
- The command prints the next missing stage.
- The command does not require private project data.

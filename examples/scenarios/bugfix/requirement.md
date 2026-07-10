# Bugfix Scenario

Business purpose: Stop incomplete delivery artifacts from being treated as ready when required test evidence has not been provided.

Scenario: Engineer validates a generated delivery artifact, the gate detects missing required test evidence, and the artifact remains blocked until evidence is attached.

Entry: Delivery validation gate run against generated artifacts.

Req: Fix a validation bug where a generated delivery artifact is marked ready even when required test evidence is missing.

Acceptance criteria:

- The gate blocks missing test evidence.
- The error message identifies the missing evidence.
- Existing passing artifacts remain accepted.
